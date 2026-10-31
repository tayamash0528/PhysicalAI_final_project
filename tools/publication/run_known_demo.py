"""既知leaf_02の1試行を別出力へ実行。性能評価には加算しない。"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    checkpoint = Path('models/fruit_vla/expert_delta.safetensors')
    expected = '67a1dd9044c21f4b13de96afca496099e02f9531b624879f151fc3996e991ac2'
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != expected:
        raise ValueError('採用C1250のSHA256が一致しません')
    origin = Path('evaluation/initial/main_comparison')
    locked = json.loads((origin / 'LOCK.json').read_text(encoding='utf-8'))
    for section in ('source_sha256', 'asset_sha256'):
        for name, digest in locked[section].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
                raise ValueError(f'採用版ファイルが一致しません: {name}')
    setups = json.loads((origin / 'episode_setups.json').read_text(encoding='utf-8'))
    one = [entry for entry in setups if entry['case_id'] == 'leaf_02' and entry['active_reobservation']]
    if len(one) != 1:
        raise ValueError('既知条件を1件に限定できません')
    args.out.mkdir(parents=True, exist_ok=False)
    setup_path = args.out / 'setups.json'
    setup_path.write_text(json.dumps(one, indent=2), encoding='utf-8')
    command = [sys.executable, 'scripts/run_rollout.py', '--fruit-task', 'apple_single',
               '--episode-setups', str(setup_path), '--observer-profile', 'rgb_early_approach_v10',
               '--max-steps', '900', '--n-action-steps', '10', '--visibility-eval-step', '45',
               '--telemetry', '--trainable-fp32', '--inference-amp', '--expert-delta', str(checkpoint),
               '--out', str(args.out / 'rollout')]
    (args.out / 'command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
    outcome = subprocess.run(command)
    (args.out / 'execution.json').write_text(json.dumps({'return_code': outcome.returncode,
        'performance_evaluation': False, 'case_id': 'leaf_02', 'seed': one[0]['seed']}), encoding='utf-8')
    raise SystemExit(outcome.returncode)


if __name__ == '__main__':
    main()
