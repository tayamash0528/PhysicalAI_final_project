FROM python:3.12-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 \
    MUJOCO_GL=egl PYOPENGL_PLATFORM=egl HF_HOME=/workspace/cache/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1 TOKENIZERS_PARALLELISM=false \
    NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential ffmpeg libegl1 libgl1 libgles2 libglib2.0-0 libosmesa6 libx11-6 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system \
    torch==2.7.1 torchvision==0.22.1 --index-url https://pypi.org/simple
COPY vendor/lerobot/pyproject.toml vendor/lerobot/setup.py vendor/lerobot/README.md vendor/lerobot/LICENSE /opt/lerobot/
COPY vendor/lerobot/src /opt/lerobot/src
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system 'cmake>=3.29,<4'
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system '/opt/lerobot[smolvla,libero,evaluation]' 'imageio[ffmpeg]' matplotlib 'cmake<4'
WORKDIR /workspace
CMD ["python", "tools/publication/run_known_demo.py", "--help"]
