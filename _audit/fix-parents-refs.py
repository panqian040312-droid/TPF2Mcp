"""One-shot: replace `X = Path(__file__).resolve().parents[1]` with a search for `.git`.

Why: under tools/ every script was exactly one level below the repository root, so
`parents[1]` was correct. After the move into the four layers, only `2_brain_analysis/`
still happens to be one level deep -- the others silently resolve to their own layer
directory (e.g. `1_data_collection/`). Searching upward for `.git` is depth-independent.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ["0_core_shared", "1_data_collection", "2_brain_analysis", "3_dashboard_ui", "4_execution_control"]

PATTERN = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*Path\(__file__\)\.resolve\(\)\.parents\[1\]\s*$",
    re.MULTILINE,
)
REPLACEMENT = r'\1 = next(p for p in Path(__file__).resolve().parents if (p / ".git").is_dir())'

changed: list[str] = []
for layer in LAYERS:
    base = ROOT / layer
    if not base.is_dir():
        continue
    for path in sorted(base.rglob("*.py")):
        original = path.read_text(encoding="utf-8")
        updated = PATTERN.sub(REPLACEMENT, original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())

print(f"changed: {len(changed)}")
for name in changed:
    print(f"  {name}")
