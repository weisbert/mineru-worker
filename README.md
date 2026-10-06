# mineru-worker

[MinerU](https://github.com/opendatalab/MinerU)（4.0.10）解析 PDF 的显卡服务镜像，给 RunPod serverless 用。镜像里只有开源的 MinerU、它的模型和一段处理请求的代码，没有密钥。

- 镜像：`ghcr.io/weisbert/mineru-worker:4.0.10`（推到 main 由 GitHub Actions 自动构建）
- 一台机器开机时起一次 `mineru-kit api-server --preload-models`，之后每个请求交给它；看图模型走 vllm，版面识别走 torch，都在显卡上。
- 请求格式见 `handler.py` 文件头：`pdf_url` 或 `pdf_b64`，可选 `pages`、`ocr_mode`、`result_put_url`、`keep`（只回传 zip 里这几个文件；RunPod 一次返回限 10MB）。
- 镜像标签：`4.0.10` 跟最新构建走；`4.0.10-r<构建次数>` 固定不变，接口锁这个。
- 建接口：`python endpoint.py create --tag 4.0.10-r4`（模板 + 接口：零台起、最多 1 台、空等 60 秒关、24GB 档），换版本 `python endpoint.py set-image --tag …`（顺带把台数调 0 再调回，清掉旧版本的机器），查看 `python endpoint.py show`。
- 不设 `RUNPOD_ENDPOINT_ID` 时（普通 pod）走 RunPod 的 `start.sh`，可以 ssh 进去用 `test/podtest.py` 自测。

实测（10-05，RunPod RTX A5000 用这个镜像，307 页中文扫描书）：

| | 用时 |
|---|---|
| 新机器拉镜像（7.3GB） | 2.5–4.75 分钟（两台） |
| 开机起服务、加载模型 | 83 秒（新机器，含编译和显卡预热） |
| 第一个请求，30 页 | 29 秒 |
| 同一台机器第二个请求，同样 30 页 | 10.4 秒 |
| 整本 307 页 | 133 秒 |
| 同一台机器两段同时跑（154 + 153 页） | 117 秒（只比整本一次快 12%，不值得） |

同一本书在两台云机器上跑两次，去掉空白后字差 0.22%（看图模型不是逐字确定的）。
