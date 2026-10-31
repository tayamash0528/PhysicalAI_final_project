# 学習データの公開範囲

採用モデルは、1軌道403フレームを起点に12軌道5,065フレームで継続学習し、1,250ステップ時点を採用した。後の不採用構成に使ったデータは混ぜない。

`training/` にはデータ構成・初期状態の小さな記録・学習結果・実行ソースを収録した。画像・action配列を含む大容量のteacher_episode.npzなどは配布していない。これらの未同梱パスは生成時の出典であり、cloneだけで存在するとは説明しない。

採用モデルによるデモには教師配列は不要。Releaseのモデル・アセット、固定ベースモデル、固定初期状態を使う。

見本生成の自作ソースは `scripts/diagnose_physical_grasp.py`、`scripts/collect_compact_teachers.py`、学習処理は `scripts/train_tiny_teacher.py` と `training/continuation/executed_training_source.py` に残す。正解位置は教師生成に使用するが、本番VLA入力・再観察判断へは渡さない。公開用パス整理後に再収集・再学習はしておらず、採用重みを再学習で完全再現する手順まで検証済みとはしない。
