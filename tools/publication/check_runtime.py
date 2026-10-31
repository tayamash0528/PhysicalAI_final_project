"""公開候補の主要依存・GPU・採用識別情報を読み取り検査する。"""
import importlib.metadata
import json
import platform
from pathlib import Path

import torch


def main():
    expected = {'torch': '2.7.1', 'torchvision': '0.22.1', 'lerobot': '0.6.2',
                'hf-libero': '0.1.4', 'transformers': '5.5.4', 'mujoco': '3.8.1', 'robosuite': '1.4.0'}
    actual = {name: importlib.metadata.version(name) for name in expected}
    different = {name: dict(expected=version, actual=actual[name])
                 for name, version in expected.items() if actual[name] != version}
    report = dict(python=platform.python_version(), dependencies=actual, mismatches=different,
                  cuda_available=torch.cuda.is_available(), torch_cuda=torch.version.cuda)
    if report['cuda_available']:
        report['gpu'] = torch.cuda.get_device_name(0)
    out = Path('results/publication_runtime_check.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if different or not report['cuda_available'] or report['python'] != '3.12.16':
        raise SystemExit('検証済み環境との差があります。結果を確認してください。')


if __name__ == '__main__':
    main()
