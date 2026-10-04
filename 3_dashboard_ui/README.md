# 3 表现层（dashboard ui）

**干什么**：渲染 + 收指令。

| 允许 | 🔴 禁止 |
|---|---|
| 画图、交互、查表渲染 | **核心计算**（图遍历、判据、规划） |
| 收集用户指令（点击、勾选、批准） | 直接执行任何游戏操作 |
| 产出 `approved_actions.json`（批准的通行证） | 自己判断"该不该做" |

## 现状（尚未搬迁）

| 实际位置 | 内容 |
|---|---|
| `ui/rail-map/`（19 个源码文件 + 资产） | 全部前端 |
| `tools/serve-rail-map.py` | HTTP 服务（把 bridge 产物切块成 `layers/*.json`） |
| `mcp_server/start_ui.py`、`station_preview.py` | 启动壳、车站预览图 |

## 搬迁后要做的

- `3_dashboard_ui/rail-map/`（前端）＋ `3_dashboard_ui/server/`（服务）
- **`shared/layer-shell.js`**：消掉 5 个图层各写一份的 `buildPanel`
- **`shared/geo.js`**：消掉 `app.js` ↔ `network-app.js` 的 5 个重复画图函数
- **`approved_actions.json` 闸门**：用户点"批准"才写得出来，4 层只认它

⚠️ `ui/rail-map/` 被 `rail-map-service.pyw` 的 `UI_DIRECTORY` 指着 —— 搬它要同步改 `.pyw`。
⚠️ 改了静态文件**必须提 `index.html` 里的 `?v=`**，否则浏览器吃缓存。
