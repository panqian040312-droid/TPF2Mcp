# 1 采集层（data collection）

**干什么**：只读 + 导出。把引擎里的东西变成外面能读的文本。

| 允许 | 🔴 禁止 |
|---|---|
| 读引擎对象（组件、实体、引擎函数） | **业务判据**（什么算堵 / 缺货 / 该加车） |
| 为导出而做的**机械整理**（聚合、并集、反解坐标） | 引入**阈值 / 权重 / 判断** |
| 写 `bridge/*.json` | 向上要数据、碰游戏状态 |

判据一句话：**这段代码里有没有出现一个数字，它的取值需要人来拍板？** 有 → 越界。

## 现状（尚未搬迁）

| 实际位置 | 内容 |
|---|---|
| `tpf2_mod/res/scripts/tpf2_mcp/collectors/` | 9 个图层采集器 + 领域读取器 + 探针 |
| `tools/export-*.py`、`build-*.py`、`extract-*.py` | 离线导出器（桥数据 → 前端数据） |
| `mcp_server/src/tpf2_mcp/bridge.py`、`snapshot.py`、`save_scope.py` | 桥读取端 |

## 搬迁后

`1_data_collection/`（Python 侧）＋ `tpf2_mod/res/scripts/tpf2_mcp/1_data_collection/`（Lua 侧）。

⚠️ Lua 侧**只能在 `res/scripts/tpf2_mcp/` 内部建子目录** —— 引擎按 `require "tpf2_mcp/…"` 加载，入口路径写死。

详见 `0_core_shared/ARCHITECTURE.md` § 四。
