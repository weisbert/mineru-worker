# mineru-worker

[MinerU](https://github.com/opendatalab/MinerU)（4.0.10）解析 PDF 的显卡服务镜像，给 RunPod serverless 用。镜像里只有开源的 MinerU、它的模型和一段处理请求的代码，没有密钥。

- 镜像：`ghcr.io/weisbert/mineru-worker:4.0.10`（推到 main 由 GitHub Actions 自动构建）
- 一台机器开机时起一次 `mineru-kit api-server --preload-models`，之后每个请求交给它；看图模型走 vllm，版面识别走 torch，都在显卡上。
- 请求格式见 `handler.py` 文件头：`pdf_url` 或 `pdf_b64`，可选 `pages`、`ocr_mode`、`result_put_url`。
- 不设 `RUNPOD_ENDPOINT_ID` 时（普通 pod）走 RunPod 的 `start.sh`，可以 ssh 进去用 `test/podtest.py` 自测。

实测（RTX 3090，未用这个镜像、现场装的）：307 页扫描书解析 133 秒；起模型第一次约 170 秒，之后约 45 秒。
