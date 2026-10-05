#!/bin/bash
# serverless（RunPod 注入 RUNPOD_ENDPOINT_ID）起处理请求的代码；否则当普通 pod，交给 RunPod 的 start.sh（ssh 调试用）
export LD_LIBRARY_PATH="$(cat /opt/worker/nvlibs.txt):${LD_LIBRARY_PATH:-}"
if [ -n "${RUNPOD_ENDPOINT_ID:-}" ]; then
  exec python3.12 -u /opt/worker/handler.py
fi
exec /start.sh
