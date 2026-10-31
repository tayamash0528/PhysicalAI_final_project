"""POSTHOC EVAL_ONLY red-visibility proxy; never run a policy or step a robot.

Restore saved MuJoCo states and render the same real camera twice, with the leaf
visible and (evaluation only) hidden.  Saved policy RGBs are never overwritten.
The ratio is red-pixel evidence, NOT an exact visible apple surface fraction.
Run from the project root in the existing simulator environment, after trials.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import random
import shutil
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT / 'scripts'))

import numpy as np
from PIL import Image, ImageDraw

VIEWS = ('image', 'image2')
SCHEMA = 'posthoc_same_state_leaf_hidden_rgb_v1'


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def official_rgb(obs):
    # Matches active_observation.save_views and the trained LIBERO image rotation.
    return {key: np.ascontiguousarray(obs['pixels'][key][::-1, ::-1]) for key in VIEWS}


def red_pixels(rgb):
    a = rgb.astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return int(((r > 80) & (r > 1.5 * g) & (r > 1.5 * b)).sum())


def image_error(actual, replay):
    if actual.shape != replay.shape:
        return {'saved_shape': list(actual.shape), 'replay_shape': list(replay.shape),
                'exact_match': False, 'mean_absolute_error_0_255': None,
                'max_absolute_error_0_255': None}
    d = np.abs(actual.astype(np.int16) - replay.astype(np.int16))
    return {'saved_shape': list(actual.shape), 'replay_shape': list(replay.shape),
            'exact_match': bool(not np.any(d)),
            'mean_absolute_error_0_255': float(d.mean()),
            'max_absolute_error_0_255': int(d.max()),
            'differing_pixel_count': int(np.any(d != 0, axis=-1).sum())}


def current_observation(env):
    return env._format_raw_obs(env._env.env._get_observations(force_update=True))


def assert_snapshot_dimensions(env, flat):
    current = np.asarray(env._env.sim.get_state().flatten())
    if flat.shape != current.shape:
        raise ValueError(f'Saved/current state shapes differ: {flat.shape} != {current.shape}; '
                         'do not invent missing leaf state')


def evaluate_snapshot(env, state_path, saved_images, folder, frame_id, min_red, kind):
    """Only restore + render. No env.step, controllers, action replay, or policy."""
    folder.mkdir(parents=True, exist_ok=True)
    sim = env._env.sim
    flat = np.load(state_path, allow_pickle=False)
    assert_snapshot_dimensions(env, flat)
    rgba_before = sim.model.geom_rgba.copy()
    try:
        raw = env._env.set_init_state(flat)
        obs = env._format_raw_obs(raw)
        actual_replay = official_rgb(obs)
        actual = {k: np.array(Image.open(saved_images[k]).convert('RGB')) for k in VIEWS}
        errors = {k: image_error(actual[k], actual_replay[k]) for k in VIEWS}
        for k in VIEWS:
            Image.fromarray(actual_replay[k]).save(folder / f'EVAL_ONLY_replayed_actual_{k}.png')
        if kind == 'none':
            reference = {k: actual_replay[k].copy() for k in VIEWS}
            reference_method = 'clear_scene_no_leaf_to_hide'
        else:
            gid = sim.model.geom_name2id('observation_leaf_visual')
            sim.model.geom_rgba[gid, 3] = 0
            reference = official_rgb(current_observation(env))
            reference_method = 'same_state_same_actual_cameras_only_leaf_visual_alpha_zero'
        views = {}
        for k in VIEWS:
            Image.fromarray(reference[k]).save(folder / f'EVAL_ONLY_leaf_hidden_reference_{k}.png')
            nr, nf = red_pixels(actual[k]), red_pixels(reference[k])
            views[k] = {'visible_red_ratio': nr / nf if nf else None,
                        'actual_red_pixels': nr, 'reference_red_pixels': nf,
                        'reference_min_red_pixels': min_red,
                        'reference_red_pixels_sufficient': bool(nf >= min_red),
                        'ratio_valid': bool(nf >= min_red and errors[k]['exact_match']),
                        'ratio_not_clamped': True,
                        'reference_zero_reason': 'no red reference evidence; frustum/background/occlusion ambiguous' if not nf else None,
                        'saved_actual_image': str(saved_images[k]),
                        'evaluation_only_reference_image': str(folder / f'EVAL_ONLY_leaf_hidden_reference_{k}.png')}
            canvas = Image.new('RGB', (actual[k].shape[1] * 3, actual[k].shape[0] + 38), 'white')
            draw = ImageDraw.Draw(canvas)
            for i, (name, pixels) in enumerate((('SAVED actual policy RGB', actual[k]),
                                               ('EVAL_ONLY restored actual', actual_replay[k]),
                                               ('EVAL_ONLY leaf-hidden reference', reference[k]))):
                x = i * actual[k].shape[1]
                canvas.paste(Image.fromarray(pixels), (x, 38))
                draw.text((x + 4, 4), name, fill='black')
            draw.text((4, 20), f'EVAL_ONLY / {k} / frame {frame_id} / red evidence proxy, not exact surface area', fill='black')
            canvas.save(folder / f'EVAL_ONLY_saved_replay_reference_{k}.png')
        return {'status': 'measured', 'views': views, 'frame_id': frame_id,
                'uses_truth_only_for_evaluation': True,
                'saved_sim_state': str(state_path), 'saved_sim_state_sha256': sha(state_path),
                'actual_replay_image_error': errors,
                'actual_replay_images_exact_match': all(x['exact_match'] for x in errors.values()),
                'reference_method': reference_method,
                'policy_or_controller_executed': False,
                'metric_limitation': 'Red-pixel evidence relative to leaf-hidden same-camera reference, '
                'not exact visible surface area. Other robot/environment occlusion remains. '
                'Ratios may exceed 1 due to render/color effects; zero reference gives null.'}
    finally:
        # Restore every geom even when state restoration, observation, or rendering failed.
        sim.model.geom_rgba[:] = rgba_before
        current_observation(env)
        if not np.array_equal(sim.model.geom_rgba, rgba_before):
            raise RuntimeError('Geom RGBA restoration verification failed')


def missing(reason, frame_id=None):
    return {'status': 'not_measured', 'reason': reason, 'frame_id': frame_id,
            'uses_truth_only_for_evaluation': True, 'views': {}}


def discover(root):
    if (root / 'result.json').exists():
        return [root]
    episodes = sorted(root.glob('episode_*/result.json'))
    if not episodes:
        episodes = sorted((root / 'trials').glob('episode_*/result.json'))
    return [p.parent for p in episodes]


def provenance_check(manifest):
    """Record and enforce the source/assets which define the restored scene."""
    checks = []
    for key in ('source_sha256', 'asset_sha256'):
        for original, expected in manifest.get(key, {}).items():
            path = Path(original)
            # Docker /workspace paths and Windows paths both map to the project.
            portable = original.replace('\\', '/')
            if '/scripts/' in portable:
                path = PROJECT / 'scripts' / portable.rsplit('/scripts/', 1)[1]
            elif not path.is_absolute():
                path = PROJECT / path
            relevant = key == 'asset_sha256' or path.name in ('fruit_objects.py', 'occlusion_scene.py')
            if not relevant:
                continue
            actual = sha(path) if path.exists() else None
            checks.append({'path': str(path), 'expected_sha256': expected, 'actual_sha256': actual,
                           'matches': actual == expected})
    if any(not x['matches'] for x in checks):
        raise ValueError('Scene source/assets no longer match executed manifest: ' + json.dumps(checks))
    return checks


def evaluate_episode(ep, args, LiberoEnv, scene):
    result = read(ep / 'result.json')
    manifest_path = ep.parent / 'manifest.json'
    manifest = read(manifest_path) if manifest_path.exists() else {}
    setup = result.get('setup_only', {})
    kind = setup.get('occlusion', result.get('occlusion', 'none'))
    checks = provenance_check(manifest)
    task = SimpleNamespace(name='apple_single',
                           language=manifest.get('instruction', 'pick up the apple and place it in the tray'),
                           problem_folder='', bddl_file=str(PROJECT / 'tasks/apple_single.bddl'))
    class Suite:
        def get_task(self, _):
            return task
    scene.install(kind, setup.get('leaf_half_size_m'))
    env = None
    phases = {}
    errors = []
    try:
        env = LiberoEnv(Suite(), int(manifest.get('task_id', 0)), manifest.get('suite', 'libero_spatial'),
                        observation_height=256, observation_width=256,
                        obs_type='pixels_agent_pos', control_freq=20, init_states=False,
                        episode_index=int(result.get('episode', 0)), hard_reset=True,
                        episode_length=int(manifest.get('max_steps', 900)))
        seed = int(result.get('seed', setup.get('seed', 0)))
        random.seed(seed)
        np.random.seed(seed)
        env.reset(seed=seed)
        candidates = {'initial': (ep / 'initial_sim_state.npy',
                                  {k: ep / 'reobservation' / f'before_{k}.png' for k in VIEWS}, 0)}
        metadata = ep / 'matched_time' / 'metadata.json'
        matched_frame = int(read(metadata)['pre_action_frame_id']) if metadata.exists() else 45
        candidates['matched_time'] = (ep / 'matched_time' / f'evaluation_only_state_{matched_frame:04d}.npy',
                                      {k: ep / 'matched_time' / f'frame_{matched_frame:04d}_{k}.png' for k in VIEWS},
                                      matched_frame)
        for name, (state_path, images, frame) in candidates.items():
            missing_files = [str(p) for p in (state_path, *images.values()) if not p.exists()]
            if missing_files:
                phases[name] = missing('Required saved state/RGB missing: ' + ', '.join(missing_files), frame)
                continue
            try:
                phases[name] = evaluate_snapshot(env, state_path, images,
                                                ep / 'evaluation_only_visibility' / name,
                                                frame, args.min_reference_red_pixels, kind)
            except Exception:
                error = traceback.format_exc()
                errors.append({'phase': name, 'traceback': error})
                phases[name] = {'status': 'error', 'error': error, 'frame_id': frame,
                                'uses_truth_only_for_evaluation': True, 'views': {}}
        decision = result.get('reobservation_decision') or {}
        if (ep / 'reobservation' / 'decision.json').exists():
            decision = read(ep / 'reobservation' / 'decision.json')
        obs_steps = int(result.get('observation_steps', 0))
        if decision.get('executed') and obs_steps:
            after_frame = int(decision.get('image_frame_after', obs_steps))
            if after_frame == matched_frame and phases['matched_time'].get('status') == 'measured':
                # Confirm actual observation handoff PNGs match this saved-state snapshot.
                extra = {}
                for k in VIEWS:
                    ap = ep / 'reobservation' / f'after_{k}.png'
                    mp = candidates['matched_time'][1][k]
                    if ap.exists():
                        extra[k] = image_error(np.array(Image.open(ap).convert('RGB')),
                                               np.array(Image.open(mp).convert('RGB')))
                    else:
                        extra[k] = {'exact_match': False, 'reason': 'after PNG missing'}
                if all(x['exact_match'] for x in extra.values()):
                    phases['after_observation'] = dict(phases['matched_time'],
                        same_data_as='matched_time', after_observation_saved_image_error=extra)
                else:
                    phases['after_observation'] = missing('After-observation RGB does not match saved matched-time RGB', after_frame)
                    phases['after_observation']['matched_time_saved_image_error'] = extra
            else:
                phases['after_observation'] = missing('No complete state snapshot at observation end; no action replay or interpolation performed', after_frame)
        else:
            phases['after_observation'] = missing('No observation-only movement executed; use initial and matched_time separately', 0)
        payload = {'schema_version': SCHEMA, 'evaluated_utc': utc(), 'episode': str(ep),
                   'case_id': result.get('case_id'), 'method': result.get('method'), 'occlusion': kind,
                   'status': 'completed_with_phase_errors' if errors else 'completed',
                   'uses_truth_only_for_evaluation': True, 'never_used_by_policy_or_observer': True,
                   'policy_or_controller_executed': False, 'scene_provenance_checks': checks,
                   'source_sha256': sha(__file__), 'errors': errors, **phases}
        return payload
    finally:
        if env is not None:
            env.close()
        scene.install('none')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True, help='Protocol root, rollout root, or one episode directory')
    p.add_argument('--episode', help='Optional episode directory name, e.g. episode_00')
    p.add_argument('--max-episodes', type=int, help='Bound posthoc processing (does not run rollouts)')
    p.add_argument('--min-reference-red-pixels', type=int, default=100)
    p.add_argument('--overwrite', action='store_true', help='Explicitly recompute an existing evaluation sidecar')
    args = p.parse_args()
    if args.min_reference_red_pixels < 1:
        p.error('--min-reference-red-pixels must be positive')
    root = args.root.resolve()
    episodes = discover(root)
    if args.episode:
        episodes = [ep for ep in episodes if ep.name == args.episode]
    if args.max_episodes is not None:
        if args.max_episodes < 1:
            p.error('--max-episodes must be positive')
        episodes = episodes[:args.max_episodes]
    if not episodes:
        raise SystemExit('No completed episode result.json found')
    archive = root / 'evaluation_only_visibility_provenance'
    archive.mkdir(parents=True, exist_ok=True)
    source_copy = archive / f'evaluate_visibility_{sha(__file__)[:12]}.py'
    if not source_copy.exists():
        shutil.copy2(__file__, source_copy)
    # Import only the installed environment + object registration. No policy/model load.
    from lerobot.envs.libero import LiberoEnv
    import fruit_objects  # noqa: F401 - register exact project object classes
    import occlusion_scene as scene
    versions = {}
    for package in ('lerobot', 'hf-libero', 'robosuite', 'mujoco', 'numpy'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = 'not found via importlib.metadata'
    index = {'schema_version': SCHEMA, 'started_utc': utc(), 'root': str(root),
             'dependencies': versions, 'source_copy': str(source_copy),
             'source_sha256': sha(__file__), 'uses_truth_only_for_evaluation': True,
             'policy_or_controller_executed': False, 'episodes': []}
    failures = 0
    for ep in episodes:
        sidecar = ep / 'visibility_evaluation.json'
        if sidecar.exists() and not args.overwrite:
            index['episodes'].append({'episode': str(ep), 'status': 'existing_sidecar_preserved', 'sidecar': str(sidecar)})
            continue
        try:
            payload = evaluate_episode(ep, args, LiberoEnv, scene)
        except Exception:
            payload = {'schema_version': SCHEMA, 'status': 'episode_error', 'episode': str(ep),
                       'evaluated_utc': utc(), 'uses_truth_only_for_evaluation': True,
                       'policy_or_controller_executed': False, 'error': traceback.format_exc(),
                       'initial': missing('Episode setup/API failed'),
                       'matched_time': missing('Episode setup/API failed'),
                       'after_observation': missing('Episode setup/API failed')}
        dump(sidecar, payload)
        status = payload['status']
        failures += status != 'completed'
        entry = {'episode': str(ep), 'status': status, 'sidecar': str(sidecar)}
        index['episodes'].append(entry)
        print(json.dumps(entry), flush=True)
        dump(archive / 'index.json', index)
    index.update(finished_utc=utc(), failure_episode_count=failures)
    dump(archive / 'index.json', index)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
