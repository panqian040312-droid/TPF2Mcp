"""One-shot: rewrite `tools/<name>.py|.ps1` path references to their new layer paths.

Deliberately narrow:
  * pattern requires a `.py`/`.ps1` suffix, so MCP protocol strings like `tools/list`
    and `tools/call` are never touched;
  * the new path is looked up from the file that actually exists, so a wrong guess
    is impossible;
  * only the four layers, tests/, AGENTS.md and docs/*.md are rewritten --
    deploy_mod_layers.bat and build-workshop-package.ps1 are left alone on purpose,
    because their `tools\\` occurrences are the *staging/package* target path, not a source.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ["0_core_shared", "1_data_collection", "2_brain_analysis", "3_dashboard_ui", "4_execution_control"]
SUFFIXES = {".py", ".ps1"}

by_name: dict[str, str] = {}
for layer in LAYERS:
    base = ROOT / layer
    if not base.is_dir():
        continue
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUFFIXES:
            by_name[path.name] = path.relative_to(ROOT).as_posix()

targets: list[Path] = []
for layer in LAYERS:
    base = ROOT / layer
    if base.is_dir():
        targets += [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES]
tests = ROOT / "tests"
if tests.is_dir():
    targets += list(tests.glob("*.py"))
targets.append(ROOT / "AGENTS.md")
targets += list((ROOT / "docs").glob("*.md"))

PATTERN = re.compile(r"tools[/\\]([A-Za-z0-9_.\-]+\.(?:py|ps1))")
changed: list[tuple[str, int]] = []
unmatched: set[str] = set()

for path in sorted(set(targets)):
    if not path.is_file():
        continue
    original = path.read_text(encoding="utf-8", errors="replace")
    count = 0

    def replace(match: re.Match) -> str:
        global count
        name = match.group(1)
        new = by_name.get(name)
        if new is None:
            unmatched.add(name)
            return match.group(0)
        count += 1
        return new

    updated = PATTERN.sub(replace, original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        changed.append((path.relative_to(ROOT).as_posix(), count))

print(f"rewritten files : {len(changed)}")
for name, count in changed:
    print(f"  {count:3d}  {name}")
if unmatched:
    print("\nUNMATCHED (left as-is):")
    for name in sorted(unmatched):
        print(f"  {name}")
