"""把一份 PDF 交给本机 api-server 解析，存成 zip。

不用 `mineru-kit parse --remote-url`：4.0.10 的 parse 命令走远程时不把 --ocr-mode 传给服务（kit/commands/parse.py 建
MinerUApiParser 时漏了 ocr_mode），服务按缺省 auto 走，带文字层的 PDF 就直接抄文字层——10-05 Make It Stick 云上结果
parse_mode 是 txt、「fi rst」这种文字层拆词原样出来。这里直接建 MinerUApiParser 把 ocr_mode 带上。

  python parse_remote.py <api_url> <pdf> <结果.zip> <tier> <ocr_mode> [页码]
"""
import sys
from pathlib import Path

from mineru.kit.common import save_parse_result
from mineru.parser import MinerUApiParser

api, pdf, dest, tier, ocr_mode = sys.argv[1:6]
pages = sys.argv[6] if len(sys.argv) > 6 else ""
parser = MinerUApiParser(api_url=api, tier=tier, ocr_mode=ocr_mode, include_images=True)
save_parse_result(parser.parse(pdf, page_range=pages), Path(dest), "zip")
print("parsed", dest, flush=True)
