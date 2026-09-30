// 站点结构渲染器（station-struct.js）
//
// 干什么：把存档里的车站画到地图上（按类型上色、按客货运分实心空心、按容量分大小），
// 点一个站弹个浮层，交代它的容量、服务实体和所属站群。
//
// 为什么站点标记挂在 svg 根、而不挂进 mapLayer：
//   车站是"固定屏幕尺寸的标记"—— 缩放地图时大小不能跟着变。这类元素只能挂 svg 根，
//   用 screenPoint() 现算屏幕坐标。挂进 mapLayer 的话 zoom=1 时 5 个世界单位也就 1 px 出头，
//   全图一片看不见的灰点（主文件的站台层踩过这个坑）。
//
// 为什么位置每帧重算、而且走 onViewport：
//   挂 svg 根的元素不跟着地图的 transform 动，不给它每帧重算坐标就会黏在原地。
//   重算入口统一用 TPF2Map.onViewport()，跟地图共用同一次绘制节奏；
//   自己开 requestAnimationFrame 会跟地图错开一帧，拖动时标记明显滞后。
//
// 本文件不碰任何别人的文件（network-app.js / index.html / network.css / app.js 都不动），
// 也不引入新依赖 —— 页面里的 jQuery 和 Pixi 一概不用。
(function () {
  "use strict";

  // ===== 常量 ================================================================

  // 四类有站房的站（火车 / 汽车 / 港口 / 机场）+ 两类**没有站房**的小站（简易公交站 / 货车卸货站）。
  // 配色跟「交通工具 · 种类」那组车辆图层对齐，两处对得上。
  const TYPE_ORDER = ["RAIL", "STREET", "WATER", "AIR", "BUS_STOP", "CARGO_STOP"];
  const TYPE_LABEL = { RAIL: "火车", STREET: "汽车", WATER: "港口", AIR: "机场", BUS_STOP: "公交站", CARGO_STOP: "卸货站" };
  const TYPE_FULL = { RAIL: "火车站", STREET: "汽车站", WATER: "港口", AIR: "机场", BUS_STOP: "简易公交站", CARGO_STOP: "货车卸货站" };
  const TYPE_COLOR = { RAIL: "#d43b2b", STREET: "#2b7fd4", WATER: "#17a2a2", AIR: "#8a4fd4", BUS_STOP: "#7fb3d5", CARGO_STOP: "#d9a441" };
  const TYPE_TITLE = {
    RAIL: "混凝土/单轨等所有轨道车站（数据里是 station/rail/ 与 station/train/ 两种路径）",
    STREET: "station/street/ 下的车站，也就是汽车站（不是公交站牌）",
    WATER: "station/water/ 下的码头、港口",
    AIR: "station/air/ 下的机场",
    BUS_STOP: "没有站房建筑的简易公交站 —— 官方建造帮助：可直接建在人行道旁（客运；默认不勾，一开总开关就糊一片）",
    CARGO_STOP: "没有站房建筑的货车卸货站 —— 官方建造帮助：可直接建在人行道旁（货运端；默认不勾，同上）",
  };

  // 占地数据（layers/station-structures.json）里的 kind 是**小写**的 rail/street/water/air，
  // 上面这套常量却全是大写，中间必须转一道。2026-09-30 就是漏了这步：
  // `state.types["water"]` 取到 undefined，显隐判断把整类框当成"没勾"全藏了，
  // 颜色也落到兜底灰 —— 症状是"一个框都看不见"，但数据和坐标其实都是好的。
  const KIND_TO_TYPE = { rail: "RAIL", street: "STREET", water: "WATER", air: "AIR" };

  // 模块格子按"这格是什么"上色 —— 生成工具已经按模块文件名归好类（cell.k）。
  // 车站不是一坨，是这些格子拼出来的；分色才能一眼看出站台在哪、站房在哪。
  const CELL_COLOR = {
    platform: "#7fd4ff",   // 站台 / 月台
    building: "#ffcf7a",   // 站房 / 候车楼
    track: "#8fa3b8",      // 轨道
    stairs: "#c9a0ff",     // 楼梯 / 地道 / 天桥
    pier: "#d9a441",       // 栈桥 / 码头泊位
    entrance: "#7fe3a0",   // 出入口
    terminal: "#ff9ec4",   // 航站楼
    other: "#9fb0bf",
  };

  // 客运站画成空心圆，底色得贴近地图底色才像"空"的。这里跟 #board-wrap 的底色一致。
  const HOLLOW_FILL = "#070c12";

  // ===== 判据 ================================================================

  // 站类型只看 construction_files[0] 的路径前缀。
  // ⚠️ 火车有两条路径：常见的 station/rail/，以及单轨/skytrain 那 17 座站走的 station/train/。
  //    只认 rail/ 的话火车会少数 17 座（61 vs 78）。
  // 🔴 **没有站房建筑的那批（232 座）不是一类** —— 按官方建造帮助该分**两种**（用户 2026-09-30 指出）：
  //    「**简易公交站**」与「**货车卸货站**」，两者都直接建在人行道旁、共用同一个 .con，
  //    靠站台自身的 `cargo` 属性区分（该判据用户此前已核实）。
  //    实测这 232 座里：cargo=false → 简易公交站 **195** 座；cargo=true → 货车卸货站 **37** 座。
  //    （更早一版把两类混成一个「未知」标签，是漏读了这条。）
  function typeOf(station) {
    const file = (station.construction_files && station.construction_files[0]) || "";
    if (file.indexOf("station/rail/") === 0 || file.indexOf("station/train/") === 0) return "RAIL";
    if (file.indexOf("station/street/") === 0) return "STREET";
    if (file.indexOf("station/water/") === 0) return "WATER";
    if (file.indexOf("station/air/") === 0) return "AIR";
    return station.cargo ? "CARGO_STOP" : "BUS_STOP";
  }

  // 容量按服务的 cargo 真假分开累加。
  // 站上的 capacity_cargo / capacity_passenger 字段就是这两个和（565 座逐条核对过，全相等），
  // 但任务要的是"按 services 累加"，而且 services 一定在、那两个字段有几个站没有，所以只算一份。
  function capacityOf(station) {
    let freight = 0;
    let passenger = 0;
    (station.services || []).forEach(service => {
      const value = Number(service.capacity) || 0;
      if (service.cargo) freight += value;
      else passenger += value;
    });
    return { freight: freight, passenger: passenger, total: freight + passenger };
  }

  // 地下站：站底比同点地表低 3 m 以上。
  // ⚠️ 这个阈值按全量数据跑出来是 484/565 —— 明显把"嵌进地形里的普通站台"也算进来了，
  //    数值上不太可信。判据是任务定死的，就按它显示；详情里把地表 / 站底两个高程都列出来，
  //    让人能自己判断，而不是只丢一个"地下站"的结论。
  function isUnderground(station) {
    const surface = station.surface_z;
    const depth = station.depth_m;
    if (typeof surface !== "number" || typeof depth !== "number") return false;
    return surface - depth > 3;
  }

  // 大小分四档。565 座里 346 座容量为 0（服务实体没采到），所以 0 单独占一档，
  // 不然它们会全挤成同一个看不见的小点。
  function radiusOf(total) {
    if (!total) return 2.6;
    if (total < 100) return 3.4;
    if (total < 400) return 4.3;
    return 5.2;
  }

  // ===== 状态 ================================================================

  const state = {
    map: null,
    data: null,
    counts: null,
    byCluster: null,      // cluster id → 同群的车站数组（详情里要列"同群还有哪些站"）
    views: [],            // {station, type, group, position}
    layer: null,          // 所有标记的父 <g>，挂在 svg 根
    panel: null,          // 详情浮层（懒建）
    master: false,        // 总开关，默认关：别一进页面就往人地图上糊一堆点
    types: { RAIL: true, STREET: true, WATER: true, AIR: true, BUS_STOP: false, CARGO_STOP: false },
    lastViewportKey: "",  // 视口指纹，见 updatePositions()
    shapes: true,         // 是否画"真实占地轮廓"（跟着地图缩放走的那层）
    shapeLayer: null,     // 占地轮廓的父 <g>，挂在 mapLayer 下（**不是** svg 根）
    shapeViews: [],       // {type, group}，只用来跟着类型筛选显隐
    shapeByRef: null,     // layer-stations 实体 id → 结构数据，详情浮层里补"占地"那行
  };

  // ===== 启动：等 TPF2Map 就绪 ================================================
  // 本文件执行时 TPF2Map 很可能还没挂上（network-app.js 排在后面），所以要等事件；
  // 但也要照顾"注册时其实已经就绪"（脚本顺序被调过、或者本文件被动态插进来）的情况，
  // 所以先查一次再挂监听 —— 只挂不查会永远等不到那一枪。
  if (window.TPF2Map) {
    start(window.TPF2Map);
  } else {
    window.addEventListener("tpf2map:ready", function () { start(window.TPF2Map); }, { once: true });
  }

  function start(map) {
    if (!map || state.map) return;   // 只认一次；重复注册会让 565 个标记翻倍
    state.map = map;
    loadStations(0);
  }

  // 车站结构数据是 network-app.js 自己异步拉的，刚就绪时 stationData() 还是 null，
  // 而且它拉完不会广播任何事件，只能自己等。
  // 用**有次数上限**的 setTimeout 递进重试：只解决"数据到没到"，跟重绘没关系 ——
  // 重绘一律走 onViewport（见 updatePositions），这里不碰。
  function loadStations(attempt) {
    const data = state.map.stationData();
    if (data && Array.isArray(data.stations) && data.stations.length) {
      build(data);
      return;
    }
    if (attempt >= 40) {
      console.warn("[地图] 车站结构：等不到 stationData()，这一层不画了");
      return;
    }
    setTimeout(function () { loadStations(attempt + 1); }, 300);
  }

  // ===== 建图层 ==============================================================

  function build(data) {
    if (state.data) return;
    state.data = data;
    const map = state.map;

    const counts = { RAIL: 0, STREET: 0, WATER: 0, AIR: 0, BUS_STOP: 0, CARGO_STOP: 0 };
    const byCluster = new Map();
    data.stations.forEach(function (station) {
      counts[typeOf(station)] += 1;
      const key = station.cluster;
      if (!byCluster.has(key)) byCluster.set(key, []);
      byCluster.get(key).push(station);
    });
    state.counts = counts;
    state.byCluster = byCluster;

    // 整层挂 svg 根（不是 mapLayer）—— 见文件头的说明。
    const layer = map.S("g", { id: "station-struct-layer" }, "", map.svg);
    state.layer = layer;
    data.stations.forEach(function (station) {
      if (!station.position) return;
      state.views.push(makeMarker(station));
    });

    buildPanel(counts);
    applyVisibility();
    loadShapes();     // 真实占地轮廓，异步单独取（另一份数据，到了自己往上贴）

    // 点地图空白处把详情浮层收掉。标记自己会 stopPropagation，所以点标记不会顺手关掉刚开的层。
    map.svg.addEventListener("click", closeDetail);

    state.lastViewportKey = "";      // 逼第一帧把坐标写一遍
    map.onViewport(updatePositions); // 注册时就立刻先跑一次，标记当场落位

    console.log("[地图] 车站结构：" + data.stations.length + " 座（火车 " + counts.RAIL
      + " / 汽车 " + counts.STREET + " / 港口 " + counts.WATER + " / 机场 " + counts.AIR + "）");
  }

  function makeMarker(station) {
    const map = state.map;
    const type = typeOf(station);
    const color = TYPE_COLOR[type];
    const radius = radiusOf(capacityOf(station).total);

    const group = map.S("g", { "data-station-type": type, cursor: "pointer" }, "", state.layer);
    // 货运实心 / 客运空心 —— 这样"颜色区分类型、填充区分客货"，两个维度互不抢。
    if (station.cargo) {
      map.S("circle", { r: radius, fill: color, stroke: "#04090e", "stroke-width": 1, "pointer-events": "none" }, "", group);
    } else {
      map.S("circle", { r: radius, fill: HOLLOW_FILL, stroke: color, "stroke-width": 2, "pointer-events": "none" }, "", group);
    }
    // 命中区比图形大一圈，小圆点也点得中。
    map.S("circle", { r: Math.max(radius + 3, 9), fill: "transparent", "pointer-events": "fill" }, "", group);
    // 悬停名字用 SVG 自带的 <title>（浏览器原生气泡）。不去借主文件的 .track-tooltip ——
    // 那个元素有主文件自己的显隐逻辑，两边轮着写会打架。
    map.S("title", {}, (station.name || ("车站 " + station.entity_id)) + "（" + TYPE_FULL[type] + "）", group);

    // 主文件是在 svg 的 pointerdown 上起拖的；标记上先挡掉，否则点一下会变成拖地图。
    group.addEventListener("pointerdown", function (event) {
      if (event.button === 0) event.stopPropagation();
    });
    group.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      openDetail(station);
    });

    return { station: station, type: type, group: group, position: station.position };
  }

  // ===== 车站真实占地 =========================================================
  //
  // 数据来自 layers/station-structures.json（由 tools/build-station-structures.py 生成）：
  // 每个站的**占地包围盒**（游戏自己量出来的世界坐标，单位米）＋ 能读到的站台坐标。
  //
  // 🔴 这一层挂 **mapLayer**，跟上面的彩色圆点相反：
  //    圆点画的是"固定屏幕尺寸"的标记，缩放时大小不变，所以挂 svg 根 + screenPoint；
  //    占地框画的是**真实尺寸**的场地（几百米见方），必须跟着地图缩放走，所以挂 mapLayer + P()。
  //    两套坐标别搞混，混了就是"缩放到某档全糊在原点"。
  //
  // 挂上去之后不用每帧算：mapLayer 自己带 transform，元素跟着一起动。

  function loadShapes() {
    if (state.shapeLayer) return;   // 只建一次（build 理论上也只跑一次，这里是保险）
    const map = state.map;
    if (!map) return;
    fetch("layers/station-structures.json", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (data) { buildShapes(data); })
      .catch(function (error) {
        // 没生成过这份数据很正常（不跑工具就没有）—— 降级成"只有彩色点"，别让整层哑掉。
        console.warn("[地图] 车站结构：读不到占地数据，只画标记。"
          + "跑一次 tools/build-station-structures.py 就会生成 layers/station-structures.json。",
          error && error.message);
      });
  }

  function buildShapes(data) {
    const map = state.map;
    const list = (data && data.stations) || [];
    if (!list.length || !map.mapLayer) return;

    // 详情浮层要按实体 id 反查，先建索引
    const byRef = new Map();
    list.forEach(function (item) {
      if (item.station_ref != null) byRef.set(item.station_ref, item);
    });
    state.shapeByRef = byRef;

    const layer = map.S("g", { id: "station-shape-layer", "pointer-events": "none" }, "", map.mapLayer);
    state.shapeLayer = layer;

    let drawn = 0;
    list.forEach(function (item) {
      const box = item.box;
      if (!box || !(box.w > 0) || !(box.h > 0)) return;

      // 小写 kind → 大写的类型键（见文件头 KIND_TO_TYPE 的说明，漏这步框会被自己藏掉）
      const type = KIND_TO_TYPE[item.kind];
      if (!type) return;

      // 世界坐标的两个对角 → 底图坐标，再取 min/尺寸。
      // 不直接拿 p1 当左上角，是因为底图的 y 轴方向未必跟世界坐标一致（P() 里可能翻过），
      // 用两个角取 min 能自动兜住两种朝向。
      const a = map.P({ x: box.x, y: box.y });
      const b = map.P({ x: box.x + box.w, y: box.y + box.h });
      const left = Math.min(a.x, b.x);
      const top = Math.min(a.y, b.y);
      const width = Math.abs(b.x - a.x);
      const height = Math.abs(b.y - a.y);
      if (!(width > 0) || !(height > 0)) return;

      const color = TYPE_COLOR[type];
      const group = map.S("g", { "data-station-shape": type }, "", layer);

      // ⚠️ 属性名一律写 SVG 原生的连字符形式。S() 是 setAttribute(名字, 值) 原样写进 DOM，
      //    写驼峰（fillOpacity）会**静默失效、不报错**，填充就变成全不透明 —— 今天刚踩过。
      map.S("rect", {
        x: left.toFixed(1),
        y: top.toFixed(1),
        width: width.toFixed(1),
        height: height.toFixed(1),
        fill: color,
        "fill-opacity": 0.13,
        stroke: color,
        "stroke-width": 1.2,
        "stroke-opacity": 0.9,
        // 描边不随缩放变粗变细，不然缩远了边框会糊成一片
        "vector-effect": "non-scaling-stroke",
      }, "", group);

      // 站台：只有火车站读得出来坐标（其余三类引擎不给，生成工具已经滤掉了空值）。
      //
      // 🔴 半径必须用 T() 把**米**换算成底图尺寸再写进去。
      //    这个元素挂在 mapLayer 里，数值的单位是"底图单位"，1 单位 ≈ 22.6 米
      //    （baseScale≈0.0443）。直接写阿拉伯数字会被当成底图单位 ——
      //    2026-09-30 就这么踩的：想给 12 米半径，实际画出 271 米，屏幕上是一坨
      //    盖住半张地图的大圆。
      // ★ 模块格子 = 真正的站场结构。
      //   四类站都是"一个 .con 容器 + 若干 .module 格子"拼出来的（用户原话：模块化设计）：
      //   站台、站房、轨道、楼梯、栈桥、出入口各占一格。生成工具按 slotId 反解出网格坐标 (i,j)，
      //   乘上格尺寸、再套建筑的朝向矩阵，算出每格四角的**世界坐标** —— 所以这里拿到的是一串
      //   多边形顶点，直接喂 P() 就行，不用在前端算角度（地图自己还有一层旋转，避开它）。
      (item.cells || []).forEach(function (cell) {
        if (!cell.poly || cell.poly.length < 3) return;
        const points = cell.poly.map(function (pt) {
          const q = map.P({ x: pt[0], y: pt[1] });
          return q.x.toFixed(1) + "," + q.y.toFixed(1);
        }).join(" ");
        map.S("polygon", {
          points: points,
          fill: CELL_COLOR[cell.k] || CELL_COLOR.other,
          "fill-opacity": 0.5,
          stroke: "#04090e",
          "stroke-width": 0.8,
          "vector-effect": "non-scaling-stroke",
        }, "", group);
      });

      const platformRadius = map.T({ x: 8, y: 0 }).x;   // 8 米 ≈ 站台半宽
      (item.terminals || []).forEach(function (term) {
        const point = map.P({ x: term.x, y: term.y });
        map.S("circle", {
          cx: point.x.toFixed(1),
          cy: point.y.toFixed(1),
          r: platformRadius.toFixed(3),
          fill: color,
          "fill-opacity": 0.75,
          stroke: "#04090e",
          "stroke-width": 0.6,
          "vector-effect": "non-scaling-stroke",
        }, "", group);
      });

      state.shapeViews.push({ type: type, group: group });
      drawn += 1;
    });

    applyVisibility();

    console.log("[地图] 车站占地：" + drawn + " 个框（数据 " + (data.generated_at || "?")
      + "，其中带站台坐标的 " + list.filter(function (s) { return (s.terminals || []).length; }).length + " 个）");
  }

  // 每帧重算屏幕坐标 —— 唯一的重绘入口，由 TPF2Map.onViewport 驱动。
  function updatePositions() {
    if (!state.layer || !state.views.length) return;
    const map = state.map;
    // 视口没动就整段跳过。
    // 指纹用 (zoom, screenPoint(世界原点))：给定 zoom 和这个点，panX/panY 是唯一解，
    // 所以它跟 (zoom, panX, panY) 一一对应，不会漏判。拖动时每帧 565 次属性写太贵，
    // 主文件的注意力档位缓存也是同一个道理。
    const zoom = map.currentZoom();
    const probe = map.screenPoint({ x: 0, y: 0 });
    const key = zoom + "|" + probe.x.toFixed(2) + "|" + probe.y.toFixed(2);
    if (key === state.lastViewportKey) return;
    state.lastViewportKey = key;
    state.views.forEach(function (view) {
      if (view.group.style.display === "none") return;   // 藏起来的不用算
      const point = map.screenPoint(view.position);
      view.group.setAttribute("transform", "translate(" + point.x.toFixed(1) + " " + point.y.toFixed(1) + ")");
    });
  }

  function applyVisibility() {
    if (!state.layer) return;
    const master = state.master;
    state.layer.style.display = master ? "" : "none";
    // 占地轮廓跟着同一套总开关 + 类型筛选，另外自己还有一个"显示占地"开关。
    if (state.shapeLayer) {
      state.shapeLayer.style.display = (master && state.shapes) ? "" : "none";
    }
    if (!master) return;   // 整层都藏了，逐个再写一遍显示属性没意义
    state.views.forEach(function (view) {
      view.group.style.display = state.types[view.type] ? "" : "none";
    });
    if (state.shapeLayer && state.shapes) {
      state.shapeViews.forEach(function (view) {
        view.group.style.display = state.types[view.type] ? "" : "none";
      });
    }
    // 刚显出来的标记可能带着旧坐标（隐藏期间视口动过），逼下一帧全部重算。
    state.lastViewportKey = "";
    updatePositions();
  }

  // ===== 图层面板 ============================================================
  function buildPanel(counts) {
    const map = state.map;
    // 自建一个分组，别和别的扩展挤在「设施」里（2026-09-30：曾和产业链挤在一起，界面糊成一团）。
    const panelApi = map.panel;
    const group = (panelApi && typeof panelApi.addGroup === "function")
      ? panelApi.addGroup("车站结构")
      : (panelApi && panelApi.groups && panelApi.groups.facility);
    if (!group || typeof map.panel.addOption !== "function") {
      // 面板接口被改过 / 没挂上：至少把图画出来，别整个功能哑掉。
      console.warn("[地图] 车站结构：图层面板接口不可用，标记只画不加开关");
      state.master = true;
      state.types.BUS_STOP = true;
      state.types.CARGO_STOP = true;
      applyVisibility();
      return;
    }
    const add = map.panel.addOption;

    add(group, "车站结构（全部）", {
      checked: false,
      count: state.data.stations.length,
      title: "总开关。车站标记固定在屏幕上大小不变：颜色分类型，实心是货运站、空心是客运站，大小按容量分档；点标记看详情",
      onChange: function (checked) { state.master = checked; applyVisibility(); },
    });

    add(group, "占地轮廓", {
      checked: state.shapes,
      title: "按游戏量出来的占地包围盒，把车站的真实场地画上去（挂在缩放层，跟着放大缩小）。"
        + "外框是站区范围，实心小圆是站台（只有火车站读得出站台坐标）。"
        + "数据来自 tools/build-station-structures.py 生成的 layers/station-structures.json",
      onChange: function (checked) { state.shapes = checked; applyVisibility(); },
    });

    TYPE_ORDER.forEach(function (type) {
      add(group, TYPE_LABEL[type], {
        checked: state.types[type],
        count: counts[type],
        swatch: TYPE_COLOR[type],
        title: TYPE_TITLE[type],
        onChange: function (checked) { state.types[type] = checked; applyVisibility(); },
      });
    });
  }

  // ===== 详情浮层 ============================================================
  // 自己做一个浮层贴在 #board-wrap 里（主侧栏归主文件管，不去动它，免得两边打架）。
  // 样式全部内联：network.css 是主文件的地盘，一行都不改。
  function ensureDetailPanel() {
    if (state.panel) return state.panel;
    const wrap = document.querySelector("#board-wrap");
    if (!wrap) return null;
    const panel = document.createElement("div");
    panel.setAttribute("style", [
      "position:absolute",
      "right:16px",
      "top:78px",                 // 让开右上角的 watermark 和"收起侧栏"按钮
      "width:296px",
      "max-height:calc(100% - 104px)",
      "overflow:auto",
      "display:none",
      "z-index:6",                // 压过图层面板(2)和提示气泡(5)，但不盖侧栏
      "padding:10px 12px",
      "background:#09131ef2",
      "border:1px solid #31495e",
      "border-radius:3px",
      "box-shadow:0 6px 20px #000a",
      "color:#cfe9f6",
      "font:12px/1.7 'Microsoft YaHei',Consolas",
    ].join(";"));
    wrap.appendChild(panel);
    state.panel = panel;
    return panel;
  }

  function closeDetail() {
    if (state.panel) state.panel.style.display = "none";
  }

  function openDetail(station) {
    const panel = ensureDetailPanel();
    if (!panel) return;

    const type = typeOf(station);
    const color = TYPE_COLOR[type];
    const capacity = capacityOf(station);
    const underground = isUnderground(station);
    const members = (state.byCluster && state.byCluster.get(station.cluster)) || [station];

    panel.replaceChildren();

    // ---- 标题行：色块 + 站名 + 关闭 ----
    const head = document.createElement("div");
    head.setAttribute("style", "display:flex;align-items:center;gap:7px;margin-bottom:8px");

    const dot = document.createElement("i");
    // 色块跟着标记的"实心 / 空心"走，列表和图上一眼能对上。
    dot.setAttribute("style", "flex:0 0 auto;width:11px;height:11px;border-radius:"
      + (station.cargo ? "2px" : "50%") + ";background:" + (station.cargo ? color : HOLLOW_FILL)
      + ";border:2px solid " + color);
    head.appendChild(dot);

    const name = document.createElement("b");
    name.textContent = station.name || ("车站 " + station.entity_id);
    name.setAttribute("style", "flex:1 1 auto;color:#eaf9ff;font-size:13px;word-break:break-all");
    head.appendChild(name);

    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "×";
    close.title = "关闭";
    close.setAttribute("style", "flex:0 0 auto;width:22px;height:22px;border:1px solid #3a6178;background:#102535;color:#7ee6ff;border-radius:2px;font:13px Consolas;line-height:1;cursor:pointer");
    close.addEventListener("click", closeDetail);
    head.appendChild(close);
    panel.appendChild(head);

    // ---- 关键属性表 ----
    const table = document.createElement("div");
    table.setAttribute("style", "display:grid;grid-template-columns:auto 1fr;gap:2px 9px;margin-bottom:9px");
    const row = function (label, value, valueColor) {
      const key = document.createElement("span");
      key.textContent = label;
      key.setAttribute("style", "color:#7fa8c0");
      const val = document.createElement("span");
      val.textContent = value;
      val.setAttribute("style", "color:" + (valueColor || "#eaf9ff") + ";word-break:break-all");
      table.appendChild(key);
      table.appendChild(val);
    };
    row("类型", TYPE_FULL[type], color);
    row("职能", station.cargo ? "货运站" : "客运站");
    row("容量", "货运 " + capacity.freight + " · 客运 " + capacity.passenger + " · 合计 " + capacity.total);
    row("高程", (typeof station.surface_z === "number" ? "地表 " + station.surface_z.toFixed(2) + " m" : "地表 未知")
      + " · " + (typeof station.depth_m === "number" ? "站底 " + station.depth_m.toFixed(2) + " m" : "站底 未知"));
    row("位置", underground ? "地下站（站底比地表低 3 m 以上）" : "地面站", underground ? "#ffbd52" : null);
    row("实体", "id " + station.entity_id + " · 子实体 " + ((station.child_ids || []).length));
    row("站台", (station.platforms || []).length + " 个");
    // 占地：从结构数据按实体 id 反查。还没加载到就不写这行，不拿"未知"占位。
    const shape = state.shapeByRef ? state.shapeByRef.get(station.entity_id) : null;
    if (shape && shape.box) {
      row("占地", shape.box.w.toFixed(0) + " × " + shape.box.h.toFixed(0) + " m · 高 "
        + shape.height.toFixed(1) + " m"
        + ((shape.terminals || []).length ? " · 站台 " + shape.terminals.length + " 个" : ""));
    }
    panel.appendChild(table);

    // ---- 服务实体明细 ----
    panel.appendChild(sectionTitle("服务实体（" + ((station.services || []).length) + "）"));
    const services = station.services || [];
    if (!services.length) {
      panel.appendChild(hint("这个站没有采到服务实体。"));
    } else {
      services.forEach(function (service, index) {
        const item = document.createElement("div");
        item.setAttribute("style", "display:flex;gap:6px;padding:2px 0;border-bottom:1px solid #16303f");
        const order = document.createElement("span");
        order.textContent = (index + 1) + ".";
        order.setAttribute("style", "color:#5f8ba3;flex:0 0 auto");
        const file = document.createElement("span");
        // 服务实体的 file 字段经常缺（只留在站的 construction_files 上），缺了就照实说。
        file.textContent = service.file || "（未记录文件名）";
        file.setAttribute("style", "flex:1 1 auto;color:#a9cfe2;word-break:break-all");
        const meta = document.createElement("span");
        meta.textContent = (service.cargo ? "货 " : "客 ") + (Number(service.capacity) || 0);
        meta.setAttribute("style", "flex:0 0 auto;color:" + (service.cargo ? "#ffbd52" : "#7ee6ff"));
        item.appendChild(order);
        item.appendChild(file);
        item.appendChild(meta);
        panel.appendChild(item);
      });
    }

    // ---- 所属站群 ----
    panel.appendChild(sectionTitle("所属站群（同群 " + members.length + " 站，群 id " + station.cluster + "）"));
    if (members.length <= 1) {
      panel.appendChild(hint("这个站自己一群，没有互通的其他站。"));
    } else {
      const list = document.createElement("div");
      // 最大的群有 29 个站，给它一个自己的滚动区，免得浮层被名字撑爆。
      list.setAttribute("style", "max-height:132px;overflow:auto;padding-left:2px");
      members.slice().sort(function (a, b) {
        return String(a.name || "").localeCompare(String(b.name || ""), "zh-CN");
      }).forEach(function (member) {
        const item = document.createElement("div");
        item.setAttribute("style", "color:" + (member === station ? "#7ee6ff" : "#a9cfe2") + ";word-break:break-all");
        item.textContent = (member === station ? "▸ " : "· ") + (member.name || ("车站 " + member.entity_id))
          + "　" + TYPE_LABEL[typeOf(member)] + "·" + (member.cargo ? "货" : "客");
        list.appendChild(item);
      });
      panel.appendChild(list);
    }

    // ---- 建设文件 ----
    panel.appendChild(sectionTitle("建设文件"));
    const files = station.construction_files || [];
    panel.appendChild(hint(files.length ? files.join("\n") : "（未记录 construction_files，所以类型判不出来）"));

    panel.style.display = "block";
  }

  function sectionTitle(text) {
    const node = document.createElement("div");
    node.textContent = text;
    node.setAttribute("style", "margin:9px 0 4px;padding-top:7px;border-top:1px solid #1d3a4d;color:#7ee6ff;font-weight:600");
    return node;
  }

  function hint(text) {
    const node = document.createElement("div");
    node.textContent = text;
    node.setAttribute("style", "color:#6f93a8;word-break:break-all;white-space:pre-wrap");
    return node;
  }
})();
