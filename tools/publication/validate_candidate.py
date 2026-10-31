"""学習・実験を行わず、公開候補の採用SHAと結果CSV・参照文書を確認する。"""
import argparse
import ast
import csv
import hashlib
import json
import re
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='results/publication_static_check.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    checks = []
    experiments = [('initial', 'main_comparison'),
                   ('relocated_apple', 'holdout_comparison')]
    for exp, sub in experiments:
        base = root / 'evaluation' / exp / sub
        lock = json.loads((base / 'LOCK.json').read_text(encoding='utf-8'))
        for section in ('source_sha256', 'asset_sha256'):
            for name, expected in lock[section].items():
                assert sha(root / name) == expected, name
        assert sha(base / 'episode_setups.json') == lock['episode_setups_sha256']
        if (root / lock['delta']).exists():
            assert sha(root / lock['delta']) == lock['delta_sha256']
        rows = list(csv.DictReader((base / 'results.csv').open(encoding='utf-8-sig')))
        assert len(rows) == 20
        for occlusion, expected in ([('none', (5, 5)), ('leaf_visual', (2, 4))]
                                    if sub == 'main_comparison' else [('leaf_visual', (4, 4))]):
            for method, count in zip(['no_reobserve', 'reobserve'], expected):
                chosen = [r for r in rows if r['occlusion'] == occlusion and r['method'] == method]
                assert sum(r['placement_success'] == 'True' for r in chosen) == count
        if sub == 'holdout_comparison':
            for method, count in [('no_reobserve', 8), ('reobserve', 5)]:
                assert sum(r['grasp_success_50mm_2sec'] == 'True' for r in rows if r['method'] == method) == count
        checks.append(dict(experiment=exp, formal_trials=len(rows), fixed_hashes_match=True))
    sources = [p for parent in ['scripts', 'tools', 'evaluation'] for p in (root / parent).rglob('*.py')]
    for path in sources:
        ast.parse(path.read_text(encoding='utf-8-sig'))
    broken = []
    for name in ['README.md', 'docs/reproduction.md', 'docs/readme_validation.md',
                 'docs/distribution.md', 'docs/development_history.md']:
        path = root / name
        text = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if target.startswith(('https://', 'http://', '#')):
                continue
            if not (path.parent / target.split('#')[0]).exists():
                broken.append(dict(document=name, target=target))
    assert not broken, broken
    result = dict(passed=True, experiments=checks, python_sources_parsed=len(sources),
                  main_document_links_resolved=True, performance_runs_started=0)
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
