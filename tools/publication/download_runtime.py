"""固定revisionの公開モデルとLIBEROアセットを取得する。学習は行わない。"""
import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--out', default='results/runtime_download.json')
    args = parser.parse_args()
    records = []
    sources = [
        dict(repo_id='HuggingFaceVLA/smolvla_libero', revision='6721902bc4d61e50a3bfdb11dfb4cb626f05d102'),
        dict(repo_id='HuggingFaceTB/SmolVLM2-500M-Instruct', revision='7b375e1b73b11138ff12fe22c8f2822d8fe03467',
             allow_patterns=['*.json', '*.jinja', '*.txt', '*.model']),
    ]
    for source in sources:
        path = snapshot_download(**source, local_files_only=args.offline)
        records.append(dict(repo_id=source['repo_id'], revision=source['revision'], path=path))
    processor_snapshot = Path(records[1]['path'])
    processor_ref = processor_snapshot.parents[1] / 'refs/main'
    if not processor_ref.exists() or processor_ref.read_text().strip() != sources[1]['revision']:
        processor_ref.parent.mkdir(parents=True, exist_ok=True)
        processor_ref.write_text(sources[1]['revision'], encoding='utf-8')
    asset_path = snapshot_download(repo_id='lerobot/libero-assets', repo_type='dataset',
        revision='0b3ea86be5fe169d0fd036ae63d1070ec09e90f6',
        local_dir='/root/.cache/libero/assets', local_files_only=args.offline)
    records.append(dict(repo_id='lerobot/libero-assets', repo_type='dataset',
        revision='0b3ea86be5fe169d0fd036ae63d1070ec09e90f6', path=asset_path))
    # 固定revisionで取得したtokenizerを採用コードのrepo名指定からも解決する。
    from transformers import AutoProcessor
    AutoProcessor.from_pretrained(sources[1]['repo_id'], local_files_only=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(offline=args.offline, sources=records), indent=2), encoding='utf-8')
    print('モデル・標準アセットの固定revision取得を確認しました')


if __name__ == '__main__':
    main()
