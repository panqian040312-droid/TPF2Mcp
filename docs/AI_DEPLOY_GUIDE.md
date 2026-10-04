# 用 AI 部署这个 Mod —— 给 AI 助手的说明书

> **目标读者是 AI 助手**（人把这份文档丢给你，你照着做即可）。
> 人也可以直接照做 —— 步骤是一样的，只是这份写得更"可执行"。
>
> 前置：**Windows** + **Steam 版 Transport Fever 2** + **Python 3.11 或更高**（无第三方依赖）。

---

## 0. 一句话

把仓库里的 `tpf2_mod/res` 整棵复制到**游戏的 Mod 目录**，然后让 `mcp_server/` 以 MCP 服务方式跑起来；
游戏开着的时候，Mod 会把游戏数据写进 `bridge/`，MCP 服务和地图 UI 都从那里读。

🔴 **关于 DLL 注入 —— 读和写是两条不同的路，别混：**

- **只读采集**（图层数据、诊断）**不走注入**：Mod 往 `<Mod 根>/bridge/` 写 JSON、读命令文件，
  Python 侧读写同一个目录，Mod 在引擎的 update 回调里取走 —— 纯文件轮询，**不需要管理员权限**。
- **在游戏内执行操作**（加车 `buyVehicle` / 改线路 `setLine` / 调速度 `setGameSpeed`）走的是
  **远程线程注入**：把 `tpf2_control.dll` 注入 Transport Fever 2 进程。**介意 DLL 注入请勿使用本项目。**
  当前 `allow_write_operations=false`（只读为主），**这一条通道尚未在本机启用与验证**。

⚠️ 给 AI：**不要因为仓库里找不到 `.dll` 就说"本项目不需要注入"** —— DLL 是二进制，本来就不进仓库
（`.gitignore` 也不该让它进），"仓库里没有文件"**推不出**"运行时不需要注入"。要用写操作，
先向人确认 DLL 的获取方式与安装位置，再动手。

---

## 1. 三个路径先分清（最容易搞错的地方）

| 概念 | Steam 默认位置 | 说明 |
|---|---|---|
| **仓库** | 你 clone/解压的地方 | 只读源码，游戏不认 |
| **Mod 根目录** | ① 创意工坊：`…\steamapps\workshop\content\1066780\<mod_id>\`<br>② 本地开发：`…\steamapps\userdata\<SteamID>\1066780\local\staging_area\<任意名>\` | **游戏只认这里**。`res/`、`mod.lua` 必须在**这一层** |
| 游戏本体 | `…\steamapps\common\Transport Fever 2\` | 只作参考（原版素材在这里），**不要往里塞东西** |

怎么找：

- `1066780` = Transport Fever 2 的 Steam AppID，**固定值**，不用找。
- `<SteamID>`：`…\steamapps\userdata\` 下那个**纯数字目录**（只有一个就对了；多个账号时取最近修改的）。
- Mod 根目录里必须能直接看到 `res\` 和 `mod.lua` —— 看不到就是复制多了一层或少了 `res`。

---

## 2. 安装（三步）

### 2.1 放 Mod 文件

把 `tpf2_mod\res` 的**全部内容**复制到 `<Mod 根>\res\`（**保持 `res` 这一级**），
再把 `tpf2_mod\mod.lua`、`tpf2_mod\strings.lua` 复制到 `<Mod 根>\`。

或者用仓库根的部署脚本（**先改成你自己的路径**，见 §6）：

```bat
deploy_mod_layers.bat
```

它用 robocopy 做整目录同步（`/E` **只复制不删除**，故意保住 `<Mod 根>\res\scripts\tpf2_mcp\local_config.lua`
这种本机私有配置），末尾会自检并打印 `[OK] res\ is fully in sync`。

> 🔴 **复制之前必须完全退出 Transport Fever 2。**
> 游戏运行时这些文件被占用，复制会报「拒绝访问 / 错误 5 / PermissionError」，而且**部分是复制成功的**
> （新建的文件能进去、覆盖既有文件的失败）—— 这会造成"改了没生效"的假象。**先退游戏，再复制。**

### 2.2 让游戏加载它

- 创意工坊包：订阅后自动出现在 Mod 列表
- 本地目录：在游戏里启用 `tpf2mcp`

> 🔴 **TPF2 只在"启动游戏"时读一次 Mod 脚本。** 改完 Lua 必须**完全退出游戏再启动**；
> 在已运行的实例里读档**不会**重新加载。判断"生效没有"要看产物内容（新字段、`note` 版本号），
> **不能只看文件时间戳**。

### 2.3 起 MCP 服务

Python **3.11+**，**不需要装任何包**（`mcp_server/requirements.txt` 里没有第三方依赖）。

MCP 客户端配置示例（WorkBuddy 是 `~/.workbuddy/mcp.json`，Claude Desktop 是 `claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "tpf2": {
      "command": "python",
      "args": ["<Mod 根>/mcp_server/start_server.py"],
      "env": { "TPF2_MCP_MOD_DIR": "<Mod 根>" }
    }
  }
}
```

关于 `TPF2_MCP_MOD_DIR`：

- `start_server.py` **会自己**把 `TPF2_MCP_MOD_DIR` 设成它的**上一级目录** —— 但仅当上一级里存在
  `res/scripts/tpf2_mcp/runtime.lua`。**所以把 `mcp_server/` 放在 Mod 根里面时，`env` 可以省。**
- 服务放在 Mod 根**外面**时，`TPF2_MCP_MOD_DIR` **必须显式给**，否则会 `FileNotFoundError`。

### 2.4 起地图 UI（可选，但强烈建议）

```bat
python "<Mod 根>\mcp_server\start_ui.py"
```

然后浏览器打开 `http://127.0.0.1:8790/`。
仓库根的 `start_rail_map.bat` 是同一件事的快捷方式（同样要先改路径）。

---

## 3. 验证（照着做，别跳步）

1. **启动游戏 → 读档 → 保持运行，不要暂停。** 慢速 1x 就够。
   （命令轮询挂在引擎的 `update` 回调上，**暂停时回调不跑**，此时发什么命令都没反应。）
2. 看 `<Mod 根>\bridge\heartbeat.json`：
   `game_running` 应为 `true`，`last_update` 应**每约 2 秒前进**。
   不动 = 游戏没在跑 / 没在推进 / bridge 路径不对。
3. 调一次 `get_game_state`（设 `force_refresh: true`）→ 应返回城镇/产业/车站/线路/车辆的 counts。
4. 等 1–2 分钟，`<Mod 根>\bridge\` 里会陆续出现 `layer-*.json`
   （`terrain` 最慢：整张地形图分帧采，要跑一阵）。

---

## 4. 目录说明

| 路径 | 作用 |
|---|---|
| `<Mod 根>\res\` | Mod 本体（Lua 采集器/探针）。**改这里** |
| `<Mod 根>\bridge\` | **运行时通信目录**：Mod 写产物、Python 读；Python 写命令、Mod 取走。**别删** —— 删了要重启游戏才会重建 |
| `<Mod 根>\mcp_server\` | MCP 服务 + 地图 UI 服务端 |
| `<Mod 根>\ui\rail-map\` | 前端静态文件（地图页面），由 UI 服务提供 |
| 仓库根 `analyze_*.py` / `check_*.py` / `*probe*.py` | **开发期的一次性分析脚本**，部署**不需要**。别被这一坨吓到 |
| 仓库根 `tools\` | 生成数据用的工具（图标、配方、几何、拥堵数据）。只有 `export-layer-map.py`、`serve-rail-map.py` 是运行时需要的 |

---

## 5. 🔴 坑清单（按踩到的频率排）

1. **改 Lua 后必须完全重启游戏**。读档不算。
2. **游戏运行时不要复制/覆盖 Mod 文件**。占用 → 错误 5；且**新建能成、覆盖失败**，制造假象。
3. **`bridge/` 不是缓存**，是通信目录。清它 = 断链。
4. 改了服务端 Python 或前端资源后，**要重启 UI 服务**；浏览器**要强刷**（页面里脚本带版本号查询串）。
5. **时间量以游戏内时间为准**。实测挂钟 ÷2.09 ≈ 游戏时间，且随负载波动 —— 别用挂钟算游戏里的耗时。
6. 🔴 **读引擎字段有三条路，少走一条就漏数据**（本项目最反复的一类坑）：
   - `component["字段名"]` —— 常规 getter 路径；
   - `pairs(component)` —— 有些字段**只有这条**能拿到（如 `TOWN.name`）；
   - `game.interface.getEntity(id)` 的**聚合表** —— 另一些字段**只在那里**（如 `TOWN.position`、`BASE_EDGE_STREET.streetType`）。
   另外 **`pairs(api.type.ComponentType)` 枚举不出组件清单**；要问"这个实体挂了哪些组件"，
   只能照常量名逐个 `getComponent` 试（现成表在 `res/scripts/tpf2_mcp/collectors/common.lua`）。
7. 前端加图层：挂地图层用 `P()/T()`；要"固定屏幕尺寸"的标记必须挂 `svg` 根 + `screenPoint()` + 每帧回调；
   **不要用 `requestAnimationFrame` / `setInterval` 重绘**（会跟地图错开一帧，拖动时滞后）。
8. `<Mod 根>\res\scripts\tpf2_mcp\local_config.lua` 是**本机私有配置，不要覆盖**。
9. `bridge/` 里的东西是**周期快照**，不是实时流：`layer-*` 按固定帧数间隔采集。
   要最新数据得等下一轮，或者用命令触发（`get_game_state` 带 `force_refresh`）。

---

## 6. 换机器必须先改的两处路径

仓库根这两个脚本里写死了开发机的路径（`E:\workbody\TPF2Mcp` 和某个 Steam 用户 ID）：

- `deploy_mod_layers.bat` —— 里面的 `PROJ` 与 `STAGE` 两个变量
- `start_rail_map.bat` —— 同理

**换机器第一件事就是改这两个变量**，否则脚本会往不存在的目录复制、或者让 UI 服务读错地方。

---

## 7. 写操作与 DLL 注入（当前未启用）

**读和写是两条不同的路，别混：**

| | 通道 | 需不需要注入 |
|---|---|---|
| **只读采集**（图层数据、诊断） | Mod 读写 `<Mod 根>/bridge/` 下的 JSON，纯文件轮询 | ❌ 不需要 |
| **游戏内执行操作**（加车 / 改线路 / 调速度） | **远程线程注入** —— 把 `tpf2_control.dll` 注入游戏进程 | ✅ 需要 |

- 当前 `allow_write_operations = false`，**写通道默认关闭** —— 按本文档装好之后是**能读、不能写**。
  这**不影响**只读能力和地图 UI。
- 🔴 **仓库里找不到 `.dll` 是正常的** —— 二进制不进版本库。**不要因为搜不到文件就断定"本项目不需要注入"**；
  "仓库里没有文件"**推不出**"运行时不需要注入"。
- ⚠️ **本项目当前处于 mod 开发阶段**（以只读能力为主），写操作留待后续启用。本机**尚未装这个 DLL、
  开关也是 false**，所以本文档**没有可照抄的注入步骤** —— 这一步请向项目作者确认获取方式与安装位置，
  **不要自己猜、也不要自己写一个注入工具**。

---

## 8. 出问题时的最小排查顺序

```
① 心跳在动吗？           → bridge/heartbeat.json 的 last_update，每 ~2s 应前进
② 游戏在跑且没暂停吗？    → 暂停时引擎 update 回调不跑，采集器和命令都停
③ Mod 真加载了吗？        → 看 bridge/ 有没有 layer-*.json 产出，而不是看时间戳
④ 是"改了没生效"吗？      → 完全退出游戏，重新启动，再看产物里的新字段
⑤ Mod 根路径对吗？        → <Mod 根> 下应直接看到 res\ 和 mod.lua
⑥ Python 找得到 Mod 吗？  → 服务在 Mod 根外面时必须给 TPF2_MCP_MOD_DIR
```
