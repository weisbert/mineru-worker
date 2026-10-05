"""建 / 改 RunPod serverless 接口（模板 + endpoint），用这个仓库的镜像。

  python endpoint.py show                       看现有的 mineru 模板和接口
  python endpoint.py create --tag 4.0.10-r4     建模板和接口，打印接口 id
  python endpoint.py set-image --tag 4.0.10-r5  换模板的镜像版本，并清掉旧版本的机器

钥匙取环境变量 RUNPOD_API_KEY，没有就读 ~/.config/gpu-rent/deploy.env。
接口配置（10-05 定）：没有活时零台机器；最多 2 台防失控；干完活空等 60 秒再关（同一次洗书里定级探针和整本隔几分钟，
免得再付一次 80–170 秒开机）；24GB 档 A5000 / 3090 / L4（vllm 在 24GB 上实测过），单个请求 20 分钟超时。
"""
import argparse
import json
import os
import time
import urllib.request

REST = "https://rest.runpod.io/v1"
NAME = "mineru-worker"
IMAGE = "ghcr.io/weisbert/mineru-worker"
GPUS = ["NVIDIA RTX A5000", "NVIDIA GeForce RTX 3090", "NVIDIA L4"]


def key():
    k = os.environ.get("RUNPOD_API_KEY")
    if k:
        return k
    p = os.path.expanduser("~/.config/gpu-rent/deploy.env")
    for line in open(p, encoding="utf-8"):
        if line.startswith("RUNPOD_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("没有 RUNPOD_API_KEY")


def call(method, path, body=None):
    req = urllib.request.Request(REST + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json", "User-Agent": "mineru-worker-endpoint/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t = r.read()
            return json.loads(t) if t else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} → {e.code} {e.read()[:500]!r}")


def mine():
    ts = [t for t in call("GET", "/templates") or [] if t.get("name") == NAME]
    es = [e for e in call("GET", "/endpoints") or [] if (e.get("name") or "").startswith(NAME)]
    return ts, es


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["show", "create", "set-image"])
    ap.add_argument("--tag")
    a = ap.parse_args()
    ts, es = mine()
    if a.cmd == "show":
        for t in ts:
            print("template", t["id"], t.get("imageName"))
        for e in es:
            print("endpoint", e["id"], e.get("name"), "workers", e.get("workersMin"), "-", e.get("workersMax"), "idle", e.get("idleTimeout"), "gpus", e.get("gpuTypeIds"))
        return
    if not a.tag:
        raise SystemExit("要 --tag")
    image = f"{IMAGE}:{a.tag}"
    if a.cmd == "set-image":
        if not ts:
            raise SystemExit("还没有模板，先 create")
        call("PATCH", f"/templates/{ts[0]['id']}", {"imageName": image})
        print("template", ts[0]["id"], "→", image)
        # 只换模板的话，快速开机会把旧版本的机器（连同加载好的模型）恢复来接单（10-05 两次烟雾测试都被 r3 接走）：台数调 0 再调回，清掉旧机器
        for e in es:
            call("PATCH", f"/endpoints/{e['id']}", {"workersMax": 0})
            time.sleep(20)
            call("PATCH", f"/endpoints/{e['id']}", {"workersMax": e.get("workersMax") or 2})
            print("endpoint", e["id"], "旧机器已清")
        return
    if ts or es:
        raise SystemExit(f"已经有了（模板 {[t['id'] for t in ts]}，接口 {[e['id'] for e in es]}），要换镜像用 set-image")
    t = call("POST", "/templates", {"name": NAME, "imageName": image, "isServerless": True, "containerDiskInGb": 40,
                                    "env": {"WORKER_CONCURRENCY": "2"}})
    print("template", t["id"], image)
    e = call("POST", "/endpoints", {"name": NAME, "templateId": t["id"], "gpuTypeIds": GPUS, "gpuCount": 1,
                                    "workersMin": 0, "workersMax": 2, "idleTimeout": 60, "scalerType": "QUEUE_DELAY", "scalerValue": 4,
                                    "flashboot": True, "executionTimeoutMs": 20 * 60 * 1000})
    print("endpoint", e["id"])


if __name__ == "__main__":
    main()
