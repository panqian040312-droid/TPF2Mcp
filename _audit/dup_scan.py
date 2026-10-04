"""Audit: near-duplicate files, duplicate function names/bodies, dead scripts.

Read-only. Emits JSON + a text report. No project files are touched.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def norm_lines(text: str, kind: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if kind == "py" and s.startswith("#"):
            continue
        if kind == "js" and (s.startswith("//") or s.startswith("/*") or s.startswith("*")):
            continue
        if kind == "lua" and s.startswith("--"):
            continue
        s = re.sub(r"\s+", " ", s)
        out.append(s)
    return out


def collect() -> list[tuple[str, str, Path]]:
    items: list[tuple[str, str, Path]] = []
    for p in sorted(ROOT.glob("*.py")):
        items.append(("py", p.stem + " [top]", p))
    for p in sorted(ROOT.glob("tools/*.py")):
        items.append(("py", "tools/" + p.name, p))
    for p in sorted(ROOT.glob("mcp_server/src/tpf2_mcp/**/*.py")):
        items.append(("py", "mcp/" + p.relative_to(ROOT / "mcp_server/src/tpf2_mcp").as_posix(), p))
    for p in sorted(ROOT.glob("ui/rail-map/*.js")):
        items.append(("js", "ui/" + p.name, p))
    for p in sorted(ROOT.glob("tpf2_mod/res/scripts/tpf2_mcp/**/*.lua")):
        items.append(("lua", "lua/" + p.name, p))
    return items


def py_functions(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    result = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_names = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    body_names.append(sub.id)
                elif isinstance(sub, ast.Attribute):
                    body_names.append(sub.attr)
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    body_names.append(sub.value)
            sig = "|".join(body_names)
            result.append((node.name, len(node.body), hashlib.md5(sig.encode()).hexdigest()[:10]))
    return result


def js_lua_functions(text: str, kind: str):
    if kind == "js":
        pat = re.compile(r"(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(", re.M)
    else:
        pat = re.compile(r"(?:^|\n)\s*(?:local\s+)?function\s+([\w.:]+)", re.M)
    names = []
    for m in pat.finditer(text):
        names.append(next(g for g in m.groups() if g))
    return names


def main() -> int:
    items = collect()
    report: dict = {"files": {}, "near_duplicates": [], "dup_function_names": {}, "dup_bodies": {}}

    texts = {}
    for kind, label, path in items:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            report["files"][label] = {"error": str(e)}
            continue
        lines = norm_lines(raw, kind)
        texts[label] = (kind, lines, raw, path)
        report["files"][label] = {
            "kind": kind,
            "raw_lines": len(raw.splitlines()),
            "code_lines": len(lines),
            "bytes": path.stat().st_size,
        }

    labels = list(texts)
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            ka, la, _, _ = texts[a]
            kb, lb, _, _ = texts[b]
            if ka != kb:
                continue
            if min(len(la), len(lb)) < 8:
                continue
            r = difflib.SequenceMatcher(None, la, lb, autojunk=False).ratio()
            if r >= 0.40:
                report["near_duplicates"].append({"a": a, "b": b, "ratio": round(r, 3),
                                                  "lines_a": len(la), "lines_b": len(lb)})
    report["near_duplicates"].sort(key=lambda d: -d["ratio"])

    name_map = defaultdict(list)
    body_map = defaultdict(list)
    for label, (kind, lines, raw, path) in texts.items():
        if kind == "py":
            for name, n, h in py_functions(path):
                if n >= 6:
                    name_map[name].append(label)
                    body_map[h].append(f"{label}::{name}")
        else:
            for name in js_lua_functions(raw, kind):
                name_map[name].append(label)
    report["dup_function_names"] = {k: sorted(set(v)) for k, v in name_map.items() if len(set(v)) > 1}
    report["dup_bodies"] = {k: sorted(set(v)) for k, v in body_map.items() if len(set(v)) > 1}

    out = ROOT / "_audit"
    out.mkdir(exist_ok=True)
    (out / "dup_scan.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 78)
    print(f"FILES SCANNED: {len(report['files'])}")
    print("=" * 78)
    print("\n--- NEAR-DUPLICATE FILE PAIRS (>=0.55) ---")
    for d in report["near_duplicates"]:
        print(f"  {d['ratio']:.2f}  {d['a']}  <->  {d['b']}  ({d['lines_a']}/{d['lines_b']} lines)")
    print(f"\n  total pairs: {len(report['near_duplicates'])}")
    print("\n--- DUPLICATE FUNCTION NAMES ACROSS FILES ---")
    for k, v in sorted(report["dup_function_names"].items(), key=lambda kv: -len(kv[1])):
        print(f"  {k}  x{len(v)}: {', '.join(v)}")
    print(f"\n  total names: {len(report['dup_function_names'])}")
    print("\n--- IDENTICAL FUNCTION BODIES (>=6 stmts) ---")
    for k, v in sorted(report["dup_bodies"].items(), key=lambda kv: -len(kv[1])):
        print(f"  {v}")
    print(f"\n  total bodies: {len(report['dup_bodies'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
