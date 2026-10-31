# 出典・第三者ライセンス通知

## 自作コードと配布物

自作コードは[MIT License](LICENSE)。C1250追加学習差分はベースモデルに合わせApache-2.0で配布する。重みZIPへApache-2.0原文と本通知を含める。YCB由来のリンゴ素材はCC BY 4.0であり、コードのMITライセンスへ変更しない。

## LeRobot・SmolVLA

- LeRobot: https://github.com/huggingface/lerobot
- 採用revision: `89cc0a809477e8425c9aa31a561a8f293e76a25c`
- Copyright Hugging Face、Apache License 2.0。上流の著作権表示・ライセンスを維持する。公開ソースZIPには上流全体を同梱せず、固定revisionの取得スクリプトを含める。
- ベースモデル: https://huggingface.co/HuggingFaceVLA/smolvla_libero
- 採用revision: `6721902bc4d61e50a3bfdb11dfb4cb626f05d102`、Apache-2.0。巨大なベース重みは上流から取得する。
- C1250はベースモデル用の追加学習パラメーター差分で、単独では推論できない。既存の著作権・出典を保持する。配布候補は`fruit_vla_model_v1.0.zip`。公開URLは未設定。
- processor: `HuggingFaceTB/SmolVLM2-500M-Instruct`、revision `7b375e1b73b11138ff12fe22c8f2822d8fe03467`。公開ページの名称変更とは区別し、採用名と固定revisionを使う。

## LIBERO・robosuite・MuJoCo

- LIBERO: https://github.com/huggingface/LIBERO （元プロジェクト: https://github.com/Lifelong-Robot-Learning/LIBERO ）、コードはMIT。
- hf-libero 0.1.4の標準アセットは`lerobot/libero-assets`から取得する。本アセットZIPには再同梱しない。素材ごとの上流通知も適用される。
- robosuite: https://github.com/ARISE-Initiative/robosuite 、MIT。
- MuJoCo: https://github.com/google-deepmind/mujoco 、Apache-2.0。
- それぞれの上流ライセンスを保持する。

## YCBのリンゴ形状・テクスチャ

- 対象: YCB Object and Model Set、013_apple、Google 16k scan。
- 作成・提供: Berk C. Calli, Arjun Singh, Aaron Walsman, Siddhartha Srinivasa, Pieter Abbeel, Aaron M. Dollar / YCBプロジェクト。
- 出典: https://ycb-benchmarks.s3.amazonaws.com/index.html
- 元アーカイブ: https://ycb-benchmarks.s3.amazonaws.com/data/google/013_apple_google_16k.tgz
- ライセンス: Creative Commons Attribution 4.0 International (CC BY 4.0)、https://creativecommons.org/licenses/by/4.0/
- 引用: Berk Calli et al., The YCB Object and Model Set: Towards Common Benchmarks for Manipulation Research, ICAR 2015.
- 加工履歴: 先行作業でOBJをCOLLADAへ変換、XY中心化・底面z=0へ移動、textureを最大1024ピクセルへ縮小。本プロジェクトで保存COLLADAをOBJへ変換し、全軸を中心化した。保存textureを維持し、衝突形状には近似楕円体を使用した。
- 派生`apple.obj`と`texture.png`を採用バイト列のままアセットZIPへ含める。元アーカイブからの再変換では同一SHAを保証しない。
- 原著者・提供者による本システムへの推奨を意味しない。

## その他の依存・履歴

PyTorch（BSD系）、torchvision（BSD）、transformers（Apache-2.0）、NumPy（BSD）、Pillow（HPND）、OpenCV（Apache-2.0）、imageio（BSD）、FFmpeg（ビルドによるLGPL/GPL）、Matplotlib（PSF系）などを利用する。実測依存一覧はrequirements.lockと比較時freezeに保存し、個別の上流ライセンスが適用される。これらは構築時に取得し、バイナリ配布物へ同梱しない。

過去の認識検証で使ったGrounding DINO（https://huggingface.co/IDEA-Research/grounding-dino-tiny 、Apache-2.0）は、採用VLAの再観察判断には使用しない。過去のPDF・動画のフォントバイナリも配布候補へ含めない。
