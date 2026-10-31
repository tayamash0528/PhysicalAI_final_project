# 公開用コピーの確認

名称と参照を更新し、配布ZIP・内容SHA・初期状態・LOCK・既知デモの引数経路・構文・リンク・登録対象を確認した。VLA操作の再実行はしていない。

過去のDocker構築・既知配置の実行は既存キャッシュを使用した別の確認であり、新しい公開パスで空環境から実行した証明ではない。[過去の検証記録](archive/publication_validation_history.md)。

認証済みRelease取得の検査記録はmetadata/github_release_verification.json。Public化後の未認証取得は別途必要。[名称対応表](path_mapping.md)／[再現手順](reproduction.md)／[提出前の残作業](submission_pending.md)。

別cloneでPrivate Releaseのモデル・アセットをgh認証で取得し、ZIP CRC・ZIP全体と内容のSHA・配置後SHA・固定条件の検査を通過した。metadata/github_release_verification.jsonに保存。動画MP4はGit対象外。公開準備時にはPDFの追記ページを画像として確認した。この過去の確認記録はmetadata/pdf_validation.jsonに保持する。

## 提出資料と実演動画の案内の更新

説明資料はOmniCampusへ別途提出する方針に変更し、docs/project_report.pdfをGitの追跡から外した。ローカルのPDF本文は変更・削除せず、このファイルだけを.gitignoreで除外する。過去のコミットと当時の作業記録は保持する。

READMEの概要直後に[実演動画（YouTube・2分28秒）](https://youtu.be/uYTpWKR6QEs)を掲載した。限定公開はユーザー申告による。YouTubeの取得はこの環境では失敗したため、リンク先の取得・再生を確認済みとはしていない。

現行のGit同梱物一覧はdocs/publication_files.json、提出先と動画案内の現行メタデータはmetadata/submission_artifacts.jsonを参照。以前の監査JSONと出典・ハッシュ対応表は、作成時点の記録であり現在の収録物一覧とは区別する。
