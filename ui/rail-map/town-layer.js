// 城镇图层 —— 把 27 个城镇的名字和"它要什么货"画到图上。
//
// 数据：`/layers/town-data.json`（地图服务切好的产物，源是 mod 的 layer-town.json），
//       每个城镇带 `name` / `x`,`y` / `needs`。
//       `needs` 是三元素数组，按官方语义依次是 **住宅 / 商业 / 工业** 三个区，
//       每区一串**货种 id**（对应 /cargo-types.json，图标就是 icons/cargo/ 那批原版图标）。
//       实测住宅区恒为空（住宅不收货），要货的是商业和工业 —— 所以图上只画这两行。
//
// 这一层画的是"固定屏幕尺寸"的标记（名字和图标不随缩放变大变小），所以：
//   挂 svg 根 + screenPoint() + onViewport 每帧重算。**不是**挂 mapLayer ——
//   反过来，占地那种"真实米数"的东西才挂 mapLayer，两套别混。

(function () {
  "use strict";

  var TOWN_URL = "/layers/town-data.json";
  var CARGO_URL = "/cargo-types.json";

  var LABEL_COLOR = "#ffe6b8";   // 城镇名（暖黄，跟站名的青色一眼分开）
  var ZONE_COLOR = "#c9b489";
  var ICON_SIZE = 13;            // 需求图标边长（原图 50×50，缩小用）
  var ICON_GAP = 1;
  var ROW_GAP = 9;               // 两行之间留的空
  var ZONE_W = 12;               // 行首那个区名占的宽度（一个汉字 + 一点缝）
  var FIRST_ROW_Y = 17;          // 第一行相对城镇名的下移量

  var ZONE_LABEL = ["住", "商", "工"];

  var state = {
    map: null,
    towns: [],
    byId: {},        // 货种 id → {zh, icon}
    layer: null,
    master: false,   // 总开关，默认关（一进页面就糊 27 个城镇没必要）
    showNeeds: true,
    lastKey: "",
  };

  // ===== 启动 ================================================================
  // 本文件执行时 TPF2Map 多半还没挂上（network-app.js 排在后面），等事件；
  // 但也要照顾"注册时其实已经就绪"，所以先查一次再挂监听 —— 只挂不查会永远等不到。

  if (window.TPF2Map) boot(window.TPF2Map);
  else window.addEventListener("tpf2map:ready", function () { boot(window.TPF2Map); }, { once: true });

  function boot(map) {
    if (!map || state.map) return;
    state.map = map;
    Promise.all([getJson(TOWN_URL), getJson(CARGO_URL)])
      .then(function (res) { build(map, res[0], res[1]); })
      .catch(function (error) {
        console.warn("[地图] 城镇层：数据没取到 ——", error && error.message);
      });
  }

  function getJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(url + " HTTP " + r.status);
      return r.json();
    });
  }

  // ===== 建图层 ==============================================================

  function build(map, townData, cargoData) {
    var towns = (townData && townData.towns) || [];
    (cargoData && cargoData.types || []).forEach(function (t) { state.byId[String(t.id)] = t; });

    // ⚠️ 城镇坐标要等 mod 的 town 采集器部署后才采得到。没坐标的直接跳过，
    //    并且把原因说清楚 —— 免得出现"代码在跑、图上什么都没有"的无头案。
    var withPos = towns.filter(function (t) {
      return typeof t.x === "number" && typeof t.y === "number";
    });
    state.towns = withPos;

    if (withPos.length) {
      var layer = map.S("g", { id: "town-layer", "pointer-events": "none" }, "", map.svg);
      state.layer = layer;
      withPos.forEach(function (town) { drawTown(map, layer, town); });
      state.lastKey = "";
      map.onViewport(updatePositions);   // 注册时会立刻先跑一次，标签当场落位
    } else {
      console.warn("[地图] 城镇层：" + towns.length + " 个城镇在数据里，但**一个坐标都没有**，这一层先不画。"
        + "原因通常是 mod 的 layer_town.lua 坐标修复还没部署（改 Lua 要重启游戏）。");
    }

    buildPanel(withPos.length, towns.length);
    applyVisibility();
  }

  function drawTown(map, layer, town) {
    var group = map.S("g", {}, "", layer);

    // 城镇名：跟站名一样带描边，压在深色底图上才读得清
    map.S("text", {
      x: "0", y: "0", "text-anchor": "middle",
      "font-size": "12", "font-family": 'Consolas,"Microsoft YaHei",sans-serif',
      fill: LABEL_COLOR, stroke: "#0a0602", "stroke-width": "3",
      "paint-order": "stroke", "stroke-linejoin": "round",
    }, String(town.name || ("城镇 " + town.id)), group);

    // 需求：三区里只画有货的（住宅区一般是空的）。整行按"区名 + 图标串"的总宽居中。
    var rows = [];
    (town.needs || []).forEach(function (zone, index) {
      var ids = [];
      (Array.isArray(zone) ? zone : []).forEach(function (id) {
        if (typeof id === "number") ids.push(String(id));
      });
      if (ids.length) rows.push({ zone: index, ids: ids });
    });

    rows.forEach(function (row, rowIndex) {
      var rowY = FIRST_ROW_Y + rowIndex * (ICON_SIZE + ROW_GAP);
      var rowWidth = ZONE_W + row.ids.length * (ICON_SIZE + ICON_GAP) - ICON_GAP;
      var startX = -rowWidth / 2;

      // 区名（住 / 商 / 工）。打上 data-needs，好让"需求货种"开关一次性全收掉。
      var label = map.S("text", {
        x: startX.toFixed(1), y: (rowY + 4).toFixed(1), "text-anchor": "start",
        "font-size": "10.5", "font-family": 'Consolas,"Microsoft YaHei",sans-serif',
        fill: ZONE_COLOR, stroke: "#0a0602", "stroke-width": "2.6", "paint-order": "stroke",
      }, ZONE_LABEL[row.zone] || "?", group);
      label.setAttribute("data-needs", "1");

      var cursorX = startX + ZONE_W;
      row.ids.forEach(function (id) {
        var cargo = state.byId[id];
        if (cargo) {
          var image = map.S("image", {
            href: cargo.icon,
            x: cursorX.toFixed(1), y: (rowY - ICON_SIZE / 2).toFixed(1),
            width: ICON_SIZE, height: ICON_SIZE,
            preserveAspectRatio: "xMidYMid meet",
          }, "", group);
          image.setAttribute("data-needs", "1");
          // 悬停能看中文货名（SVG 原生气泡）
          map.S("title", {}, "商业/工业要的货：" + cargo.zh, image);
        } else {
          // 字典里没有这个 id（装了 mod 的货种）—— 画个灰块占位，别静默消失
          var block = map.S("rect", {
            x: cursorX.toFixed(1), y: (rowY - ICON_SIZE / 2).toFixed(1),
            width: ICON_SIZE, height: ICON_SIZE, fill: "#8a949c", "fill-opacity": "0.6",
          }, "", group);
          block.setAttribute("data-needs", "1");
        }
        cursorX += ICON_SIZE + ICON_GAP;
      });
    });

    town._group = group;
  }

  // ===== 每帧定位 ============================================================
  // 唯一的重绘入口，由 TPF2Map.onViewport 驱动。**别**用 rAF / setInterval ——
  // 那样会跟地图的绘制节奏错开一帧，拖动时标签会滞后。

  function updatePositions() {
    if (!state.layer || !state.towns.length) return;
    var map = state.map;
    var origin = map.screenPoint({ x: 0, y: 0 });
    var key = map.currentZoom() + "|" + origin.x.toFixed(2) + "|" + origin.y.toFixed(2);
    if (key === state.lastKey) return;      // 视口没动就整段跳过
    state.lastKey = key;

    state.towns.forEach(function (town) {
      var point = map.screenPoint({ x: town.x, y: town.y });
      town._group.setAttribute("transform",
        "translate(" + point.x.toFixed(1) + " " + point.y.toFixed(1) + ")");
    });
  }

  // ===== 显隐 ================================================================
  // 🔴 整层收起来必须用 display。visibility 是**继承**属性，子元素只要显式设了
  //    visible 就会盖过父元素的 hidden —— 父级那层等于没藏住（2026-09-30 在产业图标上踩过）。

  function applyVisibility() {
    if (!state.layer) return;
    state.layer.style.display = state.master ? "" : "none";
    applyNeeds();
    state.lastKey = "";
    updatePositions();
  }

  function applyNeeds() {
    if (!state.layer) return;
    var shown = state.master && state.showNeeds;
    state.layer.querySelectorAll("[data-needs]").forEach(function (el) {
      el.style.display = shown ? "" : "none";
    });
  }

  // ===== 图层面板 ============================================================

  function buildPanel(shown, total) {
    var panel = state.map.panel;
    if (!panel || typeof panel.addGroup !== "function") return;
    var group = panel.addGroup("城镇");

    panel.addOption(group, "城镇", {
      checked: false,
      count: total,
      title: "标出城镇名字，以及它**要什么货**：下面两行是商业区和工业区要的货种，"
        + "图标用的是游戏原版的货种图标。住宅区不收货，所以不画。"
        + (shown < total ? " ⚠️ 目前只有 " + shown + "/" + total + " 个城镇采到坐标，其余等 mod 重启后才补上。" : ""),
      onChange: function (checked) { state.master = checked; applyVisibility(); },
    });

    panel.addOption(group, "需求货种", {
      checked: true,
      title: "每个城镇下面那两行货种图标（商 = 商业区、工 = 工业区）。关掉只留名字，图面干净些。",
      onChange: function (checked) { state.showNeeds = checked; applyNeeds(); },
    });
  }

})();
