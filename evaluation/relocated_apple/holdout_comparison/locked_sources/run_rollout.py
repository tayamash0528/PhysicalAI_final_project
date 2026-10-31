"""Real SmolVLA -> LIBERO rollout with action, image, evaluator and video evidence.

Object poses are written by the evaluator after env.step; they never enter policy inputs.
All manipulation actions originate from select_action + pretrained unnormalization.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import time
import shutil
from types import SimpleNamespace
from pathlib import Path
import imageio.v2 as iio
import numpy as np
import torch
from PIL import Image, ImageDraw
# LIBERO's first import prompts for a dataset path. Supply the same defaults
# noninteractively, with project-local caches, before importing the package.
config_dir = Path('cache/libero').resolve()
config_dir.mkdir(parents=True,exist_ok=True)
os.environ['LIBERO_CONFIG_PATH'] = str(config_dir)
libero_root = Path(next(iter(importlib.util.find_spec('libero').submodule_search_locations)))/'libero'
libero_paths = dict(benchmark_root=str(libero_root),bddl_files=str(libero_root/'bddl_files'),
    init_states=str(libero_root/'init_files'),datasets=str(Path('cache/datasets').resolve()),
    assets=str(libero_root/'assets'))
(config_dir/'config.yaml').write_text(json.dumps(libero_paths))
from libero.libero import benchmark
from lerobot.envs.libero import LiberoEnv
from lerobot.envs.configs import LiberoEnv as LiberoConfig
from lerobot.envs.factory import make_env_pre_post_processors
from lerobot.envs.utils import preprocess_observation
from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig
from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
from lerobot.policies.factory import make_pre_post_processors


def dump(path, value):
    path=Path(path);tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8');tmp.replace(path)


def batched_state(value):
    # Official env processor expects vector-env shaped proprioception (B, dim).
    if isinstance(value, dict): return {k:batched_state(v) for k,v in value.items()}
    if isinstance(value,np.ndarray): return value[None]
    return value


def evaluator(env):
    sim = env._env.sim
    result = {}
    for obj in env._env.env.objects:
        body_id = sim.model.body_name2id(obj.root_body)
        result[obj.name] = sim.data.body_xpos[body_id].tolist()
    return result

def camera_view_evidence(env):
    sim=env._env.sim;result={}
    for key,name in [('image','agentview'),('image2','robot0_eye_in_hand')]:
        cid=sim.model.camera_name2id(name)
        result[key]={'actual_camera':name,'position_world_m':sim.data.cam_xpos[cid].tolist(),
                     'rotation_to_world':sim.data.cam_xmat[cid].tolist()}
    return result


def panel(obs, text):
    # These are the same two views used by the official LIBERO processor (180-deg rotation).
    cams = [obs['pixels'][key][::-1, ::-1] for key in ('image', 'image2')]
    canvas = Image.new('RGB', (1024, 560), '#111827')
    for idx, cam in enumerate(cams):
        canvas.paste(Image.fromarray(cam).resize((512, 512)), (512*idx, 36))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 9), text, fill='white')
    draw.text((10, 548), 'agentview (policy input)', fill='white')
    draw.text((522, 548), 'wrist camera (policy input)', fill='white')
    return np.asarray(canvas)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', default='libero_spatial')
    parser.add_argument('--task-id', type=int, default=0)
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--episodes', type=int, default=1)
    parser.add_argument('--max-steps', type=int, default=280)
    parser.add_argument('--n-action-steps', type=int, default=None)
    parser.add_argument('--fruit-task', choices=['apple_single'], default=None)
    parser.add_argument('--instruction', default=None)
    parser.add_argument('--telemetry',action='store_true',help='Evaluation-only contact/distance logger')
    parser.add_argument('--visibility-eval-step',type=int,default=None,help='Save eval-only full state and real RGB at a matched elapsed step; never used for actions')
    parser.add_argument('--expert-delta',default=None)
    parser.add_argument('--initial-state',default=None,help='Simulator setup only, never a policy feature')
    parser.add_argument('--setup-tray-xy',type=float,nargs=2,default=None,help='Initial scene setup only')
    parser.add_argument('--episode-setups',default=None,help='JSON list of setup-only initial_state, seed, apple_xy, tray_xy')
    parser.add_argument('--trainable-fp32',action='store_true')
    parser.add_argument('--inference-amp',action='store_true')
    parser.add_argument('--active-reobservation',action='store_true')
    parser.add_argument('--observer-profile',choices=['legacy_v3','rgb_candidates_v5','rgb_candidates_v6_aligned','rgb_minimal_tilt_v7','rgb_normal_wrist_v8','rgb_normal_wrist_v9_pregrasp','rgb_early_approach_v10'],default='legacy_v3')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    if args.episode_setups:shutil.copy2(args.episode_setups,out/'executed_episode_setups.json')
    snapshot=out/'source_snapshot';snapshot.mkdir()
    for source in [Path(__file__),*[Path('scripts')/n for n in ['placement_score.py','fruit_objects.py','arm_telemetry.py','occlusion_scene.py','active_observation.py']]]:
        shutil.copy2(source,snapshot/source.name)
    meta = json.loads(Path('evidence/model.json').read_text())
    model_path = meta['local_path']
    cfg = SmolVLAConfig.from_pretrained(model_path)
    cfg.device = 'cuda'
    cfg.pretrained_path = Path(model_path)
    # Entire policy checkpoint contains VLM weights. Do not separately overwrite them.
    cfg.load_vlm_weights = False
    if args.n_action_steps is not None:
        cfg.n_action_steps = args.n_action_steps
    load_start = time.perf_counter()
    policy = SmolVLAPolicy.from_pretrained(model_path, config=cfg).to('cuda').eval()
    if args.trainable_fp32:
        for param in policy.parameters():
            if param.requires_grad:param.data=param.data.float()
    if args.expert_delta:
        from safetensors.torch import load_file
        missing,unexpected=policy.load_state_dict(load_file(args.expert_delta),strict=False)
        if unexpected:raise RuntimeError(f'Unexpected delta keys: {unexpected}')
    pre, post = make_pre_post_processors(cfg, pretrained_path=model_path,
        preprocessor_overrides={'device_processor': {'device': 'cuda'}})
    env_cfg = LiberoConfig(task=args.suite, task_ids=[args.task_id],
                           observation_height=256, observation_width=256)
    env_pre, env_post = make_env_pre_post_processors(env_cfg, cfg)
    load_seconds = time.perf_counter() - load_start
    suite = benchmark.get_benchmark_dict()[args.suite]()
    task = suite.get_task(args.task_id)
    if args.fruit_task:
        import fruit_objects  # registers custom project objects; no object poses read
        from placement_score import PlacementHold, contained, gripper_released
        task = SimpleNamespace(name=args.fruit_task, language='pick up the apple and place it in the tray',
            problem_folder='', bddl_file=str(Path('tasks/apple_single.bddl').resolve()))
        class SingleTask:
            def get_task(self, _): return task
        suite = SingleTask()
    if args.instruction:
        task = SimpleNamespace(**(vars(task) | {'language':args.instruction})) if args.fruit_task else task._replace(language=args.instruction)
    manifest = vars(args) | {'model_id': meta['repo_id'], 'model_revision': meta['revision'],
        'instruction': task.language, 'control_freq_hz': 20, 'control_mode': 'relative',
        'n_action_steps': cfg.n_action_steps, 'model_load_seconds': load_seconds,
        'image_shape': [256, 256, 3], 'robot': 'LIBERO Panda',
        'policy_inputs': ['two camera RGB images', '8D eef/gripper state', 'instruction'],
        'evaluation_truth_used_by_policy': False,
        'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),*[Path('scripts')/n for n in ['placement_score.py','fruit_objects.py','occlusion_scene.py','active_observation.py']]]},
        'asset_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path('tasks/apple_single.bddl'),Path('assets/apple/apple.xml'),Path('assets/apple/apple.obj'),Path('assets/tray/tray.xml')]} if args.fruit_task else {},
        'placement_evaluator_version':'v2_open_command_and_75mm_gap_40_steps' if args.fruit_task else 'native_LIBERO',
        'stage': 'B_apple_single' if args.fruit_task else 'A_native_task',
        'success_criterion': 'full footprint in tray + open gripper + 2s hold' if args.fruit_task
                            else 'native LIBERO check_success (not fruit tray criterion)'}
    dump(out/'manifest.json', manifest)
    if args.expert_delta:
        manifest['expert_delta_sha256']=hashlib.sha256(Path(args.expert_delta).read_bytes()).hexdigest()
        dump(out/'manifest.json',manifest)
    print('Loaded policy; task:', task.language, 'load_s', load_seconds, flush=True)
    summaries = []
    setups=json.loads(Path(args.episode_setups).read_text()) if args.episode_setups else [{} for _ in range(args.episodes)]
    for episode,setup in enumerate(setups):
        seed = setup.get('seed',args.seed+episode)
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        epdir = out/f'episode_{episode:02d}'
        epdir.mkdir()
        (epdir/'inputs').mkdir()
        if args.fruit_task:
            import occlusion_scene
            import active_observation as ao
            occlusion_scene.install(setup.get('occlusion','none'),setup.get('leaf_half_size_m'))
        env = LiberoEnv(suite, args.task_id, args.suite, observation_height=256,
            observation_width=256, obs_type='pixels_agent_pos', control_freq=20,
            init_states=not bool(args.fruit_task), episode_index=episode, hard_reset=True,
            episode_length=args.max_steps)
        t0 = time.perf_counter()
        obs, info = env.reset(seed=seed)
        if args.fruit_task:obs=occlusion_scene.apply_setup(env,obs,setup,args.initial_state,args.setup_tray_xy)
        elif args.initial_state:
            raw=env._env.set_init_state(np.load(args.initial_state));obs=env._format_raw_obs(raw)
        initial_image_acquisition_wall_offset_s=time.perf_counter()-t0
        state = env._env.sim.get_state().flatten()
        np.save(epdir/'initial_sim_state.npy', state)
        policy.reset()
        if hasattr(pre, 'reset'): pre.reset()
        writer = iio.get_writer(str(epdir/'rollout.mp4'), fps=20, codec='libx264', quality=8)
        action_log = (epdir/'actions.jsonl').open('w', encoding='utf-8')
        eval_log = (epdir/'evaluation_only.jsonl').open('w', encoding='utf-8')
        telemetry=None;telemetry_log=None
        if args.telemetry:
            from arm_telemetry import ArmTelemetry
            telemetry=ArmTelemetry(env,'apple_1' if args.fruit_task else 'akita_black_bowl_1')
            dump(epdir/'telemetry_metadata.json',telemetry.metadata())
            telemetry_log=(epdir/'arm_telemetry.jsonl').open('w')
        infer_seconds = 0.0
        sim_wall_seconds = 0.0
        success = False
        hold = PlacementHold() if args.fruit_task else None
        if args.fruit_task:
            # Evaluate the entire visible mesh, not just the object center.
            vertices = np.array([[float(x) for x in line.split()[1:]]
                for line in Path('assets/apple/apple.obj').read_text().splitlines() if line.startswith('v ')])
        writer.append_data(panel(obs, f'{args.suite}/{args.task_id} seed={seed} step=0'))
        active_enabled=bool(setup.get('active_reobservation',args.active_reobservation))
        decision_start=time.perf_counter()
        decision=ao.decide(obs) if args.fruit_task else None
        decision_wall_seconds=time.perf_counter()-decision_start
        observer_classes={'rgb_candidates_v5':ao.CandidateObserver,'rgb_candidates_v6_aligned':ao.AlignedCandidateObserver,'rgb_minimal_tilt_v7':ao.MinimalTiltObserver,'rgb_normal_wrist_v8':ao.NormalWristObserver,'rgb_normal_wrist_v9_pregrasp':ao.NormalWristPregraspObserver,'rgb_early_approach_v10':ao.EarlyApproachObserver} if args.fruit_task else {}
        observer_class=observer_classes.get(args.observer_profile)
        adaptive_observer=observer_class(obs) if decision and decision['trigger'] and active_enabled and observer_class else None
        observer_budget=ao.RULE['motion_steps'] if decision and decision['trigger'] and active_enabled and adaptive_observer is None else 0
        observer_target=ao.observation_target(obs) if observer_budget else None
        observer_applied=0;observer_after_saved=False
        observation_wall_seconds=0.;manipulation_wall_seconds=0.
        phase_handoff_wall_offset_s=None
        if decision:
            selected_rule={'rgb_candidates_v5':ao.CANDIDATE_RULE,'rgb_candidates_v6_aligned':ao.ALIGNED_RULE,'rgb_minimal_tilt_v7':ao.MINIMAL_TILT_RULE,'rgb_normal_wrist_v8':ao.NORMAL_WRIST_RULE,'rgb_normal_wrist_v9_pregrasp':ao.NORMAL_WRIST_PREGRASP_RULE,'rgb_early_approach_v10':ao.EARLY_APPROACH_RULE}.get(args.observer_profile,ao.RULE)
            decision.update(enabled=active_enabled,executed=bool(observer_budget or adaptive_observer),
                rule=selected_rule,trigger_rule=ao.TRIGGER_RULE,
                observer_profile=args.observer_profile,candidate_rule=selected_rule if observer_class else None,
                target_eef_m=adaptive_observer.target[0].tolist() if adaptive_observer else observer_target.tolist() if observer_budget else None,
                views_before=camera_view_evidence(env),image_frame_before=0,
                decision_wall_seconds=decision_wall_seconds,decision_wall_offset_s=decision_start-t0,
                initial_image_acquisition_wall_offset_s=initial_image_acquisition_wall_offset_s)
            ao.save_views(obs,epdir/'reobservation','before')
            dump(epdir/'reobservation/decision.json',decision)
        for step in range(args.max_steps):
            loop_start=time.perf_counter()
            is_observation=(not adaptive_observer.done) if adaptive_observer else step<observer_budget
            if observer_applied and not is_observation and not observer_after_saved:
                observer_after_saved=True
                phase_handoff_wall_offset_s=time.perf_counter()-t0
                policy.reset()
                if hasattr(pre,'reset'):pre.reset()
                decision['after_metrics']=ao.image_metrics(obs)
                decision['views_after']=camera_view_evidence(env);decision['image_frame_after']=step
                if adaptive_observer:decision['candidate_visits']=adaptive_observer.visits
                ao.save_views(obs,epdir/'reobservation','after')
                dump(epdir/'reobservation/decision.json',decision)
            if args.fruit_task and args.visibility_eval_step==step:
                probe=epdir/'matched_time';ao.save_views(obs,probe,f'frame_{step:04d}')
                np.save(probe/f'evaluation_only_state_{step:04d}.npy',env._env.sim.get_state().flatten())
                dump(probe/'metadata.json',{'pre_action_frame_id':step,'sim_elapsed_s':step/20,
                    'wall_offset_s':time.perf_counter()-t0,'actual_rgb_metrics':ao.image_metrics(obs),
                    'actual_cameras':camera_view_evidence(env),'evaluation_only_state_never_read_by_policy':True})
            policy_observation = dict(obs,robot_state=batched_state(obs['robot_state']))
            observation = preprocess_observation(policy_observation)
            observation['task'] = [task.language]
            observation = env_pre(observation)
            image_hashes={}
            for key in ('image', 'image2'):
                pixels = observation[f'observation.images.{key}'][0].mul(255).byte().permute(1,2,0).cpu().numpy()
                image_hashes[key]=hashlib.sha256(pixels.tobytes()).hexdigest()
                if step % 10 == 0 or step==args.visibility_eval_step or (observer_after_saved and step==observer_applied):
                    Image.fromarray(pixels).save(epdir/'inputs'/f'{step:04d}_{key}.png')
            image_acquisition_wall_offset_s=time.perf_counter()-t0
            state_input = observation['observation.state'].cpu().tolist()
            if is_observation:
                normalized=None;queue_len_before=None;inference_time=0.
                action_np=adaptive_observer.action(obs) if adaptive_observer else ao.action(obs,observer_target);observer_applied+=1
            else:
                torch.cuda.synchronize();ti = time.perf_counter()
                batch = pre(observation);queue_len_before=len(policy._queues['action'])
                with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16,enabled=args.inference_amp):
                    normalized = policy.select_action(batch);action = post(normalized)
                action = env_post({'action': action})['action'];torch.cuda.synchronize()
                inference_time = time.perf_counter() - ti;infer_seconds += inference_time
                action_np = action.detach().cpu().numpy().reshape(-1)
            if not np.isfinite(action_np).all():
                raise RuntimeError('Non-finite action')
            # Gym action safety bound, recorded explicitly. No scripted manipulation.
            applied = np.clip(action_np, -1, 1)
            ts = time.perf_counter()
            obs, reward, terminated, truncated, info = env.step(applied)
            if is_observation and adaptive_observer and adaptive_observer.update(obs):
                ao.save_views(obs,epdir/'reobservation',f'candidate_visit_{len(adaptive_observer.visits):02d}')
            env_step_wall_seconds=time.perf_counter() - ts
            sim_wall_seconds += env_step_wall_seconds
            native_success = bool(info['is_success'])
            if args.fruit_task:
                sim = env._env.sim
                apple_id = sim.model.body_name2id(env._env.env.objects_dict['apple_1'].root_body)
                tray_id = sim.model.body_name2id(env._env.env.objects_dict['tray_1'].root_body)
                inside = contained(sim.data.body_xpos[apple_id],sim.data.body_xmat[apple_id].reshape(3,3),
                    vertices,sim.data.body_xpos[tray_id],sim.data.body_xmat[tray_id].reshape(3,3))
                mesh_world=vertices@sim.data.body_xmat[apple_id].reshape(3,3).T+sim.data.body_xpos[apple_id]
                mesh_tray=(mesh_world-sim.data.body_xpos[tray_id])@sim.data.body_xmat[tray_id].reshape(3,3)
                footprint_inside=bool(np.all((mesh_tray[:,:2]>=-.074)&(mesh_tray[:,:2]<=.074)))
                # Panda fingers use opposite joint signs; opening is the absolute gap.
                grip_open = gripper_released(obs['robot_state']['gripper']['qpos'],applied[-1])
                success = hold.update(inside,grip_open)
            else:
                success = native_success
            action_log.write(json.dumps({'step': step, 'source': 'observation_OSC' if is_observation else 'SmolVLA.select_action',
                'state_input': state_input, 'normalized_action': normalized.detach().cpu().tolist() if normalized is not None else None,
                'unnormalized_action': action_np.tolist(), 'applied_action': applied.tolist(),
                'inference_seconds': inference_time, 'native_success': native_success,
                'action_queue_len_before':queue_len_before,'predicted_new_chunk':not is_observation and queue_len_before==0,
                'phase':'observation' if is_observation else 'vla','pre_action_frame_id':step,
                'image_sha256':image_hashes,'image_acquisition_wall_offset_s':image_acquisition_wall_offset_s,
                'env_step_wall_seconds':env_step_wall_seconds,
                'project_success': success, 'tray_hold_steps': hold.streak if hold else None})+'\n')
            if telemetry_log:
                telemetry_log.write(json.dumps(telemetry.sample(step,applied,obs,'observation' if is_observation else 'vla'))+'\n')
            eval_row={'step': step, 'object_positions': evaluator(env)}
            if args.fruit_task:eval_row.update(footprint_inside_tray=footprint_inside,contained_and_supported=inside,
                released=grip_open,hold_streak=hold.streak,mesh_bottom_tray_m=float(mesh_tray[:,2].min()))
            if setup.get('occlusion') in ('leaf','leaf_visual'):
                leaf_id=env._env.sim.model.body_name2id('observation_leaf')
                eval_row['evaluation_only_leaf_position']=env._env.sim.data.body_xpos[leaf_id].tolist()
            eval_log.write(json.dumps(eval_row)+'\n')
            writer.append_data(panel(obs, f'{args.suite}/{args.task_id} seed={seed} step={step+1} success={success}'))
            phase_wall=time.perf_counter()-loop_start
            if is_observation:observation_wall_seconds+=phase_wall
            else:manipulation_wall_seconds+=phase_wall
            if step % 20 == 0 or success:
                print(f'episode={episode} step={step+1} success={success} infer={inference_time:.3f}s', flush=True)
                action_log.flush()
            if success or (not args.fruit_task and (terminated or truncated)):
                break
        writer.close()
        action_log.close()
        eval_log.close()
        if telemetry_log:telemetry_log.close()
        result = {'episode': episode, 'seed': seed, 'init_state_index': episode,
            'initial_state_sha256': hashlib.sha256(state.tobytes()).hexdigest(),
            'setup_only':setup,
            'steps': step+1, 'native_success': native_success, 'project_success': success,
            'stage': manifest['stage'], 'sim_seconds': (step+1)/20,
            'wall_seconds_including_reset': time.perf_counter()-t0,
            'inference_seconds': infer_seconds, 'sim_step_wall_seconds': sim_wall_seconds,
            'stop_reason': ('project_placement_success' if args.fruit_task else 'native_success') if success else 'max_steps',
            'placement_evaluator_version':manifest['placement_evaluator_version'],
            'telemetry_stage_counts':telemetry.stage_counts if telemetry else None,
            'manipulation_source': 'finetuned SmolVLA.select_action' if args.expert_delta else 'pretrained SmolVLA.select_action',
            'reobservation_count':len(adaptive_observer.visits) if adaptive_observer else int(observer_applied>0),
            'observation_steps':observer_applied,'vla_steps':step+1-observer_applied,
            'observation_wall_seconds':observation_wall_seconds,'manipulation_wall_seconds':manipulation_wall_seconds,
            'decision_wall_seconds':decision_wall_seconds,'phase_handoff_wall_offset_s':phase_handoff_wall_offset_s,
            'image_update_contract':'fresh actual camera observations each control step; action chunk length unchanged',
            'reobservation_decision':decision,'occlusion':setup.get('occlusion','none'),
            'method':'reobserve' if active_enabled else 'no_reobserve','case_id':setup.get('case_id')}
        dump(epdir/'result.json', result)
        summaries.append(result)
        dump(out/'summary.json', summaries)
        env.close()
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
