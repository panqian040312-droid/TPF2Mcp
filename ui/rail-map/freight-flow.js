// 产业链流向渲染器（freight-flow.js）
//
// 干什么：在地图上把「产业 ↔ 车站」的货物拉动关系画出来。
//   选中一个产业 → 把它的下游去向（橙色）和上游来料（青色）画成线；
//   线的起点是产业的世界坐标，终点是那批货要下车/装车的**车站**坐标。
//
// 为什么单独一个文件：这是给地图加的一块"扩展图层"，只读主文件暴露的 window.TPF2Map，
// 不改 network-app.js / index.html / network.css 里任何已有代码 —— 两边是两拨代码，
// 互相不知道对方内部状态，只能靠 TPF2Map 这层最小接口对接。
//
// 几个关键取舍（为什么这么写）：
//   1) 流向线**必须**挂在 mapLayer 里、坐标必须过 P()。
//      mapLayer 带着 SVG transform 跟着地图缩放平移，挂进去的内容自动跟随；
//      挂 svg 根 + screenPoint 的话一缩放线就跑到地图外面去了。
//   2) 产业高亮标记反过来**必须**用屏幕坐标：世界坐标里画个 r=5 的圆，缩到 20% 只剩 1 像素，
//      全图看不见（和主文件里车站点标记一个道理）。所以标记走 onViewport 每帧重算屏幕位置；
//      流向线只在"选中变化 / 开关变化"时重画一次，不拿 rAF / setInterval 空转。
//   3) 数据量：4330 条边，每条边还带最多 8 个车辆 id / 8 条线路 id。
//      所以默认只画选中产业相关的那几十条，且封顶 N 条（面板可调）；
//      同色同粗细的线合并进一条 <path>（多个 "M..L.." 直接拼接是合法 SVG），
//      最多 8 条 path，而不是几千个 DOM 元素。
(function () {
  'use strict';

  // 货种字典。数据里 cargo_type 是 "1".."16" 的数字字符串。
  // 中文名和图标来自 /cargo-types.json（由 tools/build-cargo-types.py 生成，
  // 源头是引擎的 cargoTypeRep，图标是游戏 ui.zip 里的原版 hud/cargo_*）。
  // 表没加载上时退化成「货种 14」这种，不至于空着。
  var CARGO_NAME = {};      // "14" → "工具"
  var CARGO_BY_KEY = {};    // "TOOLS" → { id, key, zh, icon }（配方里用的是这种英文键名）

  var DIR_DOWN = 'down';   // 下游：这个产业把货送出去
  var DIR_UP = 'up';       // 上游：别人把货送进这个产业

  var COLOR_DOWN = '#ffb347';   // 橙：下游去向
  var COLOR_UP = '#4fd1ff';     // 青：上游来料
  var COLOR_SELF = '#ff4d6d';   // 红：选中产业自己

  // 货量分档。实测货量极度倾斜：中位数才 2、90 分位才 5、最大 5.47 万，
  // 所以按数量级分档；线性等分的话 99% 的线会全部挤在最细那一档，看不出差别。
  var TIERS = [
    { min: 1000, width: 3.6, opacity: 0.85 },
    { min: 100, width: 2.4, opacity: 0.60 },
    { min: 10, width: 1.5, opacity: 0.42 },
    { min: 0, width: 0.9, opacity: 0.26 }
  ];

  var LIMIT_CHOICES = [50, 200, 0];   // 0 = 不封顶（选中产业最多也就三百来条，但仍要提示"可能卡"）
  var DEFAULT_LIMIT = 200;
  var MAX_PARTNER_MARKS = 30;   // 上下游各最多标 30 个产业，防止一屏几百个标签糊成一片
  var MAX_ROWS = 80;            // 明细面板最多列 80 行，剩下的用一句"还有 X 条"带过
  // 面板底部那行提示的默认文案。选中 / 清除 / 数据异常时会临时改写，
  // 清掉选择就写回这一句（不然用户只看到一句"已选中…"，就再也找不到操作提示了）。
  var HINT_DEFAULT = '直接点地图上的产业图标也能选中；线越粗=货量越大，橙=下游去向，青=上游来料';

  // 所有函数共用一个上下文。用显式对象而不是各写各的闭包变量，
  // 是为了避免"面板的开关回调拿不到 boot 里的局部变量"这类作用域坑。
  var ctx = {
    api: null, state: null, ui: null, detail: null,
    board: null, lineGroup: null, markGroup: null
  };

  // 主文件在 renderRailNetwork() 跑完才挂 window.TPF2Map 并广播 'tpf2map:ready'。
  // 两种都要照顾：① 我们比主文件晚加载 → 事件还没发，监听它；
  //             ② 我们比主文件早加载 / 被动态注入 → TPF2Map 已经在了，直接用。
  // 不用轮询：主文件注释里明确写了别轮询。
  if (window.TPF2Map) {
    boot(window.TPF2Map);
  } else {
    window.addEventListener('tpf2map:ready', function () { boot(window.TPF2Map); }, { once: true });
  }

  function boot(api) {
    if (!api || ctx.api) return;   // 防重复初始化

    ctx.api = api;
    ctx.state = {
      links: [],            // 4330 条流向（源数据格式）
      lines: [],            // 271 条线路（我们要的是里面的 stops）
      lineById: new Map(),  // entity_id → 线路
      // 线路 id → {spans, points}：**真实轨道几何**。
      // 来源 = `rail-network-data.json` 的 `route_edge_ids`，经 network-app 的
      // `railRoutePaths()` 拿到（那个 6.4 MB 与"线路高亮"共用缓存，只拉一次）。
      // 没有它就只能退回"站点之间的直线"—— 用户 2026-10-03 一眼看出不对：
      // 「交通线还没有高亮，是还没做吗」（直线不像铁路）。
      railPaths: new Map(),
      railPathsPending: null,   // 正在请求的线路 id 串，防重复请求
      industries: [],       // 215 个产业：{id, name, x, y}
      industryById: new Map(),
      degree: new Map(),    // 产业 id → 挂了几条边（列表项上顺手显示，帮用户先挑大的看）
      query: '',            // 产业列表搜索词
      selected: null,       // 当前选中的产业 id
      showLines: true,
      showMarks: true,
      limit: DEFAULT_LIMIT,
      edges: [],            // 选中产业相关的边：{link, dir}
      markerViews: []       // 屏幕坐标标记：{group, position}
    };

    // 「最多显示」也跟着记忆走 —— 它不是 addOption，面板那套自动记忆接不到，得单独接。
    // 键按同一套规则拼（分组名/条目名），跟面板里其它项一致。
    if (window.TPF2UIState) {
      var savedLimit = window.TPF2UIState.get('产业链/最多显示', null);
      if (typeof savedLimit === 'number' && LIMIT_CHOICES.indexOf(savedLimit) >= 0) {
        ctx.state.limit = savedLimit;
      }
    }

    ctx.board = document.querySelector('#board-wrap');
    if (!ctx.board) { console.error('[地图] 产业链：找不到 #board-wrap，放弃'); return; }

    // 两块画布：流向线挂 mapLayer（跟着缩放），高亮标记挂 svg 根（固定屏幕尺寸）。
    ctx.lineGroup = api.S('g', { id: 'freight-flow-lines', 'pointer-events': 'none' }, '', api.mapLayer);
    ctx.markGroup = api.S('g', { id: 'freight-flow-marks', 'pointer-events': 'none' }, '', api.svg);

    ctx.ui = buildPanel();
    ctx.detail = buildDetailPanel();

    // 地图上点产业图标 → 跟点列表项走**同一条路**（用户 2026-10-02：
    // 「我不想在左边的栏里面选，我根本不知道是哪一个，我要在地图上直接点击」）。
    // 用事件广播解耦：产业图标层和这一层各自监听 tpf2map:ready，谁先加载说不准。
    window.addEventListener('tpf2industry:select', function (event) {
      var id = event && event.detail ? event.detail.id : null;
      if (id == null) return;
      if (!ctx.state.industryById.has(id)) {
        // 图上点到的产业不在这份产业链数据里 —— 说明两份产物不同源（旧切块），
        // 别静默忽略，说清楚，不然用户只会觉得"点了没反应"。
        // 🔴 2026-10-02：原来只 `console.warn`，用户根本看不到控制台，等于**静默失败**。
        //    改成同时写进面板底部那行提示。
        var text = '图上点到的产业 ' + id + ' 不在这份产业链数据里（两份产物可能不同源），已忽略';
        console.warn('[地图] 产业链：' + text);
        if (ctx.ui) ctx.ui.setHint(text);
        return;
      }
      selectIndustry(id);
      // 点了给一句明确回执 —— 否则用户分不清"选中了"和"压根没响应"
      if (ctx.ui) ctx.ui.setHint('已选中「' + ctx.state.industryById.get(id).name + '」');
      if (event.detail.source === 'map') ctx.ui.revealSelected();
    });

    // 每帧只重算"屏幕标记"的位置，不重建任何东西。
    api.onViewport(function () { paintMarks(); });

    load();
  }

  // ---- 取数据 ------------------------------------------------------------
  async function load() {
    var freight, lines, overview, cargoTypes, recipes;
    var optionalJson = function (url) {
      // 字典和配方缺了不该让整层挂掉 —— 取不到就退化成"没有这部分信息"。
      return fetch(url, { cache: 'no-store' })
        .then(function (response) { return response.ok ? response.json() : null; })
        .catch(function () { return null; });
    };
    try {
      var results = await Promise.all([
        ctx.api.fetchLayer('freight'),
        ctx.api.fetchLayer('lines'),
        fetch('/layers/industry-overview.json', { cache: 'no-store' }).then(function (response) {
          if (!response.ok) throw new Error('industry-overview ' + response.status);
          return response.json();
        }),
        optionalJson('/cargo-types.json'),
        optionalJson('/industry-recipes.json')
      ]);
      freight = results[0];
      lines = results[1];
      overview = results[2];
      cargoTypes = results[3];
      recipes = results[4];
    } catch (error) {
      console.error('[地图] 产业链：数据加载失败', error);
      if (ctx.ui) ctx.ui.setHint('数据加载失败，详见控制台');
      return;
    }

    // 货种字典：数字 id → 中文名（流向明细里 cargo_type 是数字串）；
    // 英文键名 → 整条记录（配方里的原料/产品用的是 IRON_ORE 这种键名）。
    ((cargoTypes && cargoTypes.types) || []).forEach(function (item) {
      CARGO_NAME[String(item.id)] = item.zh;
      CARGO_BY_KEY[item.key] = item;
    });
    ctx.state.recipes = (recipes && recipes.industries) || {};

    var state = ctx.state;
    state.links = (freight.data && freight.data.links) || [];
    state.lines = (lines.data && lines.data.lines) || [];
    state.lineById = new Map(state.lines.map(function (line) { return [line.entity_id, line]; }));

    // industry-overview 每个点是一行数组：
    //   [x, y, level, 产业id, 名字, extent.x, extent.y, 厂内货量, 升级进度]
    // 第 3 个元素是**产业等级**（实测 0/1/2/3）；最后两个是后来补的 ——
    // 老切块里没有，取到 undefined 就当"没有这个信息"，不是 0。
    state.industries = ((overview && overview.points) || []).map(function (row) {
      return {
        id: row[3],
        name: row[4] || ('产业 ' + row[3]),
        x: row[0], y: row[1],
        level: row[2],
        stockCount: row[7],          // 厂里现在有多少件货（实时，数实体得到的）
        upgradeProgress: row[8],
      };
    }).sort(function (a, b) { return String(a.name).localeCompare(String(b.name), 'zh-CN'); });
    state.industryById = new Map(state.industries.map(function (item) { return [item.id, item]; }));

    // 每个产业挂了几条边。一遍扫完比"选中时再过滤"更省，而且列表上能直接显示。
    state.degree = new Map();
    state.links.forEach(function (link) {
      [link.source_industry, link.target_industry].forEach(function (id) {
        if (id == null) return;
        state.degree.set(id, (state.degree.get(id) || 0) + 1);
      });
    });

    reportCoverage();
    ctx.ui.renderList();
  }

  // ---- 自检日志 ----------------------------------------------------------
  // 顺便把"数据到不到位"讲清楚：这份 freight 如果是旧切块（没有 stopovers），
  // 流向线一条都定位不到终点 —— 与其让用户对着空白地图猜，不如日志里直说。
  function reportCoverage() {
    var links = ctx.state.links;
    var total = links.length;
    var toIndustry = 0;
    links.forEach(function (link) { if (link.target_kind === 'industry') toIndustry += 1; });
    console.log('[地图] 产业链：' + total + ' 条流向，其中厂→厂 ' + toIndustry + ' 条、厂→城镇 ' + (total - toIndustry) + ' 条');

    var withStops = 0;
    links.forEach(function (link) { if (link.stopovers && link.stopovers.length) withStops += 1; });
    if (total && !withStops) {
      console.warn('[地图] 产业链：这批 freight 数据里没有任何 stopovers（磁盘上可能是旧切块）。'
        + '没有 stopovers 就定位不到装货车站，流向线会全部跳过 —— 等图层重新导出后即可显示。');
    } else if (total - withStops) {
      console.log('[地图] 产业链：' + (total - withStops) + ' 条流向还没上车（没有 stopovers），画线时跳过');
    }

    // 线路这边也一样：落盘的 lines 切块如果没有 stops，dest_stop 就取不到车站坐标。
    var lines = ctx.state.lines;
    var linesWithStops = 0;
    lines.forEach(function (line) { if (line.stops && line.stops.length) linesWithStops += 1; });
    if (lines.length && !linesWithStops) {
      console.warn('[地图] 产业链：这 ' + lines.length + ' 条线路都没有 stops（磁盘上可能是旧切块），'
        + '流向线定位不到终点站，会全部跳过 —— 等线路图层重新导出后即可显示。');
    }
  }

  // ---- 面板 --------------------------------------------------------------
  function buildPanel() {
    var state = ctx.state;
    // 自建一个分组，别和别的扩展挤在「设施」里（2026-09-30：曾和站点结构挤在一起，界面糊成一团）。
    var group = ctx.api.panel && typeof ctx.api.panel.addGroup === 'function'
      ? ctx.api.panel.addGroup('产业链')
      : (ctx.api.panel.groups && ctx.api.panel.groups.facility);
    if (!group) {
      console.warn('[地图] 产业链：拿不到 facility 分组，跳过面板');
      return { renderList: noop, setHint: noop };
    }

    // 两个开关走面板自带的 addOption —— 样式和主文件其它开关天然一致，不用我们造样式。
    ctx.api.panel.addOption(group, '流向线', {
      checked: true,
      count: state.links.length || null,
      title: '选中产业后，把它相关的流向画成线：起点是产业坐标，终点是货要下车/装车的车站（橙=下游去向，青=上游来料）',
      onChange: function (value) { state.showLines = value; renderLines(); }
    });
    ctx.api.panel.addOption(group, '上下游高亮', {
      checked: true,
      title: '把相关的上游 / 下游产业在地图上标出来（固定屏幕尺寸的点，缩放不会缩没）',
      onChange: function (value) { state.showMarks = value; paintMarks(); }
    });

    // 「最多显示」用原生 select：addOption 只有勾选框，塞不下三档。
    var limitLabel = el('label', rowStyle());
    limitLabel.appendChild(el('span', { color: '#7ee6ff' }, '最多显示'));
    var limitSelect = document.createElement('select');
    limitSelect.style.cssText = 'background:#07131e;color:#7ee6ff;border:1px solid #3a6178;border-radius:2px;font:11px Consolas;padding:1px 3px';
    LIMIT_CHOICES.forEach(function (value) {
      var option = document.createElement('option');
      option.value = String(value);
      option.textContent = value === 0 ? '全部（可能卡）' : (value + ' 条');
      if (value === state.limit) option.selected = true;
      limitSelect.appendChild(option);
    });
    limitSelect.addEventListener('change', function () {
      state.limit = Number(limitSelect.value) || 0;
      if (window.TPF2UIState) window.TPF2UIState.set('产业链/最多显示', state.limit);
      renderLines();
    });
    limitLabel.appendChild(limitSelect);
    group.appendChild(limitLabel);

    // 可搜索、可滚动的产业列表。这一块面板自带的 addOption 做不了，只能自造 DOM。
    var search = document.createElement('input');
    search.type = 'search';
    search.placeholder = '搜产业名…';
    search.style.cssText = 'width:100%;box-sizing:border-box;background:#07131e;color:#eaf9ff;'
      + 'border:1px solid #3a6178;border-radius:2px;font:12px Consolas,"Microsoft YaHei";padding:3px 5px;cursor:text';
    group.appendChild(search);

    var list = document.createElement('div');
    list.style.cssText = 'max-height:170px;overflow:auto;overscroll-behavior:contain;'
      + 'border:1px solid #1d3346;border-radius:2px;padding:2px;margin-top:2px';
    group.appendChild(list);

    var clear = document.createElement('button');
    clear.type = 'button';
    clear.textContent = '清除选择';
    clear.style.cssText = 'align-self:flex-start;height:20px;padding:0 8px;background:#102535;color:#7ee6ff;'
      + 'border:1px solid #3a6178;border-radius:2px;font:11px Consolas;cursor:pointer';
    clear.addEventListener('click', function () { selectIndustry(null); });
    group.appendChild(clear);

    var hint = el('div', { color: '#6f8ea3', font: '10px Consolas', whiteSpace: 'normal' },
      HINT_DEFAULT);
    group.appendChild(hint);

    search.addEventListener('input', function () {
      state.query = search.value || '';
      renderList();
    });

    // 列表项很多（最多 215 个）。只在搜索词 / 选中项变化时重建，不做每帧更新。
    var selectedRow = null;      // 当前选中那一行 —— 在图上点中后要把它滚进视野
    function renderList() {
      selectedRow = null;
      var query = state.query.trim().toLowerCase();
      var matched = state.industries.filter(function (item) {
        return !query || String(item.name).toLowerCase().indexOf(query) >= 0;
      });
      var fragment = document.createDocumentFragment();
      matched.forEach(function (item) {
        var selected = state.selected === item.id;
        var row = el('div', {
          display: 'flex', justifyContent: 'space-between', gap: '6px',
          padding: '2px 5px', borderRadius: '2px', cursor: 'pointer',
          font: '12px Consolas,"Microsoft YaHei"',
          color: selected ? '#eaf9ff' : '#9fe8ff',
          background: selected ? '#15445f' : 'transparent'
        });
        row.appendChild(el('span', { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, item.name));
        var degree = state.degree.get(item.id) || 0;
        row.appendChild(el('span', { color: '#6f8ea3', flexShrink: '0' }, degree ? degree + ' 条' : '—'));
        row.title = item.name + '（产业 ' + item.id + '）';
        row.addEventListener('click', function () { selectIndustry(item.id); });
        if (selected) selectedRow = row;
        fragment.appendChild(row);
      });
      if (!matched.length) {
        fragment.appendChild(el('div', { color: '#6f8ea3', font: '11px Consolas', padding: '3px 5px' }, '没有匹配的产业'));
      }
      list.replaceChildren(fragment);
    }

    // 在图上点中产业后，把列表里对应的那一行滚进视野 ——
    // 用户本来就说"在列表里根本不知道是哪一个"，点完能看到它在列表的哪儿，比只高亮更有用。
    function revealSelected() {
      if (selectedRow && typeof selectedRow.scrollIntoView === 'function') {
        selectedRow.scrollIntoView({ block: 'nearest' });
      }
    }

    return {
      renderList: renderList,
      revealSelected: revealSelected,
      setHint: function (text) { hint.textContent = text; }
    };
  }

  // ---- 选中一个产业 ------------------------------------------------------
  function selectIndustry(id) {
    var state = ctx.state;
    state.selected = id;
    state.edges = collectEdges(id);
    rebuildMarks();
    renderLines();
    if (id == null) {
      // 清除选择：把明细浮层整个收起来。只清空内容会让上一次的残留内容留在屏幕上，
      // 让人以为还在看某个产业。
      if (ctx.detail) { ctx.detail.setFoot(''); ctx.detail.hide(); }
      if (ctx.ui) ctx.ui.setHint(HINT_DEFAULT);
    } else {
      renderDetail();
    }
    if (ctx.ui) ctx.ui.renderList();   // 把列表里的选中项点亮（重建列表，215 个 div 很便宜）
  }

  // 选中产业的边：**沿产业链两端逐层展开**，不是只取直接上下游。
  // 用户 2026-10-03 反馈：「只有一级上下游而不是全产业链」。
  //   上游（DIR_UP）  = 别人发给我的货（target_industry 是我）→ 继续找它的发货方
  //   下游（DIR_DOWN）= 我发出去的货（source_industry 是我）→ 继续找它的收货方
  // 上下两个方向各走一遍，方向始终相对**根节点**（不是相对中间节点），
  // 上层画上游色、下层画下游色才说得通。
  // ⚠️ 两层上限兜底：这是 4468 条边的图，链条长了会爆。
  var CHAIN_MAX_DEPTH = 6;
  var CHAIN_MAX_EDGES = 600;

  function collectEdges(id) {
    var state = ctx.state;
    if (id == null) return [];
    var edges = [];
    var seen = new Set();

    function walk(root, dir) {
      if (edges.length >= CHAIN_MAX_EDGES) return;
      var visited = new Set([root]);
      var frontier = new Set([root]);
      for (var depth = 0; depth < CHAIN_MAX_DEPTH; depth += 1) {
        if (!frontier.size || edges.length >= CHAIN_MAX_EDGES) return;
        var next = new Set();
        state.links.forEach(function (link) {
          // 上游看 target_industry、下游看 source_industry —— 谁是"我方"取决于方向。
          var mine = dir === DIR_UP ? link.target_industry : link.source_industry;
          var other = dir === DIR_UP ? link.source_industry : link.target_industry;
          if (mine == null || !frontier.has(mine)) return;
          var key = dir + ':' + link.source_industry + '>' + link.target_industry;
          if (!seen.has(key)) { seen.add(key); edges.push({ link: link, dir: dir }); }
          // ≤0 是「无」(-1)：运往城镇的货没有上游产业，链条到此为止。
          if (other != null && other > 0 && !visited.has(other)) {
            visited.add(other);
            next.add(other);
          }
        });
        frontier = next;
      }
    }

    walk(id, DIR_UP);
    walk(id, DIR_DOWN);
    edges.sort(function (a, b) { return (Number(b.link.count) || 0) - (Number(a.link.count) || 0); });
    return edges;
  }

  // ---- 真实铁路几何（按需拉取）--------------------------------------------
  // 把"这批货用到的线路"的轨道几何拉进来。**异步**，拿不到就退回站点连线。
  // 数据是 6.4 MB 的 rail-network-data.json，主文件已经有一套缓存（线路高亮在用），
  // 这里通过 `ctx.api.railRoutePaths()` 借它的缓存，不重复下载。
  var railPathsQueued = '';
  function ensureRailPaths(edges) {
    var state = ctx.state;
    var api = ctx.api;
    if (typeof api.railRoutePaths !== 'function') return;   // 主文件是旧版：不折腾
    var need = [];
    edges.forEach(function (edge) {
      (edge.link.lines || []).forEach(function (id) {
        var key = Number(id);
        if (!Number.isFinite(key) || state.railPaths.has(key)) return;
        if (need.indexOf(key) < 0) need.push(key);
      });
    });
    if (!need.length) return;
    var signature = need.join(',');
    if (railPathsQueued === signature) return;   // 同一批正在路上，别重复发
    railPathsQueued = signature;
    api.railRoutePaths(need).then(function (map) {
      railPathsQueued = '';
      if (!map || !map.forEach) return;
      map.forEach(function (value, key) { state.railPaths.set(Number(key), value); });
      console.log('[产业链] 铁路几何已就绪：' + map.size + ' 条线路可沿真实轨道绘制');
      if (state.selected != null) renderLines();   // 几何到齐，重画
    }).catch(function (error) {
      railPathsQueued = '';
      console.warn('[产业链] 铁路几何加载失败，退回站点连线', error);
    });
  }

  // 这批货在这条线上从哪站上、到哪站下（`stopovers` 里挑属于这条线的那条）。
  function pickStopover(link, lineId) {
    var found = null;
    (link.stopovers || []).forEach(function (candidate) {
      if (found === null && Number(candidate.line) === Number(lineId)) found = candidate;
    });
    return found;
  }

  // ---- 流向线 ------------------------------------------------------------
  function renderLines() {
    var state = ctx.state;
    var lineGroup = ctx.lineGroup;
    if (!lineGroup) return;
    lineGroup.replaceChildren();
    if (!state.showLines || state.selected == null) return;

    var edges = state.limit > 0 ? state.edges.slice(0, state.limit) : state.edges;

    // 铁路几何按需拉取（异步）：到齐后它会自己再调一次 renderLines 重画，这里只管触发。
    ensureRailPaths(edges);

    // 按「方向 × 粗细档」分桶：最多 8 个桶 = 最多 8 条 path，
    // 而不是几千个 <line> —— 这个数据量下唯一撑得住的做法。
    var buckets = new Map();
    var drawn = 0, skipped = 0;

    // 同一条线路会在多个货流里重复出现 —— 按「方向:线路id:区间」去重，
    // 免得同一条线叠画好几遍（叠画会让透明度累加，看着像"特别粗"，其实是重复）。
    var tracedSpans = new Set();
    // 「没走的区间」用中性灰蓝 —— 和上游青 / 下游橙**明显不同色**
    //（用户 2026-10-03：两段要分开着色，好回头查是哪一段出的问题）。
    var REST_COLOR = '#6f8ea3';

    var bucketOf = function (dir, tier, rest) {
      var bucketKey = dir + ':' + tier + (rest ? ':rest' : '');
      var list = buckets.get(bucketKey);
      if (!list) { list = []; buckets.set(bucketKey, list); }
      return list;
    };

    edges.forEach(function (edge) {
      var tier = tierOf(edge.link.count);
      var traced = false;

      // ① 优先画**这批货实际走的那条线路**。
      //    · 铁路线：`state.railPaths` 里有**真实轨道几何**（route_edge_ids → 逐边贝塞尔），
      //      用它才是"沿着铁轨"；并按 `[wait_stop, dest_stop]` 切成「走的」和「没走的」两段。
      //      用户 2026-10-03「交通线还没有高亮」的根因：之前只拿得到站点连线，画出来是直线；
      //      而 rail-network-data.json 里**早就有现成的走行路径**（route_edge_ids）。
      //    · 其余（公路/水运/航空，或还没寻到轨道的少数铁路线）：退回站点连线。
      (edge.link.lines || []).forEach(function (lineId) {
        var key = Number(lineId);
        var geom = state.railPaths.get(key);

        if (geom) {
          traced = true;
          var railKey = edge.dir + ':' + key + ':rail';
          if (tracedSpans.has(railKey)) return;                     // 这条线已经画过
          tracedSpans.add(railKey);

          // 区间切分：拿**每条轨道边的中点**去比上/下车站的世界坐标，取最近的下标。
          // （不能拿 stop 下标直接切 `spans` —— 边的粒度比站细得多。）
          var stopoverForRail = pickStopover(edge.link, key);
          var railStops = (state.lineById.get(key) || {}).stops || [];
          var nearestIndex = function (point) {
            var best = -1, bestGap = Infinity;
            geom.points.forEach(function (mid, index) {
              var gap = Math.hypot(mid.x - point.x, mid.y - point.y);
              if (gap < bestGap) { bestGap = gap; best = index; }
            });
            return best;
          };
          var fromIndex = -1, toIndex = -1;
          if (stopoverForRail) {
            var stopFrom = railStops[Number(stopoverForRail.wait_stop)];
            var stopTo = railStops[Number(stopoverForRail.dest_stop)];
            if (stopFrom) fromIndex = nearestIndex(stopFrom);
            if (stopTo) toIndex = nearestIndex(stopTo);
          }
          var railHasRange = fromIndex >= 0 && toIndex >= 0;
          if (fromIndex > toIndex) { var swapIndex = fromIndex; fromIndex = toIndex; toIndex = swapIndex; }
          geom.spans.forEach(function (spanText, index) {
            var onRoute = railHasRange && index >= fromIndex && index <= toIndex;
            bucketOf(edge.dir, tier, !onRoute).push(spanText);
          });
          return;
        }

        // ② 站点连线（轨道几何还没到位，或这条线没寻到轨道）
        var line = state.lineById.get(key);
        var geometry = line && line.points;
        if (!geometry || geometry.length < 2) return;
        traced = true;

        var last = geometry.length - 1;
        var at = function (index) {
          var screen = ctx.api.P(geometry[index]);
          return screen.x.toFixed(1) + ',' + screen.y.toFixed(1);
        };
        var span = function (from, to) {
          var out = ['M' + at(from)];
          for (var i = from + 1; i <= to; i += 1) out.push('L' + at(i));
          return out.join('');
        };

        // 这批货真正走的区间 = stops 的 [wait_stop, dest_stop]，下标直接可用：
        // 实测 **271/271** 条线的 `points` 与 `stops` 一一对应，
        // 且 4449 个 stopover 的 wait/dest **零越界**。
        var stopover = pickStopover(edge.link, key);
        var from = stopover ? Number(stopover.wait_stop) : NaN;
        var to = stopover ? Number(stopover.dest_stop) : NaN;
        var hasRange = Number.isFinite(from) && Number.isFinite(to)
          && from >= 0 && to <= last && from < to;

        var spanKey = edge.dir + ':' + key + ':' + (hasRange ? from + '-' + to : 'full');
        if (tracedSpans.has(spanKey)) return;                       // 这一段已经画过
        tracedSpans.add(spanKey);

        if (hasRange) {
          bucketOf(edge.dir, tier, false).push(span(from, to));     // 经过段
          if (from > 0) bucketOf(edge.dir, tier, true).push(span(0, from));      // 起点之前
          if (to < last) bucketOf(edge.dir, tier, true).push(span(to, last));    // 终点之后
        } else {
          // 没有区间信息 → 整条算"走的"（退回上一版行为，别让线凭空消失）
          bucketOf(edge.dir, tier, false).push(span(0, last));
        }
      });

      // ② 兜底：线路几何拿不到时，仍旧画「产业 → 目的站」的直线（原来的行为）。
      //    否则这些货流会直接从图上消失 —— 那比画得糙更糟。
      if (!traced) {
        var source = state.industryById.get(edge.link.source_industry);
        if (!source) { skipped += 1; return; }            // 货源地不是产业（或没采到坐标）→ 没有起点，跳过
        var end = stationOf(edge.link);
        if (!end) { skipped += 1; return; }               // 还没上车 / 定位不到车站 → 跳过
        var a = ctx.api.P(source);   // 世界坐标 → 底图坐标（挂 mapLayer 必须走这个）
        var b = ctx.api.P(end);
        bucketOf(edge.dir, tier, false).push(
          'M' + a.x.toFixed(1) + ',' + a.y.toFixed(1) + 'L' + b.x.toFixed(1) + ',' + b.y.toFixed(1));
      }
      drawn += 1;
    });

    // 细线先画、粗线后画，粗的压在上层，免得被细线盖住。
    // 每一档里**先画"没走的区间"**（中性灰、更细更淡，退到背景），
    // 再画"走的区间"压在上面 —— 这样一眼能分出"这条线存在"和"这批货真走它"。
    var paint = function (bucketKey, dir, tierIndex, isRest) {
      var parts = buckets.get(bucketKey);
      if (!parts || !parts.length) return;
      ctx.api.S('path', {
        d: parts.join(''),
        fill: 'none',
        stroke: isRest ? REST_COLOR : (dir === DIR_DOWN ? COLOR_DOWN : COLOR_UP),
        'stroke-width': isRest ? TIERS[tierIndex].width * 0.65 : TIERS[tierIndex].width,
        'stroke-linecap': 'round',
        opacity: isRest ? 0.30 : TIERS[tierIndex].opacity,
        // 地图靠 mapLayer 的 transform:scale(zoom) 缩放；不加这个，线宽会跟着一起放大缩小。
        'vector-effect': 'non-scaling-stroke',
        'pointer-events': 'none'
      }, '', lineGroup);
    };

    for (var t = TIERS.length - 1; t >= 0; t -= 1) {
      [DIR_UP, DIR_DOWN].forEach(function (dir) {
        paint(dir + ':' + t + ':rest', dir, t, true);
        paint(dir + ':' + t, dir, t, false);
      });
    }

    if (ctx.detail) {
      ctx.detail.setFoot('已画 ' + drawn + ' 条'
        + (state.limit > 0 && state.edges.length > state.limit ? '（共 ' + state.edges.length + ' 条，面板上限 ' + state.limit + '）' : '')
        + (skipped ? '；' + skipped + ' 条没有终点站（未上车或线路缺 stops），已跳过' : ''));
    }
  }

  // 终点 = 那批货要下车/装车的车站。
  // 链路：边.stopovers[0] → 用它的 line 找线路 → 用 dest_stop 当下标取 line.stops[dest_stop] → 拿该站 (x,y,z)。
  function stationOf(link) {
    var state = ctx.state;
    var stopover = link.stopovers && link.stopovers[0];
    if (!stopover) return null;                                    // 还没上车，压根没有目的站
    var line = state.lineById.get(stopover.line);
    if (!line || !line.stops || !line.stops.length) return null;    // 线路找不到 / 没采到 stops（旧切块）
    var stop = line.stops[stopover.dest_stop];                      // dest_stop 就是 stops 的下标
    if (!stop) return null;                                        // 下标越界
    return { x: stop.x, y: stop.y, z: stop.z };
  }

  function tierOf(count) {
    var value = Number(count) || 0;
    for (var i = 0; i < TIERS.length; i += 1) { if (value >= TIERS[i].min) return i; }
    return TIERS.length - 1;
  }

  // ---- 产业高亮标记（屏幕坐标，每帧重算位置）------------------------------
  function rebuildMarks() {
    var state = ctx.state;
    var markGroup = ctx.markGroup;
    if (!markGroup) return;
    markGroup.replaceChildren();
    state.markerViews = [];
    if (state.selected == null) return;

    var self = state.industryById.get(state.selected);
    if (self) addMark(self, COLOR_SELF, 5.5, true);

    var upIds = [], downIds = [], seenUp = new Set(), seenDown = new Set();
    state.edges.forEach(function (edge) {
      if (edge.dir === DIR_UP) {
        var id = edge.link.source_industry;
        if (id != null && !seenUp.has(id)) { seenUp.add(id); upIds.push(id); }
      } else if (edge.link.target_kind === 'industry') {
        // 下游只有"送给另一个产业"的才有坐标可标；送给城镇的没有产业点，标不了。
        var id2 = edge.link.target_industry;
        if (id2 != null && !seenDown.has(id2)) { seenDown.add(id2); downIds.push(id2); }
      }
    });

    upIds.slice(0, MAX_PARTNER_MARKS).forEach(function (id) {
      var item = state.industryById.get(id);
      if (item) addMark(item, COLOR_UP, 3.4, false);
    });
    downIds.slice(0, MAX_PARTNER_MARKS).forEach(function (id) {
      var item = state.industryById.get(id);
      if (item) addMark(item, COLOR_DOWN, 3.4, false);
    });
  }

  function addMark(item, color, radius, isSelf) {
    var group = ctx.api.S('g', {}, '', ctx.markGroup);
    if (isSelf) ctx.api.S('circle', { r: radius + 4, fill: 'none', stroke: color, 'stroke-width': 1, opacity: 0.5 }, '', group);
    ctx.api.S('circle', { r: radius, fill: color, stroke: '#061019', 'stroke-width': 1 }, '', group);
    ctx.api.S('text', {
      x: radius + 3, y: 3.2,
      fill: color, 'font-size': isSelf ? 10 : 8.5,
      'font-family': 'Consolas, Microsoft YaHei',
      'paint-order': 'stroke', stroke: '#061019', 'stroke-width': 2.5, 'stroke-linejoin': 'round'
    }, item.name, group);
    ctx.state.markerViews.push({ group: group, position: { x: item.x, y: item.y } });
  }

  // 每帧只干这一件事：把世界坐标换成屏幕坐标，改写 transform。
  // 标记数量有上限（≤61 个），每帧几十次 setAttribute 无所谓。
  function paintMarks() {
    var markGroup = ctx.markGroup;
    if (!markGroup) return;
    if (!ctx.state.showMarks) { markGroup.style.display = 'none'; return; }
    if (markGroup.style.display === 'none') markGroup.style.display = '';
    var views = ctx.state.markerViews;
    for (var i = 0; i < views.length; i += 1) {
      var q = ctx.api.screenPoint(views[i].position);
      views[i].group.setAttribute('transform', 'translate(' + q.x.toFixed(1) + ' ' + q.y.toFixed(1) + ')');
    }
  }

  // ---- 明细浮层 ----------------------------------------------------------
  // 绝对定位在 #board-wrap 里（那个容器主文件已经设成 position:relative）。
  // **不动主侧栏**：主侧栏归主文件管，我们从旁边插一块自己的浮层，互不干扰。
  function buildDetailPanel() {
    var panel = el('div', {
      position: 'absolute', right: '12px', bottom: '12px', width: '372px',
      maxHeight: 'calc(100% - 96px)', display: 'none',
      flexDirection: 'column', gap: '5px', padding: '8px 10px',
      background: '#09131ef2', border: '1px solid #31495e', borderRadius: '3px',
      boxShadow: '0 3px 12px #0008', zIndex: '3', overflow: 'hidden',
      font: '11px Consolas,"Microsoft YaHei"', color: '#cfe9f5'
    });

    var header = el('div', { display: 'flex', alignItems: 'center', gap: '6px' });
    var title = el('div', { flex: '1', font: '12px Consolas,"Microsoft YaHei"', color: '#eaf9ff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, '');
    var close = document.createElement('button');
    close.type = 'button';
    close.textContent = '×';
    close.title = '收起明细（重新选一个产业会再出现）';
    close.style.cssText = 'width:20px;height:20px;background:#102535;color:#7ee6ff;border:1px solid #3a6178;'
      + 'border-radius:2px;font:13px Consolas;cursor:pointer;line-height:1;padding:0';
    close.addEventListener('click', function () { panel.style.display = 'none'; });
    header.appendChild(title);
    header.appendChild(close);
    panel.appendChild(header);

    panel.appendChild(el('div', { color: '#6f8ea3', font: '10px Consolas,"Microsoft YaHei"' },
      '橙=下游去向 · 青=上游来料 · 线越粗货量越大'));

    // 这个产业自身的情况：等级、配方（几个什么原料 → 几个什么产品）。由 renderDetail 填。
    var info = el('div', { display: 'flex', flexDirection: 'column', gap: '3px', whiteSpace: 'normal' }, '');
    panel.appendChild(info);

    var summary = el('div', { color: '#9fe8ff', font: '11px Consolas,"Microsoft YaHei"', whiteSpace: 'normal' }, '');
    panel.appendChild(summary);

    var rows = el('div', { flex: '1', minHeight: '0', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' });
    panel.appendChild(rows);

    var foot = el('div', { color: '#6f8ea3', font: '10px Consolas,"Microsoft YaHei"', whiteSpace: 'normal' }, '');
    panel.appendChild(foot);

    ctx.board.appendChild(panel);

    return {
      show: function () { panel.style.display = 'flex'; },
      hide: function () { panel.style.display = 'none'; },
      setTitle: function (text) { title.textContent = text; },
      setInfo: function (list) { info.replaceChildren.apply(info, list); },
      setSummary: function (text) { summary.textContent = text; },
      setRows: function (list) { rows.replaceChildren.apply(rows, list); },
      setFoot: function (text) { foot.textContent = text; }
    };
  }

  function renderDetail() {
    var state = ctx.state;
    var detail = ctx.detail;
    if (!detail) return;
    var item = state.selected == null ? null : state.industryById.get(state.selected);
    if (!item) return;

    var down = [], up = [];
    state.edges.forEach(function (edge) { (edge.dir === DIR_DOWN ? down : up).push(edge); });
    var total = function (list) {
      return list.reduce(function (sum, edge) { return sum + (Number(edge.link.count) || 0); }, 0);
    };

    detail.setTitle(item.name + '（产业 ' + item.id + '）');
    detail.setInfo(buildInfoNodes(item));
    detail.setSummary('下游 ' + down.length + ' 条 / ' + fmt(total(down)) + ' 件　·　上游 '
      + up.length + ' 条 / ' + fmt(total(up)) + ' 件');

    var rows = state.edges.slice(0, MAX_ROWS).map(detailRow);
    if (state.edges.length > MAX_ROWS) {
      rows.push(el('div', { color: '#6f8ea3', padding: '2px 0' },
        '还有 ' + (state.edges.length - MAX_ROWS) + ' 条未列出（货量大的已排在前面）'));
    }
    if (!rows.length) rows.push(el('div', { color: '#6f8ea3', padding: '2px 0' }, '这个产业没有采到任何流向'));

    detail.setRows(rows);
    detail.show();
  }

  // 选中一个产业时，先说清"这厂是干什么的"：等级 + 配方（几个什么原料 → 几个什么产品）。
  // 配方来自 industry-recipes.json（tools/extract-industry-recipes.py 从游戏 .con 里抽的），
  // 按产业**名字**判类型去查 —— 类型表在 industry-kinds.js，图标层用的是同一份。
  function buildInfoNodes(item) {
    var nodes = [];
    var kinds = window.TPF2IndustryKinds;
    var kind = kinds ? kinds.of(item.name) : null;
    var recipe = (kind && ctx.state.recipes) ? ctx.state.recipes[kind.key] : null;

    var bits = [];
    if (typeof item.level === 'number') bits.push('等级 Lv.' + item.level);
    if (kind) bits.push(kind.label);
    // 厂内货量：采集器**数货实体**数出来的实时件数（TPF2 是每件货一个实体）。
    // 老切块里没有这个字段 —— 显示"—"而不是 0，免得把"没采到"看成"厂里空了"。
    bits.push(typeof item.stockCount === 'number'
      ? '厂内货量 ' + fmt(item.stockCount) + ' 件'
      : '厂内货量 —（采集器待重启）');
    if (recipe && recipe.capacity != null) bits.push('库存上限 ' + recipe.capacity);
    if (bits.length) {
      nodes.push(el('div', { color: '#9fe8ff', font: '11px Consolas,"Microsoft YaHei"' },
        bits.join('　·　')));
    }

    if (!recipe) {
      nodes.push(el('div', { color: '#6f8ea3', font: '10px Consolas,"Microsoft YaHei"' },
        '这一类产业没查到配方。'));
      return nodes;
    }

    // 配方一行：[原料图标 2×铁矿石] + [原料图标 2×煤] → [产品图标 1×钢]
    var line = el('div', { display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px' }, '');
    var inputs = recipe.inputs || [];
    if (!inputs.length) {
      line.appendChild(el('span', { color: '#7fe3a0' }, '直接采集（不要原料）'));
    } else {
      inputs.forEach(function (key, index) {
        if (index) line.appendChild(el('span', { color: '#8fa3b8' }, '+'));
        appendCargoChip(line, key, (recipe.input_amounts || [])[index]);
      });
    }
    line.appendChild(el('span', { color: '#ffb347', fontWeight: 'bold', padding: '0 2px' }, '→'));
    (recipe.outputs || []).forEach(function (key, index) {
      if (index) line.appendChild(el('span', { color: '#8fa3b8' }, '+'));
      appendCargoChip(line, key, (recipe.output_amounts || [])[index]);
    });
    nodes.push(line);
    return nodes;
  }

  // 一个"货种图标 + 数量 + 中文名"的小块。图标是游戏原版的（icons/cargo/）。
  function appendCargoChip(parent, cargoKey, amount) {
    var info = CARGO_BY_KEY[cargoKey];
    var chip = el('span', {
      display: 'inline-flex', alignItems: 'center', gap: '3px',
      padding: '1px 4px', background: '#12222e', borderRadius: '2px',
    }, '');
    if (info) {
      var icon = document.createElement('img');
      icon.src = '/' + info.icon;
      icon.alt = info.zh;
      icon.style.cssText = 'width:15px;height:15px;display:block';
      chip.appendChild(icon);
    }
    chip.appendChild(el('span', { color: '#eaf9ff' },
      (amount == null ? '' : amount + ' × ') + (info ? info.zh : cargoKey)));
    parent.appendChild(chip);
  }

  function detailRow(edge) {
    var state = ctx.state;
    var link = edge.link, isDown = edge.dir === DIR_DOWN;
    var color = isDown ? COLOR_DOWN : COLOR_UP;
    var wrap = el('div', {
      display: 'flex', flexDirection: 'column', gap: '1px',
      padding: '3px 5px', borderLeft: '2px solid ' + color, background: '#0d1c28'
    });

    // 下游看目的地，上游看货源地。
    var partnerId = isDown ? link.target_industry : link.source_industry;
    var partner = partnerId == null ? null : state.industryById.get(partnerId);
    var partnerName = partner ? partner.name
      : (isDown && link.target_kind !== 'industry' ? '城镇消费端' : (partnerId == null ? '—' : '产业 ' + partnerId));

    var head = el('div', { display: 'flex', gap: '6px', alignItems: 'baseline' });
    head.appendChild(el('span', { color: color, flexShrink: '0' }, isDown ? '→下游' : '←上游'));
    head.appendChild(el('span', { color: '#eaf9ff' }, cargoName(link.cargo_type)));
    head.appendChild(el('span', { color: '#ffd9a0', fontWeight: 'bold' }, fmt(link.count) + ' 件'));
    head.appendChild(el('span', { color: '#9fe8ff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, partnerName));
    wrap.appendChild(head);

    wrap.appendChild(el('div', { color: '#8fb4c8' },
      '在途 ' + fmt(link.onboard || 0) + ' / 候运 ' + fmt(link.waiting || 0) + ' / 未发运 ' + fmt(link.other || 0)));

    var allLines = link.lines || [];
    var lineNames = allLines.slice(0, 3).map(function (id) {
      var line = state.lineById.get(id);
      return line && line.name ? line.name : ('线路 ' + id);
    });
    var lineText = lineNames.length
      ? lineNames.join('、') + (allLines.length > 3 ? ' 等 ' + allLines.length + ' 条' : '')
      : '无线路记录';
    // 数据里 vehicles / lines 都只保留前 8 个，所以到 8 就标个 "+"，别让人误以为是精确值。
    var vehicleCount = (link.vehicles || []).length;
    var vehicleText = vehicleCount ? ('车 ' + vehicleCount + (vehicleCount >= 8 ? '+' : '') + ' 辆') : '暂无车';
    wrap.appendChild(el('div', { color: '#8fb4c8' }, '线路：' + lineText + '　·　' + vehicleText));

    var span = gameSpan(link.first_start_time, link.last_start_time);
    if (span) {
      var spanLine = el('div', { color: '#6f8ea3' }, '货物时间跨度：' + span);
      spanLine.title = 'first_start_time → last_start_time 的差，单位是游戏内秒，不是现实时间';
      wrap.appendChild(spanLine);
    }
    return wrap;
  }

  // ---- 小工具 ------------------------------------------------------------
  // 建 HTML 元素（面板 / 浮层用）。SVG 元素一律走 api.S，不要混。
  function el(tag, styles, text) {
    var node = document.createElement(tag);
    if (styles) Object.keys(styles).forEach(function (key) { node.style[key] = styles[key]; });
    if (text != null) node.textContent = text;
    return node;
  }

  function rowStyle() {
    return { display: 'flex', alignItems: 'center', gap: '6px', color: '#7ee6ff', font: '12px Consolas', whiteSpace: 'nowrap' };
  }

  function cargoName(id) {
    return CARGO_NAME[id] || ('货种 ' + id);
  }

  function fmt(value) {
    return String(Math.round(Number(value) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  // 游戏内秒 → 人看得懂的跨度。**不是现实时间**，所以措辞里点明"游戏"。
  function gameSpan(from, to) {
    var delta = (Number(to) || 0) - (Number(from) || 0);
    if (!(delta > 0)) return '';
    var days = delta / 86400;
    if (days >= 1) return (Math.round(days * 10) / 10) + ' 游戏日';
    return (Math.round(delta / 3600 * 10) / 10) + ' 游戏时';
  }

  function noop() {}
})();
