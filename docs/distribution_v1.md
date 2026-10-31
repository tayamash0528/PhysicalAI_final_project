# v1.0.0の配布

[Release](https://github.com/tayamash0528/PhysicalAI_final_project/releases/tag/v1.0.0) はPrivateのため認証が必要。重みZIPとアセットZIPは通常のGitコミットへ含めない。

|配布ファイル|内容|
|---|---|
|fruit_vla_model_v1.0.zip|継続学習1,250ステップ時点の差分重み、Apache-2.0原文、出典通知|
|fruit_vla_assets_v1.0.zip|採用リンゴmesh・XML・texture、トレー、素材manifest、出典通知|

権限のあるアカウントで `gh auth login` した後、ソースのルートで実行する。

```powershell
python tools/publication/prepare_publication.py install --release-dir cache/releases --download --github-auth
```

`gh` が保持する認証を使用する。トークン値をコマンド引数やログへ出さない。取得後、ZIP全体と内容ファイルごとの容量・SHA256・安全な相対パスを照合し、異なる既存ファイルは上書きしない。URLはrelease_urls.json、ハッシュはrelease_manifest.jsonに記録する。

Public化後は未認証の取得検査を別途行う。公開設定変更後の `--download`（`--github-auth`なし）はurllibで実URLから取得する経路で、今回は未認証状態の検証をしていない。

ベースモデル・processor・LIBERO標準アセット・依存ライブラリは同梱していない。固定revisionと取得方法はreproduction.mdに記載する。元YCBアセットと採用変換済みアセットは同一ファイルではないため、採用版の再現には本アセットZIPを使う。
