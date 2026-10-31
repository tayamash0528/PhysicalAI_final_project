# 録画素材ガイド

全試行は残し、成功例だけで性能を説明しない。動画は20Hz、時刻はシミュレーション時間。観察ありの葉では0〜2.25秒が観察専用移動。元動画内のsuccess表示はその時点の判定、contactsheet上部successは試行最終結果。

|条件|なし|あり|確認した違い|
|---|---|---|---|
|leaf02|[episode01・45秒](main_comparison/trials/episode_01/rollout.mp4)|[episode00・26.55秒](main_comparison/trials/episode_00/rollout.mp4)|接触のみ→持上げ保持・配置成功|
|leaf04|[episode15・45秒](main_comparison/trials/episode_15/rollout.mp4)|[episode14・39.75秒](main_comparison/trials/episode_14/rollout.mp4)|両方実把持、配置だけ改善|
|leaf03|[episode18・45秒](main_comparison/trials/episode_18/rollout.mp4)|[episode19・45秒](main_comparison/trials/episode_19/rollout.mp4)|なしは保持後24.25秒付近で落下、ありは接近失敗。悪化例を省かない|
|leaf00|[episode12・20.75秒](main_comparison/trials/episode_12/rollout.mp4)|[episode13・40.15秒](main_comparison/trials/episode_13/rollout.mp4)|両方配置成功、ありは遅い|
|leaf01|[episode17・25.25秒](main_comparison/trials/episode_17/rollout.mp4)|[episode16・35秒](main_comparison/trials/episode_16/rollout.mp4)|両方配置成功、ありは遅い|
|clear04|[episode07・19.05秒](main_comparison/trials/episode_07/rollout.mp4)|[episode06・19.05秒](main_comparison/trials/episode_06/rollout.mp4)|自動省略、全行動・入力画像一致、持上げ保持と配置成功|
|clear00|[episode05・16.15秒](main_comparison/trials/episode_05/rollout.mp4)|[episode04・16.15秒](main_comparison/trials/episode_04/rollout.mp4)|11.3秒付近で把持喪失→トレーに落下し配置成功。両指接触4.8秒、50mm以上の厳密保持は1秒のみ|

残りの遮蔽なしも含む全20試行と段階時刻は [正式CSV](main_comparison/results.csv)。[全34素材の一覧](materials/video_materials.csv)、`materials/*contact_sheet.png` に全成功・失敗を保存。

観察の主な図は [実画像5組](diagnostic_analysis/ACTUAL_RGB_leaf_5pairs.png)、[段階別の結果図](main_comparison/three_stage_analysis/figures/stages_comparison.png)。`three_stage_analysis/paired_images/` は全10条件の両方式を対応づける。各episodeの `reobservation/before_*`、実行した場合の `after_*`、両方式の `matched_time/frame_0045_*` が元の実画像。

葉非表示の `EVAL_ONLY_*` は制御に使っていない評価参照画像。動作後の復元画像は品質不合格であり、`observation_within_active` / `observation_matched45` の正規化proxy図は参考資料のみ。可視面積100%を示す図として使用しない。実画像では両方式とも同時刻45stepでリンゴが見えている。

全動画は完全decode済み。PDFと提出動画の編集は未実施。
