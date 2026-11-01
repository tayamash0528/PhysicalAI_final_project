# 公開用コピーの確認

名称と参照を更新し、配布ZIP・内容SHA・初期状態・LOCK・既知デモの引数経路・構文・リンク・登録対象を確認した。VLA操作の再実行はしていない。

過去のDocker構築・既知配置の実行は既存キャッシュを使用した別の確認であり、新しい公開パスで空環境から実行した証明ではない。[過去の検証記録](archive/publication_validation_history.md)。

認証済みRelease取得の検査記録はmetadata/github_release_verification.json。Public化後の未認証取得は2026-11-01に確認済み。詳細は[配布手順の確認記録](distribution.md#公開未認証取得の確認2026-11-01)を参照。[名称対応表](path_mapping.md)／[再現手順](reproduction.md)／[提出前の残作業](submission_pending.md)。

別cloneでPrivate Releaseのモデル・アセットをgh認証で取得し、ZIP CRC・ZIP全体と内容のSHA・配置後SHA・固定条件の検査を通過した。metadata/github_release_verification.jsonに保存。動画MP4はGit対象外。公開準備時にはPDFの追記ページを画像として確認した。この過去の確認記録はmetadata/pdf_validation.jsonに保持する。

## 提出資料と実演動画の案内の更新（旧148秒版の当時の記録）

説明資料はOmniCampusへ別途提出する方針に変更し、docs/project_report.pdfをGitの追跡から外した。ローカルのPDF本文は変更・削除せず、このファイルだけを.gitignoreで除外する。過去のコミットと当時の作業記録は保持する。

READMEの概要直後に[実演動画（YouTube・2分28秒）](https://youtu.be/uYTpWKR6QEs)を掲載した。限定公開はユーザー申告による。YouTubeの取得はこの環境では失敗したため、リンク先の取得・再生を確認済みとはしていない。

現行のGit同梱物一覧はdocs/publication_files.json、提出先と動画案内の現行メタデータはmetadata/submission_artifacts.jsonを参照。以前の監査JSONと出典・ハッシュ対応表は、作成時点の記録であり現在の収録物一覧とは区別する。


## 現行動画への切替確認（2026-11-02）

[正式な実演動画（148秒）](https://youtu.be/Gy2tz8IkIt8)へ更新した。タイトル`PAI最終課題_82444`はYouTube oEmbedで取得したメタデータと一致。本編再生と公開／限定公開の区分は未確認。旧URLの上記記録は当時の事実として保持する。

字幕は文章修正版の最終MP4に対応する30件へ更新。本文と時刻を編集定義・焼込み用ASSと照合し、ASS時刻の最大0.005秒の丸め以外は一致する。最終MP4のSHA256は`31a2c6c59676cdfd264196f3c30c2f92446f3fc7b44c253af61cb184007ed11f`。保存済みの修正版検証記録で全編デコード・表示・同期・数値の確認をしており、この切替作業では動画を再編集・再出力していない。

現行情報はmedia/provenance.jsonとmedia/video_validation.json。旧148秒版の検証はmetadata/video_history/summary_148.jsonへ分離して保持した。提出PDFはユーザー添付の確認済み8ページ版を正本とし、動画URLとリンク先のみ更新。本文・図・数値・参考文献・引用番号の不変をmetadata/submission_pdf_validation.jsonへ記録し、PDF本体はGitへ含めない。
