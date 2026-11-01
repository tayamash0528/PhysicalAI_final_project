# v1.0.0の配布

[Release](https://github.com/tayamash0528/PhysicalAI_final_project/releases/tag/v1.0.0) は公開されており、認証なしで取得できる。重みZIPとアセットZIPは通常のGitコミットへ含めない。

|配布ファイル|内容|
|---|---|
|fruit_vla_model_v1.0.zip|継続学習1,250ステップ時点の差分重み、Apache-2.0原文、出典通知|
|fruit_vla_assets_v1.0.zip|採用リンゴmesh・XML・texture、トレー、素材manifest、出典通知|

ソースのルートで実行する。PublicのRelease取得にGitHubログインは不要。

```powershell
python tools/publication/prepare_publication.py install --release-dir cache/releases --download
```

上記はGitHub認証を使わず、公開URLから取得する。取得後、ZIP全体と内容ファイルごとの容量・SHA256・安全な相対パスを照合し、異なる既存ファイルは上書きしない。URLはrelease_urls.json、ハッシュはrelease_manifest.jsonに記録する。

2026-11-01に未認証状態での実取得・既存manifestとのSHA256照合を完了した。取得できない場合は、ネットワークとリポジトリ・Releaseの公開状態を確認する。従来のPrivate環境で取得する場合のみ、権限のあるアカウントで `gh auth login` を済ませ、上記コマンドへ `--github-auth` を追加する。

ベースモデル・processor・LIBERO標準アセット・依存ライブラリは同梱していない。固定revisionと取得方法はreproduction.mdに記載する。元YCBアセットと採用変換済みアセットは同一ファイルではないため、採用版の再現には本アセットZIPを使う。

## 公開・未認証取得の確認（2026-11-01）

- 認証ヘッダー・Cookieを付けずにGitHub公開APIへアクセスし、リポジトリの `private=false` / `visibility=public` と、v1.0.0 Releaseの `draft=false`・公開日時を確認した。
- Gitのcredential helper・askpass・追加HTTPヘッダーを無効にしてHTTPSでcloneし、mainの `6d1734f39ecdbd37a39121689dfe8b52de28549b` を取得した。
- `urllib.request` で `release_urls.json` の公開URLから両ZIPを新規取得した。GitHub CLIやGitHub認証は使用していない。ZIP全体に加え、内部ファイル全10件の相対パス・容量・SHA256を既存の `release_manifest.json` と照合し、すべて一致した。検証はZIPを読み取って行い、実行環境への配置はしていない。

|配布ファイル|取得容量（bytes）|確認したZIPのSHA256|内部ファイル|
|---|---:|---|---:|
|fruit_vla_model_v1.0.zip|360492727|`93d8776074181e0e219a0f2f65477105162681189dda3c1ab486df27a1d734bb`|3件一致|
|fruit_vla_assets_v1.0.zip|736906|`99eba7c9e78b186ee781bf1dba88d2aa526f20819aea08936ecf76c9a58419c7`|7件一致|

この確認は公開状態・未認証clone・配布ZIPの取得と内容照合まで。Docker構築、上流依存・ベースモデルの取得、学習、デモ、比較実験、空キャッシュの新規PCでの全工程再現は実施していない。過去のキャッシュ利用による実行確認とは別の記録である。
