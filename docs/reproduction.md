# 準備・再現手順の詳細

## 1. 確認した範囲

公開候補のDockerfileと固定LeRobotソースから別タグ `fruit-vla:publication` を構築した。元の `fruit-vla:20261029` は保持した。Dockerの既存ビルドキャッシュを再利用した検証であり、空キャッシュから全依存を再取得した検証ではない。デモには既存のモデル・LIBEROアセットキャッシュも読み取り専用で再利用した。結果は[確認記録](readme_validation.md)に記載する。

環境はWindows＋Docker DesktopのLinuxコンテナ、NVIDIA RTX 4070 SUPER 12GB。ホスト側でGit・Python 3.10以上、コンテナ側でPython 3.12.16とNVIDIA GPUが必要。ドライバーとDockerのGPU連携が事前に必要であり、少ないVRAMやCPU推論は未検証。

## 2. コード・配布ファイルを準備

GitHubからcloneし、そのルートで実行する。Private中は権限のあるアカウントでgh auth loginを済ませる。[配布手順](distribution.md)と[全容量・SHA一覧](../release_manifest.json)を参照。

```powershell
python tools/publication/prepare_publication.py install --release-dir cache/releases --download --github-auth
python tools/publication/prepare_publication.py upstream
```

1行目はZIPと各ファイルのSHAを検査し、C1250と採用アセットを元の相対パスへ配置する。2行目は公開LeRobotをrevision `89cc0a809477e8425c9aa31a561a8f293e76a25c`に固定して取得する。既存vendorは上書きしない。今回の検証では取得済み上流チェックアウトを `upstream --local-source <既存上流フォルダー>` でコピーした。上流663ファイルはGitの固定revisionと内容一致しており、差分はない。第三者向けネットワークcloneの全工程は今回再実行していない。

C1250は `models/fruit_vla/expert_delta.safetensors`。同じ親フォルダーの5000step時点の差分とは区別する。教師軌道の再取得・再学習は不要。固定初期状態の小さなstate.npyはソースZIPに同梱する。

## 3. 別タグのDockerイメージを構築

```powershell
docker build --progress plain --pull=false -t fruit-vla:publication .
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }
```

これは今回実行した構築コマンド。元のDockerfileは変更していない。今回解決されたPythonベースイメージのdigestは `sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337`。既存キャッシュが使われ、主要install層もCACHEDだった。依存の実測一覧[requirements.lock](../requirements.lock)はDocker構築へ適用されていない。新規構築では依存解決・OSパッケージが変わる可能性があり、完全なオフライン再構築は保証しない。

主要依存とGPUを検査するコマンドは次のとおり（今回実行済み）。

```powershell
docker run --rm --gpus all --mount "type=bind,source=$((Get-Location).Path),target=/workspace" fruit-vla:publication python tools/publication/check_runtime.py
```

実測主要版はPython 3.12.16、PyTorch 2.7.1、torchvision 0.22.1、LeRobot 0.6.2、hf-libero 0.1.4、transformers 5.5.4、MuJoCo 3.8.1。これらの版とGPU利用可否を構築後に確認する。

## 4. 固定モデル・標準アセットを用意

| 用途 | repo | revision |
|---|---|---|
| ベースVLA | HuggingFaceVLA/smolvla_libero | 6721902bc4d61e50a3bfdb11dfb4cb626f05d102 |
| processor/tokenizer | HuggingFaceTB/SmolVLM2-500M-Instruct | 7b375e1b73b11138ff12fe22c8f2822d8fe03467 |
| LIBERO標準アセット | lerobot/libero-assets（dataset） | 0b3ea86be5fe169d0fd036ae63d1070ec09e90f6 |

processorの公開ページはSmolVLM2-500M-Video-Instructへリダイレクトされる。採用名を保持して固定revisionを取得し、そのローカルrefs/mainも固定する。採用コードは変更しない。state/actionの正規化はベースモデルに同梱されたmean/stdを使用する。

```powershell
New-Item -ItemType Directory -Force -Path cache/huggingface, cache/libero_assets | Out-Null
$projectDir = (Get-Location).Path
$mounts = @('--mount', "type=bind,source=$projectDir,target=/workspace",
            '--mount', "type=bind,source=$projectDir/cache/libero_assets,target=/root/.cache/libero")
$image = 'fruit-vla:publication'
docker run --rm @mounts $image python tools/publication/download_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime preparation failed' }
```

上記はネットワーク取得時の手順で、今回空キャッシュからのダウンロードは行っていない。今回確認したのは同じスクリプトの `--offline` モードで既存キャッシュを解決する経路。既存キャッシュを使う場合は、HFキャッシュを `/workspace/cache/huggingface`、LIBEROキャッシュを `/root/.cache/libero` へmountする。後者の直下にはassets/が必要。キャッシュに認証トークン等を含めて公開しない。

## 5. 既知配置のデモ1試行

```powershell
docker run --rm --gpus all --shm-size 2g -e HF_HUB_OFFLINE=1 @mounts $image python tools/publication/run_known_demo.py --out results/known_leaf02_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo failed; inspect saved logs' }
```

既存比較のleaf_02・再観察あり・seed8407を1件抽出する。C1250・採用ソース・アセットのSHAを照合し、chunk10、rgb_early_approach_v10、900step、telemetry、FP32追加学習パラメーター＋BF16推論で元のrun_rollout.pyを呼ぶ。新しい出力先を要求し、既存結果は上書きしない。設定・実行引数・終了コード・動画・action・評価・接触ログを保存する。このデモは性能評価へ加算しない。

今回の実行先は `results/publication_demo_1`。コンテナを `docker run -d --name fruit-vla-publication-20261031-demo ...` で起動し、対話終了に依存しない形で実行した。学習・主比較の再実行は行わない。

## 6. 固定比較を別出力へ再現する場合

既存20試行と新規配置20試行は別集計のまま保存する。この節の比較再実行は今回行っていない。実行する場合だけ、新規出力先へ条件をコピーする。初期state.npyは元の相対パスを維持する。

```powershell
$protocol = 'evaluation/initial/main_comparison'
# 新規配置: evaluation/relocated_apple/holdout_comparison
$out = 'results/fixed_comparison_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
New-Item -ItemType Directory -Path $out -ErrorAction Stop | Out-Null
foreach ($file in @('LOCK.json', 'episode_setups.json', 'evaluation_only_conditions.json')) {
    Copy-Item -LiteralPath (Join-Path $protocol $file) -Destination (Join-Path $out $file)
}
docker run --rm --gpus all --shm-size 2g -e HF_HUB_OFFLINE=1 @mounts $image python evaluation/initial/tools/run_protocol.py --root $out
docker run --rm @mounts $image python evaluation/initial/tools/analyze_three_stages.py --root $out --expect 20
```

元の正式CSV・集計JSON・試行別result.jsonは公開候補へ含める。生JSONL・入力画像・元動画は容量のため同梱せず、ローカル原本に保持する。既存CSVの参照先動画が公開ソースZIP内に存在するとは説明しない。

## 7. 今回の登録と残作業

GitHubとv1.0.0 Releaseに登録し、release_urls.jsonに実URLを設定する。Private中は認証済みで取得・SHA・ZIPを検査する。Public変更後の未認証取得、第三者の新規PC・空キャッシュでの全工程は未確認。今回は新しいVLA試行・学習・比較実験を開始していない。
