#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 `docs/CODE_WIKI_INDEX.md` —— 代码 ↔ 官方文档索引。

## 这东西解决什么

项目里有两拨代码：上游作者写的（`origin/main`，止于 `836b70f`）和我们后加的
（分支 `feature/multi-layer-map`）。日子一长就没人说得清"这段代码凭什么这么写、
官方哪一页说的"。本工具把这件事**变成一张必须维护的表**：

    源数据：docs/code-wiki-map.json      ← 人工维护（唯一的真相）
    产物：  docs/CODE_WIKI_INDEX.md      ← 自动生成，**不要手改**（改了会被下次生成覆盖）

## 三条硬断言（不通过就报错退出）

1. **每个源码文件都必须在映射表里登记** —— 新加文件忘了登记，这里直接失败。
2. **映射表里不能有失效条目** —— 引用的文件不存在、函数名写错、都被抓出来。
3. **官方出处必须能落到真实文档** —— 映射表里写的 `GM:towns` / `MD:vehicletypes`
   必须能在知识库里找到对应文件，**编不出出处**。

## 用法

    python 0_core_shared/index/build-code-wiki-index.py                 # 生成索引 + 跑断言
    python 0_core_shared/index/build-code-wiki-index.py --check         # 只跑断言，不写文件（给 CI / 提交前用）
    python 0_core_shared/index/build-code-wiki-index.py --inventory     # 打印文件与函数清单（填映射表时用）
    python 0_core_shared/index/build-code-wiki-index.py --skeleton      # 按当前源码生成一份空映射表骨架
    python 0_core_shared/index/build-code-wiki-index.py --refs <目录>   # 指定官方知识库目录

知识库目录默认从环境变量 `TPF2_REFS_DIR` 取；没有则用内置默认值（本机专家包路径）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── 路径 ────────────────────────────────────────────────────────────────────
# 项目根：向上找 .git。不要写 parent.parent —— 本脚本在 0_core_shared/index/ 下，
# 数层数会在搬目录时静默算错（2026-10-03 踩过）。
ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".git").exists())
MAP_PATH = ROOT / "docs" / "code-wiki-map.json"
OUT_PATH = ROOT / "docs" / "CODE_WIKI_INDEX.md"

DEFAULT_REFS = Path(
    os.environ.get(
        "TPF2_REFS_DIR",
        r"C:\Users\RailG\.workbuddy\plugins\marketplaces\my-experts\plugins"
        r"\tpf2-chief-engineer\skills\tpf2-game-reference\references",
    )
)

# ── 要索引哪些文件 ──────────────────────────────────────────────────────────
# 用户 2026-10-02 划定：mod Lua + MCP Python + 前端 JS + tools + protocol。
# tests/ 归到它测的模块名下、不逐条索引；docs/agents/ 是文档不是代码；
# rail-network-tiles/ 是生成物；vendor/ 是第三方库。
SCOPE: dict[str, tuple[str, str]] = {
    # 目录: (扩展名集合, 排除的路径片段)
    "tpf2_mod": (".lua", ()),
    "mcp_server": (".py", ("__pycache__",)),
    # 四层（2026-10-03：原 tools/ 已按层拆分）
    "0_core_shared": (".py .ps1", ("__pycache__",)),
    "1_data_collection": (".py", ("__pycache__",)),
    "2_brain_analysis": (".py", ("__pycache__",)),
    "3_dashboard_ui": (".py", ("__pycache__",)),
    "4_execution_control": (".py .ps1", ("__pycache__",)),
    "ui": (".js", ("vendor/", "rail-network-tiles/", "node_modules/")),
    "protocol": (".json", ()),
}

LANG_BY_EXT = {".lua": "lua", ".py": "python", ".js": "js", ".ps1": "ps1", ".json": "json"}

# ── 官方文档代号 ────────────────────────────────────────────────────────────
# 代号 → (知识库里的相对路径模式, 前缀说明)。`{}` 会被替换成 `:key` 里的 key。
DOC_KINDS: dict[str, tuple[str, str]] = {
    "GM": ("gamemanual/{}.md", "游戏手册（玩家视角：机制、运营、经济）"),
    "MD": ("modding/{}.md", "官方 modding 文档（格式、字段、脚本）"),
    "API": ("api/modules/api.{}.md", "引擎 API 参考（类型/字段/函数签名）"),
    "DG": ("_digest/{}.md", "全库精读摘要（我们自己产出的二手材料）"),
    "CM": ("community/{}.md", "社区指南（**必须甄别**，见 _digest/11）"),
    "EX": ("api/examples/{}.lua.md", "官方示例脚本"),
    "PN": ("_PROJECT-NOTES.md", "官方文档 × 本项目的对接笔记（我们产出）"),
}

# 非知识库出处的代号（不走文件存在性校验，但要在报告里说明）
SPECIAL_CODES = {
    "SRC": "游戏本体文件（res/construction、res/scripts、res/models 下的 .con/.module/.mdl/.lua）",
    "SAVE": "存档实测（bridge 产物 / 探针实测），无文档出处",
    "SELF": "本项目自创（无官方对应，也不来自游戏文件）",
    "—": "无官方对应",
}

# 关系类型：这个代码和官方出处是什么关系
RELATIONS = {
    "引用": "直接调用官方 API / 读官方定义的表",
    "复刻": "把官方文档或游戏文件里的公式、编码规则原样实现了一遍",
    "应用": "官方机制的一个应用（机制本身是官方的，用法是本项目的）",
    "校验": "用官方数据反查/校验本项目的实现对不对",
    "对照": "与官方做法不一致，或官方无明确说法（要标出来）",
}

CONFIDENCE = ("高", "中", "低", "待核")


# ── 函数提取 ────────────────────────────────────────────────────────────────
PATTERNS = {
    "lua": [
        re.compile(r"^\s*local\s+function\s+([\w.:]+)\s*\("),
        re.compile(r"^\s*function\s+([\w.:]+)\s*\("),
        re.compile(r"^\s*([\w.:]+)\s*=\s*function\s*\("),
    ],
    "python": [re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")],
    "js": [
        re.compile(r"^\s*function\s+(\w+)\s*\("),
        re.compile(r"^\s*(?:var|let|const)\s+([\w$]+)\s*=\s*function\s*\("),
        re.compile(r"^\s*([\w$]+)\s*[:=]\s*function\s*\("),
        re.compile(r"^\s*([\w$.]+)\s*=\s*function\s*\("),
    ],
    "ps1": [re.compile(r"^\s*function\s+([\w-]+)\s*[\{\(]?")],
}

# JS 全局兜底：行首匹配不到时（压缩成一行的文件），退回全文扫描，拿不到注释
JS_GLOBAL = re.compile(r"function\s+(\w+)\s*\(")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _comment_block(lines: list[str], i: int, lang: str) -> str:
    """取第 i 行**之前**紧邻的注释块，拼成一行（做"这个函数干什么"的兜底说明）。"""
    marks = {"lua": ("--",), "python": ("#",), "js": ("//", "*", "/*"), "ps1": ("#",)}.get(lang, ("#",))
    out: list[str] = []
    j = i - 1
    while j >= 0:
        stripped = lines[j].strip()
        if not stripped:
            j -= 1
            continue
        if stripped.startswith(marks) or stripped.endswith("*/"):
            out.append(stripped)
            j -= 1
            continue
        break
    out.reverse()
    text = " ".join(out)
    text = re.sub(r"^(--|//|#|\*|/\*+|/\*|\*/)\s*", "", text)
    text = re.sub(r"(--|//|#|\*/)\s*", " ", text)
    text = re.sub(r"[\s]+", " ", text).strip()
    return text[:200]


def _docstring_after(lines: list[str], i: int) -> str:
    """Python 专用：函数体第一句 `\"\"\"...\"\"\"`。很多文件不写前置注释，只写 docstring。"""
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return ""
    head = lines[j].strip()
    if not (head.startswith('"""') or head.startswith("'''")):
        return ""
    quote = head[:3]
    body = head[3:]
    if quote in body:
        return body.split(quote)[0].strip()[:200]
    parts = [body]
    j += 1
    while j < len(lines):
        if quote in lines[j]:
            parts.append(lines[j].split(quote)[0])
            break
        parts.append(lines[j].strip())
        j += 1
    return re.sub(r"\s+", " ", " ".join(parts)).strip()[:200]


def module_header(text: str, lang: str) -> str:
    """文件开头那段说明（Lua/PowerShell 是前导注释，Python 是模块 docstring）。"""
    lines = text.splitlines()
    if lang == "python":
        j = 0
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and (lines[j].strip().startswith('"""') or lines[j].strip().startswith("'''")):
            return _docstring_after(lines, j - 1)
        return ""
    marks = {"lua": ("--",), "js": ("//",), "ps1": ("#",)}.get(lang, ("#",))
    out: list[str] = []
    for line in lines[:40]:
        s = line.strip()
        if not s:
            if out:
                break
            continue
        if s.startswith(marks):
            out.append(s)
            continue
        break
    text_out = " ".join(out)
    text_out = re.sub(r"^(--|//|#)\s*", "", text_out)
    text_out = re.sub(r"(--|//|#)\s*", " ", text_out)
    return re.sub(r"\s+", " ", text_out).strip()[:300]


def extract_functions(text: str, lang: str, start_line: int = 0) -> list[dict]:
    """返回 [{name, line, doc}]；line 是 1 起的行号（含 start_line 偏移）。"""
    if lang not in PATTERNS:
        return []
    lines = text.splitlines()
    found: list[dict] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines):
        # 单行里塞了太多东西的（压缩文件），按行首 match 会漏；这种交给下面的全局兜底
        for pat in PATTERNS[lang]:
            m = pat.match(line)
            if not m:
                continue
            name = m.group(1)
            if name in seen:
                break
            seen.add(name)
            doc = _comment_block(lines, idx, lang)
            if not doc and lang == "python":
                doc = _docstring_after(lines, idx)
            found.append({"name": name, "line": start_line + idx + 1, "doc": doc})
            break
    if lang == "js" and len(found) < 2:
        for m in JS_GLOBAL.finditer(text):
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            line = start_line + text[: m.start()].count("\n") + 1
            found.append({"name": name, "line": line, "doc": ""})
        found.sort(key=lambda f: f["line"])
    return found


# ── 扫描 ────────────────────────────────────────────────────────────────────
def iter_source_files() -> list[str]:
    out: list[str] = []
    for top, (exts, excludes) in SCOPE.items():
        base = ROOT / top
        if not base.is_dir():
            continue
        allow = set(exts.split())
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in allow:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if any(x in rel for x in excludes):
                continue
            out.append(rel)
    return out


def inventory() -> dict[str, dict]:
    inv: dict[str, dict] = {}
    for rel in iter_source_files():
        path = ROOT / rel
        text = read_text(path)
        lang = LANG_BY_EXT[path.suffix.lower()]
        inv[rel] = {
            "lines": text.count("\n") + 1,
            "lang": lang,
            "header": module_header(text, lang),
            "functions": extract_functions(text, lang),
        }
    return inv


# ── 知识库校验 ──────────────────────────────────────────────────────────────
def resolve_doc(code: str, refs: Path) -> tuple[bool, str]:
    """官方出处代号 → (能不能落到真实文件, 说明)。"""
    if code in SPECIAL_CODES:
        return True, SPECIAL_CODES[code]
    # `PN` 这种不带 key 的（整份文档就是出处）
    if code in DOC_KINDS and "{}" not in DOC_KINDS[code][0]:
        path = refs / DOC_KINDS[code][0]
        return (path.is_file(), path.relative_to(refs).as_posix() if path.is_file()
                else "知识库里没有 %s" % DOC_KINDS[code][0])
    if ":" not in code:
        return False, "格式不对，应为 `<类别>:<key>`（类别见 DOC_KINDS）"
    kind, key = code.split(":", 1)
    if kind not in DOC_KINDS:
        return False, "未知类别 %s" % kind
    pattern, _desc = DOC_KINDS[kind]
    path = refs / pattern.format(key)
    if path.is_file():
        return True, path.relative_to(refs).as_posix()
    # 容错：允许写短 key（如 `DG:06` 命中 `_digest/06-gamemanual-*.md`）
    parent, stem = path.parent, path.name[:-3] if path.suffix == ".md" else path.name
    if parent.is_dir():
        hits = sorted(p for p in parent.glob(stem + "*") if p.is_file())
        if len(hits) == 1:
            return True, hits[0].relative_to(refs).as_posix()
        if len(hits) > 1:
            return False, "%s 有歧义，命中 %d 个：%s" % (
                pattern.format(key), len(hits),
                [h.name for h in hits][:4])
    return False, "知识库里没有 %s" % pattern.format(key)


def doc_title(code: str, refs: Path) -> str:
    if code in SPECIAL_CODES:
        return SPECIAL_CODES[code]
    if code in DOC_KINDS and "{}" not in DOC_KINDS[code][0]:
        path = refs / DOC_KINDS[code][0]
    elif ":" in code:
        kind, key = code.split(":", 1)
        if kind not in DOC_KINDS:
            return ""
        path = refs / DOC_KINDS[kind][0].format(key)
    else:
        return ""
    if not path.is_file():
        return ""
    for line in read_text(path).splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


# ── 断言 ────────────────────────────────────────────────────────────────────
def run_assertions(inv: dict[str, dict], mapping: dict, refs: Path) -> list[str]:
    errors: list[str] = []
    entries = mapping.get("files") or {}

    # ① 每个源码文件都要登记
    missing = [f for f in inv if f not in entries]
    if missing:
        errors.append(
            "① 有 %d 个源码文件没有登记进映射表（新加代码必须登记）：\n%s"
            % (len(missing), "\n".join("     - " + m for m in sorted(missing)))
        )
    # 反向：映射表里不能有已不存在的文件
    ghost = [f for f in entries if f not in inv]
    if ghost:
        errors.append(
            "② 映射表里有 %d 条指向了不存在的源码文件：\n%s"
            % (len(ghost), "\n".join("     - " + g for g in sorted(ghost)))
        )

    # ③ 函数名要对得上（防止改名后映射表变成假账）
    for rel, entry in sorted(entries.items()):
        if rel not in inv:
            continue
        actual = {f["name"] for f in inv[rel]["functions"]}
        declared = set((entry.get("functions") or {}).keys())
        bogus = sorted(declared - actual)
        if bogus:
            errors.append(
                "③ %s 里映射表登记了不存在的函数：%s（现有函数中的相近者：%s）"
                % (rel, bogus, sorted(n for n in actual if any(b[:6] in n for b in bogus))[:5])
            )

    # ④ 官方出处必须能落到真实文档
    bad_docs: set[str] = set()
    for code in collect_codes(entries):
        ok, note = resolve_doc(code, refs)
        if not ok:
            bad_docs.add("%s —— %s" % (code, note))
    if bad_docs:
        errors.append(
            "④ 有 %d 个出处代号在知识库里找不到（不许编出处，也检查 TPF2_REFS_DIR）：\n%s"
            % (len(bad_docs), "\n".join("     - " + b for b in sorted(bad_docs)))
        )

    # ⑤ 枚举值合法性
    for rel, entry in sorted(entries.items()):
        for field, allowed in (("relation", RELATIONS), ("confidence", CONFIDENCE)):
            value = entry.get(field)
            if value and value not in allowed:
                errors.append("⑤ %s 的 %s=%r 不在允许值内 %s" % (rel, field, value, list(allowed)))
        for fn, fe in (entry.get("functions") or {}).items():
            if fe.get("relation") and fe["relation"] not in RELATIONS:
                errors.append("⑤ %s::%s 的 relation=%r 不合法" % (rel, fn, fe["relation"]))
            if fe.get("confidence") and fe["confidence"] not in CONFIDENCE:
                errors.append("⑤ %s::%s 的 confidence=%r 不合法" % (rel, fn, fe["confidence"]))
    return errors


def collect_codes(entries: dict) -> set[str]:
    codes: set[str] = set()

    def take(node):
        for c in node.get("sources") or []:
            codes.add(c)

    for entry in entries.values():
        take(entry)
        for fe in (entry.get("functions") or {}).values():
            take(fe)
    return codes


# ── 渲染 ────────────────────────────────────────────────────────────────────
def render(inv: dict[str, dict], mapping: dict, refs: Path) -> str:
    entries = mapping.get("files") or {}
    used_codes = sorted(collect_codes(entries))
    total_files = len(inv)
    total_funcs = sum(len(v["functions"]) for v in inv.values())
    # 三种函数分开数，别把"继承"混进"逐条标注"里充数
    ann = inherit = nobasis = 0
    for rel, v in inv.items():
        e = entries.get(rel) or {}
        fmap = e.get("functions") or {}
        for f in v["functions"]:
            fe = fmap.get(f["name"]) or {}
            if fe.get("sources"):
                ann += 1
            elif e.get("sources") and e.get("functions_inherit", True):
                inherit += 1
            else:
                nobasis += 1
    with_src = sum(1 for v in entries.values() if v.get("sources"))

    L: list[str] = []
    L.append("# 代码 ↔ 官方文档索引")
    L.append("")
    L.append("> **本文件由 `0_core_shared/index/build-code-wiki-index.py` 自动生成，不要手改。**")
    L.append("> 要改内容 → 改 `docs/code-wiki-map.json` → 重跑生成器。")
    L.append("> 手改这里的内容，下次生成就会被覆盖掉。")
    L.append("")
    L.append("## 一、这张表是干什么的")
    L.append("")
    L.append("项目里有两拨代码：**上游作者写的**（`origin/main`，止于 `836b70f`）和")
    L.append("**我们后加的**（分支 `feature/multi-layer-map`）。日子一长就没人说得清")
    L.append("「这段代码凭什么这么写、官方哪一页说的」。这张表就是干这个的：")
    L.append("**每个源码文件、每个函数，落到它依据的官方文档；没有依据的，明写没有。**")
    L.append("")
    L.append("| 项 | 数 |")
    L.append("|---|---|")
    L.append("| 已登记的源码文件 | **%d / %d** |" % (with_src, total_files))
    L.append("| 扫到的函数 | **%d** 个 |" % total_funcs)
    L.append("| ├ 单独标了出处的（函数本身有依据） | %d |" % ann)
    L.append("| ├ 沿用本文件依据的（整文件同一套依据，已在文件级写明） | %d |" % inherit)
    L.append("| └ 本文件判定为「无官方对应」的 | %d |" % nobasis)
    L.append("| 用到的官方文档 | **%d** 份 |" % len([c for c in used_codes if c not in SPECIAL_CODES]))
    L.append("")
    L.append("⚠️ **「没标出处」≠「漏了」**：`—` 是本项目自己的工程实现（管道、序列化、")
    L.append("界面外壳），**判定过、确实没有官方对应**；`SRC` 是依据游戏本体文件而非文档；")
    L.append("`SAVE` 是存档实测。三者的区别见下面第三节。")
    L.append("")
    L.append("## 二、怎么维护（**新写代码必读**）")
    L.append("")
    L.append("```")
    L.append("# 1) 看看有没有漏登记的（提交前跑，不通过就别提交）")
    L.append("python 0_core_shared/index/build-code-wiki-index.py --check")
    L.append("")
    L.append("# 2) 改了代码/加了新文件，把新东西登记进映射表")
    L.append("#    改 docs/code-wiki-map.json（结构照抄现有条目）")
    L.append("python 0_core_shared/index/build-code-wiki-index.py --inventory | less   # 看清单")
    L.append("")
    L.append("# 3) 重新生成索引")
    L.append("python 0_core_shared/index/build-code-wiki-index.py")
    L.append("```")
    L.append("")
    L.append("**规则（已写进 `AGENTS.md`）**：")
    L.append("")
    L.append("1. 新增源码文件 → **必须**在 `docs/code-wiki-map.json` 里登记，否则 `--check` 失败；")
    L.append("2. 改了函数的官方依据（比如换了字段来源）→ **必须**同步改映射表里对应那条；")
    L.append("3. 引用官方出处 **必须用代号**（`GM:towns` 这种），写错代号会让 `--check` 失败 ——")
    L.append("   这是故意的：**宁可报错，也不要让出处变成随口一说**。")
    L.append("")
    L.append("## 三、出处代号表")
    L.append("")
    L.append("| 代号写法 | 指什么 |")
    L.append("|---|---|")
    for kind, (pattern, desc) in sorted(DOC_KINDS.items()):
        L.append("| `%s` | %s |" % (kind + ":<页名>" if "{}" in pattern else kind, desc))
    for code, desc in SPECIAL_CODES.items():
        L.append("| `%s` | %s |" % (code, desc))
    L.append("")
    L.append("**关系类型**（这份代码和出处是什么关系）：")
    L.append("")
    L.append("| 类型 | 含义 |")
    L.append("|---|---|")
    for k, v in RELATIONS.items():
        L.append("| %s | %s |" % (k, v))
    L.append("")
    if used_codes:
        L.append("**本索引实际引用到的文档**：")
        L.append("")
        L.append("| 代号 | 文档标题 |")
        L.append("|---|---|")
        for code in used_codes:
            if code in SPECIAL_CODES:
                L.append("| `%s` | %s |" % (code, SPECIAL_CODES[code]))
            else:
                L.append("| `%s` | %s |" % (code, doc_title(code, refs) or "（读不到标题）"))
        L.append("")

    # 按目录分组
    L.append("## 四、逐文件索引")
    L.append("")
    groups: dict[str, list[str]] = {}
    for rel in sorted(inv):
        groups.setdefault(rel.split("/")[0], []).append(rel)
    for top in sorted(groups):
        L.append("### %s/　（%d 个文件）" % (top, len(groups[top])))
        L.append("")
        for rel in groups[top]:
            entry = entries.get(rel) or {}
            v = inv[rel]
            status = "**已登记**" if entry else "🔴 **未登记**"
            sources = "、".join("`%s`" % c for c in (entry.get("sources") or [])) or "`—`"
            L.append("#### `%s`　%s" % (rel, ""))
            L.append("")
            L.append("- **干什么**：%s" % (entry.get("what") or "（未填写）"))
            L.append("- **依据**：%s｜关系：%s｜置信度：%s"
                     % (sources, entry.get("relation") or "—", entry.get("confidence") or "—"))
            if entry.get("note"):
                L.append("- **备注**：%s" % entry["note"])
            L.append("- 规模：%d 行 / %d 个函数 ｜ %s" % (v["lines"], len(v["functions"]), status))
            funcs = v["functions"]
            fmap = entry.get("functions") or {}
            if funcs:
                L.append("")
                L.append("| 函数 | 干什么 | 官方出处 | 关系 | 置信度 |")
                L.append("|---|---|---|---|---|")
                for f in funcs:
                    fe = fmap.get(f["name"]) or {}
                    what = fe.get("what") or f["doc"] or "—"
                    what = what.replace("|", "\\|")
                    fs = fe.get("sources")
                    if fs:
                        srcs = "、".join("`%s`" % c for c in fs)
                        rel = fe.get("relation") or entry.get("relation") or "—"
                        conf = fe.get("confidence") or entry.get("confidence") or "—"
                    elif entry.get("sources") and entry.get("functions_inherit", True):
                        # 本文件所有函数都吃同一个依据（采集器基本都这样）——明写"继承"，
                        # 免得读表的人以为这行漏标了
                        srcs = "↳ 同本文件"
                        rel = "（同上）"
                        conf = "（同上）"
                    else:
                        srcs, rel, conf = "`—`", fe.get("relation") or "—", fe.get("confidence") or "—"
                    L.append("| `%s` | %s | %s | %s | %s |"
                             % (f["name"], what[:160], srcs, rel, conf))
            L.append("")
    return "\n".join(L) + "\n"


def skeleton(inv: dict[str, dict], mapping: dict) -> dict:
    """按当前源码生成/补全映射表骨架（保留已有内容）。"""
    entries = mapping.setdefault("files", {})
    for rel, v in inv.items():
        e = entries.setdefault(rel, {})
        e.setdefault("what", "")
        e.setdefault("sources", [])
        e.setdefault("relation", "")
        e.setdefault("confidence", "")
        fmap = e.setdefault("functions", {})
        for f in v["functions"]:
            fe = fmap.setdefault(f["name"], {})
            if f["doc"] and not fe.get("what"):
                fe["what"] = f["doc"]
    mapping.setdefault("_doc", "代码 ↔ 官方文档索引的映射表。改这里，然后重跑 0_core_shared/index/build-code-wiki-index.py。"
                               "详见 docs/CODE_WIKI_INDEX.md。")
    return mapping


def main() -> int:
    ap = argparse.ArgumentParser(description="生成代码 ↔ 官方文档索引")
    ap.add_argument("--check", action="store_true", help="只跑断言，不写文件")
    ap.add_argument("--inventory", action="store_true", help="打印文件与函数清单")
    ap.add_argument("--skeleton", action="store_true", help="按当前源码补全映射表骨架")
    ap.add_argument("--refs", default=str(DEFAULT_REFS), help="官方知识库 references 目录")
    ap.add_argument("--quiet", action="store_true", help="只输出错误")
    args = ap.parse_args()

    refs = Path(args.refs)
    inv = inventory()

    if args.inventory:
        for rel, v in sorted(inv.items()):
            print("%s  (%d 行, %d 函数)" % (rel, v["lines"], len(v["functions"])))
            if v.get("header"):
                print("    HEADER: %s" % v["header"][:180])
            for f in v["functions"]:
                print("    %-34s L%-5d %s" % (f["name"], f["line"], f["doc"][:90]))
        return 0

    mapping: dict = {}
    if MAP_PATH.is_file():
        mapping = json.loads(read_text(MAP_PATH))

    if args.skeleton:
        skeleton(inv, mapping)
        MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("已写入骨架：%s（%d 条）" % (MAP_PATH, len(mapping.get("files") or {})))
        return 0

    errors = run_assertions(inv, mapping, refs)
    if not refs.is_dir():
        print("⚠️ 找不到官方知识库目录：%s\n   （用 --refs 或环境变量 TPF2_REFS_DIR 指定；"
              "出处校验会因此全部失败）" % refs)
    if errors:
        print("❌ 索引校验未通过（%d 项）：\n" % len(errors))
        for e in errors:
            print("  " + e + "\n")
        return 1

    if not args.check:
        OUT_PATH.write_text(render(inv, mapping, refs), encoding="utf-8")
        if not args.quiet:
            print("✅ 已生成 %s" % OUT_PATH)
    if not args.quiet:
        files = len(inv)
        funcs = sum(len(v["functions"]) for v in inv.values())
        print("✅ 校验通过：%d 个源码文件、%d 个函数，全部已登记。" % (files, funcs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
