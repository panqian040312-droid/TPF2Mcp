"""One-shot: remap the `tools/...` keys in docs/code-wiki-map.json to their new layer paths.

Keys are matched by basename against the files that actually exist under the four layers,
so a wrong guess is impossible -- anything unmatched is reported, not silently dropped.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "docs" / "code-wiki-map.json"
LAYERS = ["0_core_shared", "1_data_collection", "2_brain_analysis", "3_dashboard_ui", "4_execution_control"]
SUFFIXES = {".py", ".ps1"}

document = json.loads(MAP_PATH.read_text(encoding="utf-8"))
files = document["files"]

by_name: dict[str, list[str]] = {}
for layer in LAYERS:
    base = ROOT / layer
    if not base.is_dir():
        continue
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUFFIXES:
            by_name.setdefault(path.name, []).append(path.relative_to(ROOT).as_posix())

remapped: list[tuple[str, str]] = []
missing: list[str] = []
ambiguous: list[tuple[str, list[str]]] = []
result: dict = {}

for key, value in files.items():
    if not key.startswith("tools/"):
        result[key] = value
        continue
    name = key.split("/")[-1]
    candidates = by_name.get(name, [])
    if len(candidates) == 1:
        result[candidates[0]] = value
        remapped.append((key, candidates[0]))
    elif not candidates:
        result[key] = value
        missing.append(key)
    else:
        result[key] = value
        ambiguous.append((key, candidates))

document["files"] = result
MAP_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"remapped   : {len(remapped)}")
print(f"missing    : {len(missing)}")
print(f"ambiguous  : {len(ambiguous)}")
print(f"total keys : {len(result)}")
for old, new in remapped:
    print(f"  {old}  ->  {new}")
if missing:
    print("\nMISSING (key kept as-is):")
    for key in missing:
        print(f"  {key}")
if ambiguous:
    print("\nAMBIGUOUS (key kept as-is):")
    for key, cands in ambiguous:
        print(f"  {key}: {cands}")
