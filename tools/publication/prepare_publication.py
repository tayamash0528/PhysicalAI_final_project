"""公開候補専用の取得・SHA検査・配置。採用コードや評価値は変更しない。"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
REVISION = '89cc0a809477e8425c9aa31a561a8f293e76a25c'


@contextmanager
def scratch():
    # Windowsの保護されたシステムTEMPを使わず、作業内で生成・除去する。
    parent = (ROOT / 'cache/publication_setup').resolve()
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        resolved = Path(temporary).resolve()
        if not resolved.is_relative_to(parent):
            raise ValueError('一時領域が作業ディレクトリ外です')
        yield resolved


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def install(release_dir, download=False, github_auth=False):
    manifest = json.loads((ROOT / 'release_manifest.json').read_text(encoding='utf-8'))
    urls = json.loads((ROOT / 'release_urls.json').read_text(encoding='utf-8'))
    release_dir.mkdir(parents=True, exist_ok=True)
    for bundle in manifest['bundles']:
        archive = release_dir / bundle['filename']
        if not archive.exists():
            url = urls.get(bundle['filename'])
            if not download or not url:
                raise RuntimeError(f"配布ZIPがありません。公開前は配布者から入手してください: {bundle['filename']}")
            if not url.startswith('https://'):
                raise ValueError('取得URLにはHTTPSが必要です')
            temporary = archive.with_suffix('.download')
            if github_auth:
                subprocess.run(['gh', 'release', 'download', 'v1.0.0', '--repo',
                    'tayamash0528/PhysicalAI_final_project', '--pattern', bundle['filename'],
                    '--output', str(temporary)], check=True)
            else:
                urllib.request.urlretrieve(url, temporary)
            if sha(temporary) != bundle['sha256']:
                raise ValueError('ダウンロードした配布ZIPのSHA256が一致しません')
            temporary.replace(archive)
        if sha(archive) != bundle['sha256']:
            raise ValueError(f"配布ZIPのSHA256が一致しません: {archive.name}")
        expected = {entry['path']: entry for entry in bundle['files']}
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ValueError('ZIP内容が配布一覧と一致しません')
            # 全ファイルを検証してから配置する。既存の異なるファイルは上書きしない。
            with scratch() as temporary:
                unpacked = Path(temporary)
                for name in names:
                    relative = PurePosixPath(name)
                    if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
                        raise ValueError('ZIP内の不正な相対パス')
                    entry = expected[name]
                    if zipped.getinfo(name).file_size != entry['bytes']:
                        raise ValueError(f'容量不一致: {name}')
                    destination = unpacked.joinpath(*relative.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(name) as src, destination.open('wb') as dst:
                        shutil.copyfileobj(src, dst)
                    if sha(destination) != entry['sha256']:
                        raise ValueError(f'SHA256不一致: {name}')
                    target = ROOT.joinpath(*relative.parts)
                    if target.exists() and sha(target) != entry['sha256']:
                        raise FileExistsError(f'異なる既存ファイルは上書きしません: {name}')
                for name in names:
                    target = ROOT / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        shutil.copy2(unpacked / name, target)
        print(f"配布ZIPの検証・配置完了: {archive.name}")


def upstream(local_source=None):
    target = ROOT / 'vendor/lerobot'
    if target.exists():
        raise FileExistsError('vendor/lerobotが既にあります。既存環境は変更しません')
    with scratch() as temporary:
        source = local_source or Path(temporary) / 'lerobot'
        if local_source is None:
            subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout',
                            'https://github.com/huggingface/lerobot.git', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'checkout', REVISION], check=True,
                           env=dict(__import__('os').environ, GIT_LFS_SKIP_SMUDGE='1'))
        revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != REVISION:
            raise ValueError('上流revisionが一致しません')
        target.mkdir(parents=True)
        for name in ('src', 'pyproject.toml', 'setup.py', 'README.md', 'LICENSE'):
            origin = source / name
            if origin.is_dir():
                shutil.copytree(origin, target / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            else:
                shutil.copy2(origin, target / name)
        print(f'LeRobot固定ソースを配置: {REVISION}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    install_parser = commands.add_parser('install')
    install_parser.add_argument('--release-dir', required=True, type=Path)
    install_parser.add_argument('--download', action='store_true')
    install_parser.add_argument('--github-auth', action='store_true', help='Private Releaseをgh認証で取得する')
    upstream_parser = commands.add_parser('upstream')
    upstream_parser.add_argument('--local-source', type=Path)
    args = parser.parse_args()
    if args.command == 'install':
        install(args.release_dir, args.download, args.github_auth)
    else:
        upstream(args.local_source)


if __name__ == '__main__':
    main()
