# 全10条件の元録画と段階時刻

時刻はsim秒、logstep nの実行後は(n+1)/20秒。各試行の初期画像は動画frame0。新規編集動画ではない。

## new_leaf_00：なしだけ成功
- なし：[元動画](holdout_comparison/trials/episode_07/rollout.mp4)。両指接触6.55秒、50mm8.50秒、40step保持10.45秒、開放・収容開始27.10秒、終了38.4秒。分類：placement_success。
- あり：[元動画](holdout_comparison/trials/episode_06/rollout.mp4)。両指接触10.35秒、50mm未達、40step保持未達、開放・収容開始未達、終了45.0秒。分類：bilateral_contact_without_50mm_lift。

## new_leaf_01：両失敗
- なし：[元動画](holdout_comparison/trials/episode_00/rollout.mp4)。両指接触7.05秒、50mm11.90秒、40step保持13.85秒、開放・収容開始42.85秒、終了45.0秒。分類：tray_hold_less_than_2seconds。
- あり：[元動画](holdout_comparison/trials/episode_01/rollout.mp4)。両指接触未達、50mm未達、40step保持未達、開放・収容開始未達、終了45.0秒。分類：approach。

## new_leaf_02：ありだけ成功
- なし：[元動画](holdout_comparison/trials/episode_05/rollout.mp4)。両指接触7.40秒、50mm8.85秒、40step保持10.80秒、開放・収容開始未達、終了45.0秒。分類：release。
- あり：[元動画](holdout_comparison/trials/episode_04/rollout.mp4)。両指接触9.30秒、50mm11.15秒、40step保持13.10秒、開放・収容開始35.45秒、終了38.25秒。分類：placement_success。

## new_leaf_03：なしだけ成功
- なし：[元動画](holdout_comparison/trials/episode_13/rollout.mp4)。両指接触5.90秒、50mm7.45秒、40step保持9.40秒、開放・収容開始18.80秒、終了20.9秒。分類：placement_success。
- あり：[元動画](holdout_comparison/trials/episode_12/rollout.mp4)。両指接触9.25秒、50mm未達、40step保持未達、開放・収容開始未達、終了45.0秒。分類：bilateral_contact_without_50mm_lift。

## new_leaf_04：なしだけ成功
- なし：[元動画](holdout_comparison/trials/episode_02/rollout.mp4)。両指接触10.50秒、50mm14.30秒、40step保持16.25秒、開放・収容開始35.05秒、終了39.2秒。分類：placement_success。
- あり：[元動画](holdout_comparison/trials/episode_03/rollout.mp4)。両指接触未達、50mm未達、40step保持未達、開放・収容開始未達、終了45.0秒。分類：grasp_alignment。

## new_leaf_05：両失敗
- なし：[元動画](holdout_comparison/trials/episode_08/rollout.mp4)。両指接触6.40秒、50mm8.50秒、40step保持10.45秒、開放・収容開始未達、終了45.0秒。分類：tray_approach_or_lowering。
- あり：[元動画](holdout_comparison/trials/episode_09/rollout.mp4)。両指接触9.80秒、50mm未達、40step保持未達、開放・収容開始未達、終了45.0秒。分類：bilateral_contact_without_50mm_lift。

## new_leaf_06：ありだけ成功
- なし：[元動画](holdout_comparison/trials/episode_10/rollout.mp4)。両指接触6.90秒、50mm未達、40step保持未達、開放・収容開始未達、終了45.0秒。分類：bilateral_contact_without_50mm_lift。
- あり：[元動画](holdout_comparison/trials/episode_11/rollout.mp4)。両指接触9.15秒、50mm11.10秒、40step保持13.05秒、開放・収容開始32.45秒、終了34.75秒。分類：placement_success。

## new_leaf_07：両成功
- なし：[元動画](holdout_comparison/trials/episode_15/rollout.mp4)。両指接触6.45秒、50mm7.80秒、40step保持9.75秒、開放・収容開始17.70秒、終了19.65秒。分類：placement_success。
- あり：[元動画](holdout_comparison/trials/episode_14/rollout.mp4)。両指接触8.65秒、50mm10.15秒、40step保持12.10秒、開放・収容開始28.40秒、終了30.35秒。分類：placement_success。

## new_leaf_08：両失敗
- なし：[元動画](holdout_comparison/trials/episode_16/rollout.mp4)。両指接触6.05秒、50mm9.45秒、40step保持未達、開放・収容開始未達、終了45.0秒。分類：lift_not_held_2seconds。
- あり：[元動画](holdout_comparison/trials/episode_17/rollout.mp4)。両指接触9.10秒、50mm10.70秒、40step保持12.65秒、開放・収容開始未達、終了45.0秒。分類：release。

## new_leaf_09：ありだけ成功
- なし：[元動画](holdout_comparison/trials/episode_19/rollout.mp4)。両指接触6.55秒、50mm11.35秒、40step保持13.30秒、開放・収容開始32.80秒、終了45.0秒。分類：tray_hold_less_than_2seconds。
- あり：[元動画](holdout_comparison/trials/episode_18/rollout.mp4)。両指接触10.30秒、50mm11.80秒、40step保持13.75秒、開放・収容開始26.35秒、終了30.65秒。分類：placement_success。
