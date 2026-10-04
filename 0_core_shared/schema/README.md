# schema（契约定义）

> 🔴 **写新采集器 / 新字段之前先查 `fields.json`。**

| 文件 | 是什么 | 状态 |
|---|---|---|
| `fields.json` | **产物字段索引**：`bridge/*.json` 里已经出现过的所有字段路径 → 出现在哪些产物 | ✅ 已生成（23,405 条，37 个产物，3.7 MB） |
| `layer.schema.json` | 9 个 `layer-*.json` 的字段契约 | ⏳ 待冻结 |
| `probe.schema.json` | 探针产物契约 | ⏳ 待冻结 |
| `actions.schema.json` | `approved_actions.json` 契约 | ⏳ 待冻结（P5） |
| `audit.schema.json` | `audit_log.json` 契约 | ⏳ 待冻结（P5） |

## 复用优先的规矩

> **新字段要么复用已有路径，要么登记说明为什么复用不了。**

**动手前查两处**：

1. `docs/DATA_INVENTORY.md` 第零节「我想要 → 现成接口」—— **引擎接口**层（56 个，`--check` 强制）
2. `0_core_shared/schema/fields.json` —— **产物字段**层（23,405 条，本目录）

确需新增引擎接口 → 补进 `tools/build-data-inventory.py` 的 `WISH_LIST` → `--update-baseline`（进 git diff = 留痕）。

## 重新生成

```bash
python 0_core_shared/build-fields-index.py           # 生成 fields.json
python 0_core_shared/build-fields-index.py --check   # 只看统计，不写盘
```

来源：`TPF2_MCP_MOD_DIR` 环境变量，或其下的 `bridge/`。
若游戏在跑，产物是实时的；若没跑，读到的是上次留下的。

## 已知问题

`bridge/` 里有 5 个非 JSON 残留（解析失败，未被索引）：
`newtest.json`、`probe-absolute.json`、`probe-write.json`、`probe2.json`、`write-test.json`
—— 疑似早期测试留下的残缺文件，可考虑清理。
