"""MinerU 解析服务（RunPod serverless 的处理代码）。

一台机器开机时起一次 `mineru-kit api-server --preload-models`，模型只加载一次；
之后每个请求用 `mineru-kit parse --remote-url` 交给它，同一台机器上的后续请求不再付起模型的时间。

请求 input：
  pdf_url | pdf_b64        原料（二选一；pdf_url 支持 https:// 和 file://）
  pages                    页码，同 mineru-kit：'1-50,60'；缺省整本
  ocr_mode                 auto | txt | ocr，缺省 ocr
  tier                     缺省 standard
  result_put_url           结果 zip 用 PUT 传到这个地址（对象存储的预签名链接）；不给就把 zip 用 base64 放在返回里
  result_file              只在 pod 里自测用：结果写到本机这个路径
  keep                     只留 zip 里这几个文件（如 ["structured_content.json"]）；RunPod 返回上限 10MB，
                           整本 zip 带图 30MB+，洗书只读 structured_content.json
返回：ok、zip_bytes、timing_s（fetch / parse / 这台机器起服务用的 boot、是不是这台机器的第一个请求 cold）
"""
import asyncio
import base64
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile

PORT = int(os.environ.get("MINERU_API_PORT", "8000"))
API = f"http://127.0.0.1:{PORT}"
# 同一台机器同时解析几段：共用一个看图模型，版面识别排队（10-05 起两个独立进程会抢显存起不来）
CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "2"))

_state = {"proc": None, "boot_s": None, "jobs": 0}


def boot():
    """起 api-server，等端口通；已经起过就直接返回。"""
    if _state["proc"] is not None and _state["proc"].poll() is None:
        return _state["boot_s"]
    t = time.time()
    proc = subprocess.Popen([
        "mineru-kit", "api-server", "--host", "127.0.0.1", "--port", str(PORT),
        "--tier", "standard", "--preload-models", "--allow-local-source",
        "--concurrency", str(CONCURRENCY),
    ])
    while True:
        if proc.poll() is not None:
            raise RuntimeError(f"api-server 退出了，退出码 {proc.returncode}")
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=1).close()
            break
        except OSError:
            time.sleep(1)
    _state.update(proc=proc, boot_s=round(time.time() - t, 1))
    print(f"api-server ready in {_state['boot_s']}s", flush=True)
    return _state["boot_s"]


def _fetch(url, path):
    with urllib.request.urlopen(url, timeout=300) as r, open(path, "wb") as f:
        shutil.copyfileobj(r, f)


def _put(url, path):
    with open(path, "rb") as f:
        req = urllib.request.Request(url, data=f.read(), method="PUT", headers={"Content-Type": "application/zip"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.status


def _keep(src, names, dst):
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in zi.namelist():
            if n in names:
                zo.writestr(n, zi.read(n))
    return dst


async def handler(job):
    inp = job.get("input") or {}
    boot_s = await asyncio.to_thread(boot)
    _state["jobs"] += 1
    cold = _state["jobs"] == 1
    t0 = time.time()
    work = tempfile.mkdtemp(prefix="job-")
    try:
        pdf = os.path.join(work, "book.pdf")
        if inp.get("pdf_url"):
            await asyncio.to_thread(_fetch, inp["pdf_url"], pdf)
        elif inp.get("pdf_b64"):
            with open(pdf, "wb") as f:
                f.write(base64.b64decode(inp["pdf_b64"]))
        else:
            return {"error": "要 pdf_url 或 pdf_b64"}
        t1 = time.time()
        out = os.path.join(work, "out")
        args = ["mineru-kit", "parse", pdf, "-o", out, "--format", "zip",
                "--tier", str(inp.get("tier", "standard")), "--ocr-mode", str(inp.get("ocr_mode", "ocr")),
                "--remote-url", API]
        if inp.get("pages"):
            args += ["-p", str(inp["pages"])]
        p = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        log, _ = await p.communicate()
        log = log.decode("utf-8", "replace")
        zips = [os.path.join(dp, n) for dp, _, ns in os.walk(out) for n in ns if n.endswith(".zip")]
        if p.returncode != 0 or not zips:
            return {"error": f"parse 失败，退出码 {p.returncode}", "log_tail": log[-4000:]}
        z = zips[0]
        if inp.get("keep"):
            z = _keep(z, set(inp["keep"]), os.path.join(work, "keep.zip"))
        t2 = time.time()
        res = {"ok": True, "zip_bytes": os.path.getsize(z),
               "timing_s": {"fetch": round(t1 - t0, 1), "parse": round(t2 - t1, 1), "boot": boot_s, "cold": cold}}
        if inp.get("result_put_url"):
            res["put_status"] = await asyncio.to_thread(_put, inp["result_put_url"], z)
        elif inp.get("result_file"):
            shutil.copyfile(z, inp["result_file"])
            res["result_file"] = inp["result_file"]
        else:
            with open(z, "rb") as f:
                res["zip_b64"] = base64.b64encode(f.read()).decode()
        res["timing_s"]["total"] = round(time.time() - t0, 1)
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    import runpod

    boot()
    runpod.serverless.start({"handler": handler, "concurrency_modifier": lambda current: CONCURRENCY})
