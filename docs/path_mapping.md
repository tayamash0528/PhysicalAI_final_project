# 公開用の名前と元成果の対応

主な配布・閲覧名は次のとおり。元MP4はYouTube用としてローカルに保持し、Gitへは登録しない。

|元成果|公開・提出用の名前|
|---|---|
|fruit_vla_C1250.zip|Release: fruit_vla_model_v1.0.zip|
|fruit_vla_adopted_assets.zip|Release: fruit_vla_assets_v1.0.zip|
|experiments/20261031_0925_reobservation/main_comparison/results.csv|results/initial_comparison.csv|
|experiments/20261031_1145_leaf_holdout/holdout_comparison/results.csv|results/relocated_apple_comparison.csv|
|diagnostics/20261031_1814_leaf_motion/factorial_diagnostic.csv|results/occlusion_motion_diagnostic.csv|
|submission/video/summary_148/fruit_vla_148s_summary_ja.mp4|過去の148秒版：ローカルmedia/fruit_vla_demo.mp4に保管（Git対象外）|
|submission/video/wording_revision_148/fruit_vla_demo_final_ja.mp4|現行採用動画：YouTube（MP4はGit対象外）|
|fruit_vla_report_DRAFT.pdf|ローカル保持のdocs/project_report.pdf（Git対象外／説明資料はOmniCampusへ別途提出）|

元成果はローカルで保持している。公開用コピーのパスのみ変更し、評価の数値・CSV内の条件IDは変更していない。CSV内の動画・画像パスは実験時の出典であり、公開コピーの実在パスとは区別する。

|実験時の名前|公開用の名前|
|---|---|
|`experiments/20261031_0925_reobservation`|`evaluation/initial`|
|`experiments/20261031_1145_leaf_holdout`|`evaluation/relocated_apple`|
|`overnight/20261030_0220/config_c_multi12_b4/checkpoints/step_001250`|`models/fruit_vla`|
|`overnight/20261030_0220/config_c_multi12_b4`|`training/continuation`|
|`overnight/20261030_0220/config_c_compact`|`training/initial`|
|`overnight/20261030_0220/compact_teacher`|`training/initial_demonstration`|
|`overnight/20261030_0220/teachers_12`|`training/demonstrations`|
|`diagnostics/20261029_2356/teacher_02`|`training/seed_state`|
|`diagnostics/20261031_1814_leaf_motion`|`evaluation/occlusion_motion`|
|`docs/archive/README_before_github_20261031_145603.md`|`docs/archive/readme_history.md`|
|`final_confirmation`|`adoption_check`|
|`training_selected_C.diff`|`training_continuation.diff`|
|`fruit_vla_C1250.zip`|`fruit_vla_model_v1.0.zip`|
|`fruit_vla_adopted_assets.zip`|`fruit_vla_assets_v1.0.zip`|

採用重み本体のSHA256は変更していない。LOCKは公開用の相対パスと変更後のソースSHAに合わせたアダプター版であり、実験時のLOCKはmetadata/original_protocolsに保持した。全ファイルの旧名・新名・元SHAはmetadata/publication_path_map.jsonを参照。

現行の採用元はsubmission/video/wording_revision_148/fruit_vla_demo_final_ja.mp4。[正式な実演動画（YouTube）](https://youtu.be/Gy2tz8IkIt8)のタイトルはPAI最終課題_82444。タイトル情報を取得したが、本編再生と公開／限定公開の区分は未確認。media/fruit_vla_demo.mp4は過去の148秒版の保管用コピーで、今回上書きしていない。

説明資料はOmniCampusへ別途提出し、PDFはGitに同梱しない。docs/project_report.pdfは本文を変えずローカルに保持し、このファイルだけを.gitignoreで除外する。今回の変更前のコミットにはPDFが残るが、過去の履歴は書き換えない。現行PDFの正式提出名は説明資料_PAI最終課題_tayamash.pdf（ユーザー確認済み）。提出PDFは別途ローカルに保存する。

診断CSVは個人ホスト絶対パスを除くため、video・log_directory・initial_fixed_rgb・initial_wrist_rgb・observation_end_wrist_rgb列だけをプロジェクト相対パスへ変更した。条件ID・成否・時刻・数値は元CSVと同一。最初と別配置のCSVはbyte一致。
