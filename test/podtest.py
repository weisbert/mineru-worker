"""在用这个镜像起的 RunPod pod 里自测：起服务一次，再跑 30 页、整本、两段同时跑。
用法（pod 里）：export LD_LIBRARY_PATH="$(cat /opt/worker/nvlibs.txt):$LD_LIBRARY_PATH"; python3.12 podtest.py /workspace/t/book.pdf /workspace/t/out
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, "/opt/worker")
import handler as H  # noqa: E402

pdf, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
url = "file://" + pdf


def show(name, r):
    r = {k: v for k, v in r.items() if k != "zip_b64"}
    print(f"RESULT {name} {json.dumps(r, ensure_ascii=False)}", flush=True)


async def main():
    print(f"BOOT {H.boot()}s", flush=True)
    show("p30", await H.handler({"input": {"pdf_url": url, "pages": "41-70", "result_file": f"{out}/p30.zip"}}))
    show("p30_again", await H.handler({"input": {"pdf_url": url, "pages": "41-70", "result_file": f"{out}/p30b.zip"}}))
    show("full", await H.handler({"input": {"pdf_url": url, "result_file": f"{out}/full.zip"}}))
    t = time.time()
    rs = await asyncio.gather(
        H.handler({"input": {"pdf_url": url, "pages": "1-154", "result_file": f"{out}/half1.zip"}}),
        H.handler({"input": {"pdf_url": url, "pages": "155-307", "result_file": f"{out}/half2.zip"}}),
    )
    for i, r in enumerate(rs):
        show(f"half{i + 1}", r)
    print(f"RESULT halves_wall {round(time.time() - t, 1)}", flush=True)


asyncio.run(main())
print("PODTEST_DONE", flush=True)
