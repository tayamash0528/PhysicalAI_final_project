# 再観察を組み込んだVLA果実回収システムの構築と評価

コードと採用重み・アセットをGitHubとReleaseで公開しています。

[GitHubリポジトリ](https://github.com/tayamash0528/PhysicalAI_final_project) ／ [配布Release v1.0.0](https://github.com/tayamash0528/PhysicalAI_final_project/releases/tag/v1.0.0)

葉で対象が見づらいとき、動く前にカメラで見直すことが果実回収に役立つかを調べた。LIBERO／MuJoCoのPandaアームで、**机上のリンゴ1個をトレーへ回収する動作**を構築した。枝からの切離し、種類の判別・仕分け、実農場実証は対象外である。

[実演動画（YouTube・2分28秒）](https://youtu.be/Gy2tz8IkIt8)

動画タイトルは`PAI最終課題_82444`（YouTubeメタデータで確認）。新動画の公開／限定公開の区分と本編再生は未確認。MP4はGitに含めない。説明資料はOmniCampusへ別途提出するため、PDFはこのリポジトリに同梱しない。

2026-11-01にリポジトリのPublic状態とv1.0.0 Releaseの公開を確認した。認証なしでcloneと両配布ZIPの取得・SHA256照合を完了しており、取得にGitHubへのログインは不要。

## 仕組みと自作部分

VLAは画像・言葉・ロボットの状態から次の動きを出すAI。公開SmolVLAを追加学習し、固定・手首の2画像、8次元の状態、言語指示から行動を生成する。

- **自作の判断・移動**：RGBの赤・緑の色規則で見直しの必要性を判断する。緑250画素以上、赤／（赤＋緑）0.75未満なら、手首の向きを保ち世界座標で（+20,+40,−10）mmの固定小移動を45ステップ行う。最適視点探索ではない。
- **SmolVLAによる操作**：更新した画像・状態を渡し、action queueをリセットして、つかむ・運ぶ・置く動きを出す。**再観察なし側も操作中に画像を更新する**。
- **自作の見本・学習・評価**：正解位置を使う教師制御で見本を作り、追加学習・収容判定・接触と高さの記録・同条件比較を実装した。正解位置・個数は本番VLAや再観察判断へ渡さない。教師制御の成功はVLA成績に含めない。

採用モデルは、1軌道403フレームで2,000ステップ学習した重みを起点に、12軌道5,065フレームで継続学習した**1,250ステップ時点**。実行設定は **`n_action_steps=10`**、予測長50、観察profile **`rgb_early_approach_v10`**。後の不採用データを本数に混ぜていない。[起点の記録](training/initial/result.json)／[採用チェックポイント](models/fruit_vla/checkpoint.json)／[データ構成](training/demonstrations/dataset_list.json)。

## 結果

「5条件」は、同じ作業台でリンゴの初期位置を5通り変えた条件。各条件で同じ初期状態・seed・重み・指示・物理・判定・総900ステップを使い、両方式を1回ずつ実行した。

|評価|再観察なし|再観察あり|
|---|---:|---:|
|最初の比較・葉なし5条件：トレー収容|5/5|5/5|
|最初の比較・葉あり5条件：トレー収容|2/5|4/5|
|別の未使用10配置・葉あり：トレー収容|4/10|4/10|
|同じ10配置：持ち上げ・両指保持|8/10|5/10|

**最初の葉あり5条件では収容成功数が増えたが、学習・調整に使っていない別の10配置では増加を再現できなかった。** 評価群は合算しない。移動は画像のほか姿勢・接近経路・開始時刻・残り操作予算も変えるため、視覚情報だけが改善原因とは断定しない。

収容は、果実meshのXY足跡がトレー内、底面が所定高さ、開放指令と指関節変位和75mm以上が40制御ステップ連続して成立する判定（20Hzで2秒相当）。実行版は `v2_open_command_and_75mm_gap_40_steps`。持ち上げ・両指保持は初期果実中心から50mm以上、両指同時接触を40ステップ保つ別指標。接触だけを把持成功と呼ばない。滑脱してトレーに入った例も含み、安定した把持搬送率とは区別する。

- [最初の比較CSV](results/initial_comparison.csv)／[集計](results/initial_comparison_summary.json)
- [置き場所変更の比較CSV](results/relocated_apple_comparison.csv)／[集計](results/relocated_apple_comparison_summary.json)
- [最終診断CSV](results/occlusion_motion_diagnostic.csv)／[診断報告](evaluation/occlusion_motion/DIAGNOSTIC_REPORT.md)
- [動画の日本語字幕](media/fruit_vla_demo_ja.srt)

最終診断は失敗分析のため事後選定した3配置。葉を消しても移動後に失敗する位置A、葉を消すと成功する位置B、全条件で成功する位置Cがあった。本比較とは別集計で、姿勢が唯一の原因などとは結論しない。

## 取得・実行

Windows＋Docker DesktopのLinuxコンテナ、GPU連携済みNVIDIA GPUを使用。確認環境はRTX 4070 SUPER 12GB。Python 3.12.16、PyTorch 2.7.1、LeRobot 0.6.2、robosuite 1.4.0、MuJoCo 3.8.1。20Hzはシミュレータ制御周波数で、実時間の推論速度ではない。

ホスト側にGitとPython 3.10以上を用意し、PowerShellで実行する。

```powershell
git clone https://github.com/tayamash0528/PhysicalAI_final_project.git
cd PhysicalAI_final_project
python tools/publication/prepare_publication.py install --release-dir cache/releases --download
python tools/publication/prepare_publication.py upstream
docker build --progress plain --pull=false -t fruit-vla:publication .
```

採用重みは通常のGitへ含めない。[fruit_vla_model_v1.0.zip](https://github.com/tayamash0528/PhysicalAI_final_project/releases/download/v1.0.0/fruit_vla_model_v1.0.zip) と [fruit_vla_assets_v1.0.zip](https://github.com/tayamash0528/PhysicalAI_final_project/releases/download/v1.0.0/fruit_vla_assets_v1.0.zip) を取得し、ZIPと各内容のSHA256を確認して配置する。[配布manifest](release_manifest.json)／[URL設定](release_urls.json)。2026-11-01に認証なしで両ZIPを取得し、ZIP全体と内部の全10ファイルが既存manifestの容量・SHA256に一致することを確認した。[取得確認の詳細](docs/distribution.md#公開未認証取得の確認2026-11-01)。

重み本体のSHA256：`67a1dd9044c21f4b13de96afca496099e02f9531b624879f151fc3996e991ac2`。配置先 `models/fruit_vla/expert_delta.safetensors`。ベースSmolVLAだけでは再現できない。

ベースモデルは `HuggingFaceVLA/smolvla_libero` revision **`6721902bc4d61e50a3bfdb11dfb4cb626f05d102`**。LeRobot revision `89cc0a809477e8425c9aa31a561a8f293e76a25c`。processorと標準アセットの固定revision、mount・取得・デモの全コマンドは[再現手順](docs/reproduction.md)に記載する。

```powershell
$projectDir = (Get-Location).Path
New-Item -ItemType Directory -Force cache/libero_assets | Out-Null
$mounts = @('--mount', "type=bind,source=$projectDir,target=/workspace",
            '--mount', "type=bind,source=$projectDir/cache/libero_assets,target=/root/.cache/libero")
$image = 'fruit-vla:publication'
docker run --rm @mounts $image python tools/publication/download_runtime.py
docker run --rm --gpus all --shm-size 2g -e HF_HUB_OFFLINE=1 @mounts $image python tools/publication/run_known_demo.py --out outputs/known_leaf02_demo
```

既存環境では別タグ構築・モデル読込・初期化・既知leaf02の1試行成功を確認済み。ただし既存ビルド・モデル・アセットキャッシュを使用した。今回の公開パス整理後はハッシュ・配置・実行入口の引数を検証し、VLA実行は追加していない。**空キャッシュの新規環境で全工程を再現した検証ではない**。[確認記録](docs/readme_validation.md)。`requirements.lock` は実測依存一覧で、Docker構築には直接適用していない。

## 主要ファイル・追跡可能性

|ファイル|役割|
|---|---|
|scripts/run_rollout.py|VLA推論・前後処理・環境実行・記録|
|scripts/active_observation.py|色の判断・観察移動・引継ぎ|
|scripts/occlusion_scene.py / fruit_objects.py|リンゴ・トレー・葉・シーン|
|scripts/placement_score.py / arm_telemetry.py|収容・接触・高さ・保持の判定|
|evaluation/initial/tools/run_protocol.py|固定条件の比較入口|
|evaluation/initial/tools/analyze_three_stages.py|段階別集計|
|evaluation/relocated_apple/tools/postprocess_holdout.py|別10配置の集計|
|tools/publication/|配布取得・SHA確認・環境準備・既知デモ|

[名称対応表](docs/path_mapping.md)／[ファイル別の旧名とSHA](metadata/publication_path_map.json)／[開発履歴](docs/development_history.md)。CSV内の素材パスは実験時の出典として保持している。大容量の元録画・生ログ・教師配列は同梱しない。固定初期状態、小容量の結果とメタデータは含める。

## 限界・出典

同じリンゴモデル・狭い作業範囲・到達可能なトレーでの検証。葉は衝突なしの板状近似で、枝や支持物を省略し、固定視点では果実が見える。色規則はこのシーン用で、未知作物・実農場への一般化を示さない。

自作コードはMIT、上流モデル・ライブラリ・素材には各権利者の条件が適用される。LeRobot／SmolVLA／MuJoCoはApache-2.0、LIBERO／robosuiteはMIT、YCBのリンゴ形状・textureはCC BY 4.0。全体へ単一ライセンスを上書きしていない。[第三者通知](THIRD_PARTY_NOTICES.md)／[ライセンス原文](licenses/Apache-2.0.txt)。

YouTubeの実演動画リンクは冒頭に掲載した。提出時にはログアウト状態でコード・Release・動画へアクセスできることを確認する。[提出前の残作業](docs/submission_pending.md)を参照。
