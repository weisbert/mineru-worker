# MinerU 显卡解析服务的镜像：RunPod serverless 用，也能当普通 pod 起来 ssh 调试。
# 为什么打镜像：serverless 每次开的是空白机器，现装依赖 1.5–13 分钟、下模型 2.2GB，用户要等也要付钱（Ludisce 10-05 实测）。
FROM runpod/base:1.4.0-ubuntu2204

ENV PYTHONUNBUFFERED=1 \
    UV_BREAK_SYSTEM_PACKAGES=1 \
    MINERU_MODEL_VLM_ENGINE=vllm \
    MINERU_MODEL_SMALL_BACKEND=torch

ARG MINERU_VERSION=4.0.10

# 版面识别和看图模型都放显卡：10-05 在 3090 上，版面放 CPU 慢一倍；Linux 的 llama.cpp 包不带显卡，只能用 vllm
RUN uv pip install --system --python python3.12 --no-cache "mineru[full]==${MINERU_VERSION}" "runpod>=1.7,<2"

# 模型打进镜像（standard 档、torch 小模型、vllm 看图模型）
RUN mineru-kit models download --tier standard --small-backend torch --vlm-engine vllm -s huggingface && \
    mineru-kit models verify --tier standard --small-backend torch --vlm-engine vllm

# torch cu130 现场编译要找 pip 装的 nvidia 库（libnvrtc-builtins.so.13.0），开机时加进搜索路径
RUN mkdir -p /opt/worker && python3.12 -c "import glob,site,os;s=site.getsitepackages()[0];print(':'.join(sorted({os.path.dirname(p) for p in glob.glob(s+'/nvidia/**/*.so*',recursive=True)})))" > /opt/worker/nvlibs.txt

COPY handler.py entry.sh /opt/worker/
RUN chmod +x /opt/worker/entry.sh

CMD ["/opt/worker/entry.sh"]
