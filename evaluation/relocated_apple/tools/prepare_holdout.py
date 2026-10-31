"""Prepare identical pairs for the frozen adopted procedure; no VLA is executed."""
import datetime,hashlib,json,random,shutil,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path('scripts').resolve()))
import run_rollout as rr
import fruit_objects,occlusion_scene as scene,active_observation as ao
BASE=Path('evaluation/relocated_apple');OLD=Path('evaluation/initial');OUT=BASE/'holdout_comparison'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=read(BASE/'PLAN.json');layouts=read(BASE/'NEW_POSITIONS.json');parent=read(OLD/'main_comparison/LOCK.json');adopt=read(OLD/'adoption_check/adopted_candidate/candidate_manifest.json')
assert len(layouts['positions'])==plan['case_count_fixed_before_results']==10
for key in ['source_sha256','asset_sha256']:
    for p,h in parent[key].items():assert sha(p)==h,p
assert sha(parent['delta'])==parent['delta_sha256']==adopt['checkpoint_sha256']
assert sha(OLD/'adoption_check/adopted_candidate/checkpoint/expert_delta.safetensors')==parent['delta_sha256']
texture='assets/apple/texture.png';assert sha(texture)==adopt['files'][texture]
selection=read(OLD/'MAIN_SELECTION.json');assert selection['observer_profile']=='rgb_early_approach_v10'
OUT.mkdir(parents=True,exist_ok=False);(OUT/'locked_sources').mkdir();shutil.copy2(__file__,OUT/'prepare_holdout.py')
for p in parent['source_sha256']:shutil.copy2(p,OUT/'locked_sources'/Path(p).name)
for p in [*parent['asset_sha256'],texture]:
    dest=OUT/'locked_assets'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
task=SimpleNamespace(name='apple_single',language=parent['instruction'],problem_folder='',bddl_file=str(Path('tasks/apple_single.bddl').resolve()))
class Suite:
    def get_task(self,_):return task
truth=[];blocks=[];rng=random.Random(plan['execution_order_seed'])
for row in layouts['positions']:
    case=row['case_id'];seed=row['seed'];scene.install('leaf_visual',selection['half_size_m'])
    env=rr.LiberoEnv(Suite(),0,'libero_spatial',observation_height=256,observation_width=256,obs_type='pixels_agent_pos',control_freq=20,init_states=False,hard_reset=True,episode_length=900)
    obs,_=env.reset(seed=seed)
    setup={'initial_state':'training/demonstrations/train_00/initial_sim_state.npy','apple_xy':row['xy_m'],'tray_xy':[.04,.15],'occlusion':'leaf_visual','leaf_height_above_root_m':selection['height_above_root_m'],'leaf_anchor':'initial_wrist_ray','leaf_half_size_m':selection['half_size_m']}
    obs=scene.apply_setup(env,obs,setup);d=OUT/'initial_states'/case;d.mkdir(parents=True);state=env._env.sim.get_state().flatten();np.save(d/'state.npy',state);ao.save_views(obs,d,'initial')
    truth.append({'case_id':case,'seed':seed,'occlusion':'leaf_visual','setup_evaluation_only':setup,'state_file_sha256':sha(d/'state.npy'),'state_array_sha256':hashlib.sha256(state.tobytes()).hexdigest(),'initial_rgb_trigger':ao.decide(obs),'object_positions_evaluation_only':rr.evaluator(env)})
    pair=[{'case_id':case,'initial_state':str(d/'state.npy'),'scene_prepared':True,'occlusion':'leaf_visual','leaf_half_size_m':selection['half_size_m'],'seed':seed,'active_reobservation':active,'split':'new_local_positions_unused_for_training_selection_or_previous_evaluation'} for active in [False,True]]
    rng.shuffle(pair);blocks.append(pair);env.close();print('PREPARED',case,flush=True)
rng.shuffle(blocks);setups=[s for pair in blocks for s in pair];rr.dump(OUT/'episode_setups.json',setups);rr.dump(OUT/'evaluation_only_conditions.json',truth)
lock=dict(parent);lock.update(status='LOCKED_BEFORE_MAIN_TRIALS',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),trials=20,cases=10,clear_cases=0,leaf_cases=10,episode_setups_sha256=sha(OUT/'episode_setups.json'),reserved_layouts_file=str(BASE/'NEW_POSITIONS.json'),reserved_layouts_sha256=sha(BASE/'NEW_POSITIONS.json'),initial_states=truth,order_seed=plan['execution_order_seed'],parent_protocol_file=str(OLD/'main_comparison/LOCK.json'),parent_protocol_sha256=sha(OLD/'main_comparison/LOCK.json'),position_audit_sha256=layouts['position_audit_sha256'],new_evaluation_results_seen_before_lock=False,no_results_seen_before_lock=True,no_tuning_after_main=True,evaluation_role='new_positions_fixed_adopted_procedure_leaf_only',old5_result_preserved='2/5 no_reobserve vs4/5 reobserve confirmed',supplemental_asset_sha256={texture:sha(texture)},plan_sha256=sha(BASE/'PLAN.json'))
lock['protocol_tools_sha256']={str(BASE/'tools/prepare_holdout.py'):sha(__file__),str(BASE/'tools/generate_layouts.py'):sha(BASE/'tools/generate_layouts.py'),str(OLD/'tools/run_protocol.py'):sha(OLD/'tools/run_protocol.py')}
rr.dump(OUT/'LOCK.json',lock);print('LOCKED20_LEAF_TRIALS',sha(OUT/'LOCK.json'),flush=True)
