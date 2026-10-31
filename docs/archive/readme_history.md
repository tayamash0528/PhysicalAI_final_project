<!-- fixed_leaf_holdout_20261031_1145_begin -->
最新最終検証：既存の葉5条件でトレー収容成功2/5→4/5を確認済み。採用版の重み・chunk10・観察・物理・判定を変えず、学習・調整・過去評価に未使用と監査した新10配置を両方式20試行評価した結果、収容は4/10→4/10で増加を再現しなかった。50mm以上の両指40step保持は8/10→5/10。既存の改善と新規検証を別集計し、全結果を保存。
[今回の最終報告](evaluation/relocated_apple/RESULTS_REPORT.md)・[README/再現方法](evaluation/relocated_apple/README.md)・[新20試行CSV](evaluation/relocated_apple/holdout_comparison/results.csv)・[全動画と段階時刻](evaluation/relocated_apple/VIDEO_GUIDE.md)。固定評価・後処理は12:26 JSTまでに終了コード0で完了。既存採用版/20試行は変更していない。以下は過去の履歴。
<!-- fixed_leaf_holdout_20261031_1145_end -->

<!-- reobservation_20261031_0925_begin -->
最新記録（2026-10-31）：固定20試行を完了・exit0。旧C＋chunk10、遮蔽なし配置は両5/5、視覚葉ありはなし2/5・あり4/5。50mm持上げ＋両指2秒保持は全群4/5。葉ありleaf03では再観察後の把持が悪化し、全条件で操作を崩さない目標は未達。実画像では観察後に遮蔽軽減するが、なし側も同時刻にリンゴが見える。視覚だけの因果効果は未分離。以下の旧結果とは別実験。
[今回の報告・再現手順](evaluation/initial/README.md)・[正式CSV](evaluation/initial/main_comparison/results.csv)・[素材ガイド](evaluation/initial/VIDEO_GUIDE.md)。34録画を全フレーム検査。比較後の追加調整・学習は行わず、PDF・提出動画編集はユーザー担当。下記は過去の履歴。
<!-- reobservation_20261031_0925_end -->

<!-- c10_restore_20261031_0828_begin -->
2026-10-31 環境再現確認：Docker・GPU・保存先は正常。旧重みC＋chunk10で過去の成功配置を1回だけ実行し、549stepで配置・開放・2秒保持に成功、終了コード0。過去の成功action列と完全一致しました。今回分は性能集計と分離しています。[採用候補の実行コマンド・設定・動画・CSV](verification/20261031_0828_c10_restore/README.md)。以前のDocker起動障害は、その後の通常起動と今回の実行で解消を確認。以下の過去記録・性能集計は変更していません。
<!-- c10_restore_20261031_0828_end -->

<!-- stability_20261031_0349_begin -->
最新記録: 2026-10-31の改善作業は[improvements/20261031_0349/README.md](improvements/20261031_0349/README.md)。**目標未達**。clearは初回固定seed4/5、同じ配置の別seedは4/5。再観察後の安定配置は未確立。追加学習3構成と全検証を保存し、新規本比較20試行は未実施です。自動で続行する処理はありません。PDF・提出動画編集は作成していません。
<!-- stability_20261031_0349_end -->

# 再観察付き果実選別ロボットの検証

**2026-10-31記録・改善実験終了:** 新規予約配置の20試行は、再観察なし3/10・あり2/10で改善未確認。遮蔽なし両1/5、視覚遮蔽ありはなし2/5・あり1/5。[最終報告](improvements/20261030_2101/REPORT.md)、[README・再現手順](improvements/20261030_2101/README.md)、[全構成41試行CSV](improvements/20261030_2101/all_vla_trials.csv)。72録画を全フレーム検査し、ローカル素材ZIPを作成。PDFと提出動画の編集はユーザー担当。以下は以前の履歴を含む。

既存のGazebo認識実験を保存し、独立したCUDA/LeRobot/LIBERO環境でリンゴのVLA配置を検証するプロジェクトです。
2026-10-30の最新証拠は [夜間実行の再現手順](overnight/20261030_0220/REPRODUCE.md)、[全VLA診断CSV](overnight/20261030_0220/deliverables/all_vla_trials.csv)、[実測結果JSON](overnight/20261030_0220/deliverables/summary.json) を参照してください。

学習した物理初期状態を復元したC2000は、実VLAの行動で配置・開放・2秒保持が3/3成功。未使用配置は0/2だったため、評価配置を除外して教師12配置を収集し、追加学習と閉ループ評価を実行しています。最終結果は上記CSVと `STATUS.md` に追記します。
優先順位はリンゴのVLA配置、未使用複数配置、自動再観察、同条件20試行の順。梨・混在・洗浄・別VLAは保留。教師制御の成功とVLAの成功、Gazebo認識比較と操作比較を分けます。

## 実行入口 (Windows PowerShell / Docker Desktop Linux)

```powershell
.\start.ps1 -Build
.\demo.ps1 -Episodes 1
```

初回はCUDA依存関係、学習済み重み、LIBEROアセットを取得します。GPU付き新規コンテナだけを使用し、既存ROS環境にはインストールしません。
Dockerイメージは `fruit-vla:20261029`、モデルキャッシュは本フォルダー内の `cache/` に保存します。

ソース取得用:

```powershell
$env:GIT_LFS_SKIP_SMUDGE='1'
git clone https://github.com/huggingface/lerobot.git vendor/lerobot
git -C vendor/lerobot checkout 89cc0a809477e8425c9aa31a561a8f293e76a25c
```

`scripts/run_rollout.py` は公式のSmolVLAPolicy、LIBERO環境アダプター、前処理・後処理を使用します。
2カメラ画像と8次元状態、指示から出力した7次元actionを、正規化解除後に[-1,1]へ制限し、20Hzのシミュレーターへ送ります。
runnerのデフォルトはチェックポイントの `n_action_steps=1`。動作確認済みの `demo.ps1` は10を明示します。1の失敗1試行、10の成功3試行を保存しました。実時間20Hzで推論できることを意味しません。

## 証拠と採点

各試行フォルダーに初期sim state、seed、入力画像、action全件JSONL、評価専用位置ログ、MP4、結果JSONを保存します。
正解位置は採点専用で、観測前処理やVLAへ渡しません。ネイティブLIBERO成功と果実配置成功を区別します。

リンゴ1個の試験:

```powershell
docker run --rm --gpus all --shm-size 2g --mount "type=bind,source=$PWD,target=/workspace" fruit-vla:20261029 python scripts/run_rollout.py --fruit-task apple_single --episodes 1 --out results/apple_pilot
```

果実用の成功条件は、果実メッシュ全体のXY投影が容器の内側にあり、底面付近に支持され、開いたグリッパーで2秒連続して留まることです。
リンゴの衝突形状は楕円体の近似で、果肉変形・損傷はモデル化していません。
`python -m unittest discover -s tests -v` で採点境界と連続保持を検証できます。旧実行版v1は60mm超開口、今回の実操作ではv2（開放action＋75mm以上の開口＋40step保持）を使用しています。旧6有効試行はv1で保持0step。旧結果と今回の修正後結果を分け、実行版は各manifestへ保存します。

## 段階と比較

1. A: 元の対応タスクをVLAで完了し、動画とログで確認する。
2. B: リンゴ1個の学習配置を再現し、未使用複数配置で操作を確認する。
3. C: 遮蔽からの自動追加観察と、追加観察省略の分岐を検証する。
4. D: 遮蔽なし5配置、あり5配置を固定し、同じモデル等で2方式・計20試行以上を実行する。

前段階が未達の場合、後段階を完了扱いにしません。旧Gazeboの13/18対18/18はリンゴ認識数の比較で、VLA選別・配置率ではありません。
認識候補はGrounding DINO tiny。最初の `an apple. a pear.` では複合ラベルが発生し、`apple. pear.` とクラス別token score・マージン判定へ修正しました。リンゴ同一配置の2画像では正分類。和梨での精度は未検証です。

## 既存成果の保存

`evidence/checkpoint.json` に保存場所があります。191ファイルについてSHA-256一致を確認済み。
Dockerイメージ `cultivation-checkpoint:pre-vla-20261029` は既存コンテナのファイルシステムと設定のスナップショットです。
bind mountの元ファイルは別途ファイルバックアップに保存しています。既存コンテナ自体は変更していません。

## 公開と提出

公開前にユーザーによる確認が必要です。ローカルではソース、通知、PDF案、動画素材を整理します。
モデル重み、キャッシュ、個人情報を含むローカル実行パスは公開用アーカイブから除外します。
公開GitHub URL、YouTube URL、最終提出はローカル作成の完了とは別の項目です。

## 参考

- LeRobot: https://github.com/huggingface/lerobot (Apache-2.0)
- LIBERO説明: https://huggingface.co/docs/lerobot/libero
- SmolVLA重み: https://huggingface.co/HuggingFaceVLA/smolvla_libero (Apache-2.0)
- 認識器: https://huggingface.co/IDEA-Research/grounding-dino-tiny (Apache-2.0)
- リンゴモデルと他の依存関係: `THIRD_PARTY_NOTICES.md`
