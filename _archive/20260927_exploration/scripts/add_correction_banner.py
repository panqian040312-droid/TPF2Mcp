"""给既有报告顶部插入口径更正说明（幂等：已插入则跳过）。"""
from pathlib import Path

BANNER = """> 🔴 **口径更正（2026-09-27 15:20 追加）**
> 本报告里的「运量 / 年运量 / 每车年运量 / 吞吐量」都是引擎字段 `line.rate`。
> 经 271 条线路实测：`rate = round(730.5 × 单车容量 ÷ 发车间隔)`，其中 269 条精确相等、残差仅为整数取整。
> 也就是说，**该字段衡量的是「运力供给」（满载口径的理论年输送能力），不是实测客流或货流**。
> 文中据此得出的「需求是否被满足 / 运力闲置该减车」类判断，只能改读作「运力配置高低」，
> 不能当作需求证据。完整核查与替代指标见 `TPF2客流核查与客运运力分析_20260927.md`。

"""

MARK = "口径更正（2026-09-27"
R = Path(r"E:\workbody\TPF2Mcp\reports")
for f in sorted(R.glob("*.md")):
    if f.name.startswith("TPF2客流核查"):
        continue
    txt = f.read_text(encoding="utf-8")
    if MARK in txt:
        print("跳过（已有）", f.name)
        continue
    f.write_text(BANNER + txt, encoding="utf-8")
    print("已插入", f.name, f"(原 {len(txt)} 字节)")
