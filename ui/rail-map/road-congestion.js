/* 道路拥堵图层（像高德那样的路况色带）
 *
 * 用户要求（2026-09-30）：
 *   「像高德地图一样，每 5 分钟采样一次，把路况用颜色区分出来，放大才显示，
 *     可以开可以关，静态显示」——**不要逐辆渲染 NPC 车**，有聚合数据就够。
 *
 * 所以本层做三件事，其余一概不做：
 *   ① 从静态几何文件取路段的曲线（world 坐标），从动态路况文件取每段的等级；
 *   ② 按等级把路段合并成 ≤4 条 <path>，涂上高德那套颜色（绿/黄/橙/红）；
 *   ③ 面板里给一个总开关、一个"也画畅通段"、一个刷新按钮，外加最堵的几段清单。
 *
 * 🔴 有意不做的事（都是踩过坑的）：
 *   · **不画任何车辆**（10,710 辆 NPC 车逐辆画既没必要，也会把 DOM 拖垮）；
 *   · **不用 requestAnimationFrame / setInterval 重绘**（会跟地图绘制错开一帧，
 *     拖动时滞后 —— 见 MEMORY 里的记录）。本层画完就是静态的：路径挂在 mapLayer 下，
 *     平移缩放由地图自己的 transform 带着走，我们一个像素都不用重算；
 *   · **不搞多套按缩放走的规则**（用户明确要求过）：只有一条 —— 缩到 ZOOM_MIN 以下整层不显示；
 *   · **显隐一律用 display:none**，不用 visibility（它是继承属性，子元素能盖过父元素）。
 *
 * 数据从哪来：
 *   /layers/road-edge-geometry.json   静态几何（tools/build-road-geometry.py 生成，修路后才需重跑）
 *   /layers/road-traffic-data.json    动态路况（mod 自动产出，每 5 分钟一份）
 * 两份按 edge_id 关联。
 */
(function () {
  "use strict";

  // 高德那套配色（交通图惯例：绿=畅通、黄=缓行、橙=拥堵、红=严重）
  var LEVEL_STYLE = {
    ALARM: { color: "#d6202b", width: 5.2, label: "严重" },
    WARN: { color: "#e8791f", width: 4.2, label: "拥堵" },
    SLOW: { color: "#f0b429", width: 3.4, label: "缓行" },
    OK: { color: "#2fb457", width: 3.0, label: "畅通" }
  };
  var LEVEL_ORDER = ["ALARM", "WARN", "SLOW", "OK"];

  var ZOOM_MIN = 2.5;             // 放大到这才显示（用户要求"放大才显示"）
  var SLOW_AT = 0.12;             // 拥堵指数达到这才算"缓行"（Lua 侧只分 OK/WARN/ALARM）
  var REFRESH_MS = 5 * 60 * 1000; // 拉新数据的间隔：5 分钟，跟采样节奏对齐
  var MAX_ALARM_ROWS = 10;        // 面板里最多列几条最堵的

  var state = {
    ready: false,
    map: null,
    on: false,            // 总开关，默认关
    includeClear: false,  // 是否把"有车但畅通"的段也画成绿
    group: null,          // 图层容器（挂 mapLayer 下）
    buckets: {},          // level → [path 片段]
    built: false,
    visible: null,        // 当前该不该显示（只在翻转时写 DOM）
    sampledAt: null,      // 数据指纹；变了才重建
    traffic: null,
    counts: { ALARM: 0, WARN: 0, SLOW: 0, OK: 0 },
    refreshTimer: 0
  };

  function byId(id) { return document.getElementById(id); }

  function text(tag, style, content) {
    var el = document.createElement(tag);
    if (style) el.setAttribute("style", style);
    el.textContent = content;
    return el;
  }

  function hint(target, message) {
    if (!target) return;
    target.textContent = message;
  }

  // ===== 数据 =====

  function fetchJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (response) {
      if (!response.ok) throw new Error(url + " → HTTP " + response.status);
      return response.json();
    });
  }

  // 把"每段一条曲线"合并成"每等级一条 path"。
  // 为什么合并：一个存档有近万条路，逐条建 <path> 会让浏览器每帧重新栅格化上千个元素
  // （底图道路层早就因为这个改成了按样式合并）。多段 `M…C…` 直接拼接是合法 SVG。
  function buildPaths(map, geometry, traffic) {
    var buckets = { ALARM: [], WARN: [], SLOW: [], OK: [] };
    var shapeOf = new Map();
    for (var i = 0; i < geometry.ids.length; i += 1) shapeOf.set(geometry.ids[i], geometry.shapes[i]);

    var items = (traffic.segments && traffic.segments.items) || [];
    for (var j = 0; j < items.length; j += 1) {
      var row = items[j];
      var shape = shapeOf.get(row.edge_id);
      if (!shape) continue;
      var level = row.level || "OK";
      if (level === "OK" && row.congestion != null && row.congestion >= SLOW_AT) level = "SLOW";
      // 有车但跑得顺：默认不画 —— 一屏绿没什么信息量，还白白拉长 SVG
      if (level === "OK" && !state.includeClear) continue;
      // 8 个数：起点、控制点1、控制点2、终点（世界坐标）→ 过 P() 变底图坐标
      var a = map.P({ x: shape[0], y: shape[1] });
      var c1 = map.P({ x: shape[2], y: shape[3] });
      var c2 = map.P({ x: shape[4], y: shape[5] });
      var b = map.P({ x: shape[6], y: shape[7] });
      buckets[level].push("M" + a.x.toFixed(2) + "," + a.y.toFixed(2)
        + "C" + c1.x.toFixed(2) + "," + c1.y.toFixed(2)
        + " " + c2.x.toFixed(2) + "," + c2.y.toFixed(2)
        + " " + b.x.toFixed(2) + "," + b.y.toFixed(2));
    }
    return buckets;
  }

  function render(map, buckets) {
    // 清掉旧内容再画（刷新时几何不变，但等级会变）
    if (state.group) state.group.parentNode.removeChild(state.group);
    var group = map.S("g", { id: "road-congestion-layer", "pointer-events": "none" }, "", map.mapLayer);
    state.group = group;

    LEVEL_ORDER.forEach(function (level) {
      var parts = buckets[level];
      if (!parts || !parts.length) return;
      var style = LEVEL_STYLE[level];
      map.S("path", {
        d: parts.join(""),
        fill: "none",
        stroke: style.color,
        "stroke-width": style.width,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        // non-scaling-stroke：缩放时线宽不变，路况色带在远处也不会糊成一片
        "vector-effect": "non-scaling-stroke",
        opacity: level === "OK" ? 0.75 : 0.95,
        "pointer-events": "none",
        "data-level": level
      }, "", group);
    });
    state.built = true;
    applyZoom(map);
  }

  // 只在"开着 + 数据齐"时才真的去拼路径（默认关着，不该让人白等一次渲染）
  function ensureRendered(map) {
    if (!state.on || !state.traffic || !state.geometry) return;
    render(map, buildPaths(map, state.geometry, state.traffic));
  }

  // ===== 显示逻辑：只有一条按缩放走的规则 =====

  function applyZoom(map) {
    var should = state.on && state.built && map.currentZoom() >= ZOOM_MIN;
    if (should === state.visible) return;   // 只在翻转时写 DOM
    state.visible = should;
    if (state.group) state.group.style.display = should ? "" : "none";
  }

  // ===== 面板 =====

  function buildPanel(map, traffic) {
    var group = map.panel.addGroup("道路拥堵");
    state.panel = group;

    var head = group.firstChild;
    state.badge = text("span", "margin-left:6px;color:#ff6b6b;font-weight:700", "");
    if (head) head.appendChild(state.badge);

    map.panel.addOption(group, "路况（道路拥堵）", {
      checked: false,
      title: "像高德那样把路段涂成 绿/黄/橙/红。放大到 " + ZOOM_MIN + " 倍以上才显示；"
        + "只画有车的路段，不逐辆画 NPC 车",
      onChange: function (checked) {
        state.on = checked;
        if (checked) ensureRendered(map);
        applyZoom(map);
      }
    });

    map.panel.addOption(group, "也画畅通段", {
      checked: false,
      title: "勾上会把\u201c有车但跑得顺\u201d的路段也涂成绿色。默认不画 —— 一屏绿没什么信息量",
      onChange: function (checked) {
        state.includeClear = checked;
        ensureRendered(map);
      }
    });

    // 图例（纯展示，不参与交互）
    var legend = text("div", "margin:6px 0 2px 0;color:#9fb3c8;font-size:11px", "");
    LEVEL_ORDER.forEach(function (level) {
      var style = LEVEL_STYLE[level];
      var row = text("span", "display:inline-flex;align-items:center;margin-right:8px", "");
      var dot = text("i", "display:inline-block;width:10px;height:4px;border-radius:2px;"
        + "margin-right:3px;background:" + style.color, "");
      row.appendChild(dot);
      row.appendChild(text("span", "", style.label + " " + (state.counts[level] || 0)));
      legend.appendChild(row);
    });
    group.appendChild(legend);

    // 最堵的几段：面板里直接看，不用去翻控制台
    var list = text("div", "max-height:150px;overflow:auto;margin:4px 0;font-size:11px;"
      + "color:#cfe0ee;line-height:1.5", "");
    list.className = "layer-group is-scroll";
    var alarms = (traffic.summary && traffic.summary.alarm) || 0;
    if (alarms > 0) {
      var items = (traffic.segments && traffic.segments.items) || [];
      var shown = 0;
      for (var i = 0; i < items.length && shown < MAX_ALARM_ROWS; i += 1) {
        var row = items[i];
        if (row.level !== "ALARM" && row.level !== "WARN") continue;
        shown += 1;
        list.appendChild(text("div", "white-space:nowrap", [
          (LEVEL_STYLE[row.level] || {}).label || row.level,
          "路段 " + row.edge_id,
          row.n + " 车",
          (row.avg_kmh == null ? "?" : row.avg_kmh.toFixed(1)) + " km/h",
          row.has_bus ? "有公交" : "无公交"
        ].join(" · ")));
      }
    } else {
      list.appendChild(text("div", "color:#8fa6bb", "没有达到拥堵阈值的路段"
        + "（阈值还没按实测标定，可能偏松）"));
    }
    group.appendChild(list);

    // 数据时间 + 手动刷新
    var foot = text("div", "color:#7f95aa;font-size:11px", "");
    state.foot = foot;
    group.appendChild(foot);
    var refresh = document.createElement("button");
    refresh.type = "button";
    refresh.textContent = "刷新路况";
    refresh.title = "重新拉一次路况数据（mod 每 5 分钟自动产一份新的）";
    refresh.addEventListener("click", function () { loadTraffic(map, true); });
    group.appendChild(refresh);
  }

  // ===== 载入 =====

  function loadGeometry(map) {
    if (state.geometry) return Promise.resolve(state.geometry);
    return fetchJson("/layers/road-edge-geometry.json").then(function (geometry) {
      state.geometry = geometry;
      return geometry;
    });
  }

  function stampOf(traffic) {
    if (!traffic) return "none";
    return [traffic.sampled_at, traffic.game_time,
      (traffic.summary && traffic.summary.road_vehicles),
      (traffic.summary && traffic.summary.alarm)].join("|");
  }

  function loadTraffic(map, force) {
    if (!map) return;
    fetchJson("/layers/road-traffic-data.json").then(function (traffic) {
      var stamp = stampOf(traffic);
      if (!force && stamp === state.sampledAt) return;   // 数据没变就别重画
      state.sampledAt = stamp;
      state.traffic = traffic;

      state.counts = { ALARM: 0, WARN: 0, SLOW: 0, OK: 0 };
      var items = (traffic.segments && traffic.segments.items) || [];
      for (var i = 0; i < items.length; i += 1) {
        var level = items[i].level || "OK";
        if (level === "OK" && items[i].congestion != null && items[i].congestion >= SLOW_AT) level = "SLOW";
        state.counts[level] = (state.counts[level] || 0) + 1;
      }

      if (!state.panel) buildPanel(map, traffic);
      if (state.badge) {
        state.badge.textContent = state.counts.ALARM ? "报警 " + state.counts.ALARM : "";
      }
      if (state.foot) {
        var summary = traffic.summary || {};
        state.foot.textContent = "采样 " + (traffic.sampled_at
          ? new Date(traffic.sampled_at * 1000).toLocaleTimeString()
          : "?")
          + " · 车 " + (summary.located == null ? "?" : summary.located)
          + "/" + (summary.road_vehicles == null ? "?" : summary.road_vehicles) + " 定位成功"
          + " · 有车路段 " + (summary.segments_with_traffic == null ? "?" : summary.segments_with_traffic);
      }
      if (state.counts.ALARM > 0) {
        console.warn("[地图] 道路拥堵报警 " + state.counts.ALARM + " 段（"
          + "拥堵 " + state.counts.WARN + " 段）");
      }

      loadGeometry(map).then(function (geometry) {
        state.geometry = geometry;
        ensureRendered(map);
      }).catch(function (error) {
        console.error("[地图] 道路几何加载失败", error);
        if (state.foot) hint(state.foot, "道路几何没生成：先跑 tools/build-road-geometry.py");
      });

      // 继续排下一次。用 setTimeout 串（不是 setInterval）：只拉 JSON、不碰渲染，
      // 而且标签页在后台时直接跳过，别让它在后台空转。
      if (state.refreshTimer) clearTimeout(state.refreshTimer);
      var schedule = function () {
        state.refreshTimer = setTimeout(function () {
          if (document.hidden) { schedule(); return; }
          loadTraffic(map, false);
        }, REFRESH_MS);
      };
      schedule();
    }).catch(function (error) {
      // 还没采过 / 服务没在跑：面板上给一句人话，别只在控制台报错
      console.warn("[地图] 道路路况数据还不可用：", error.message);
      if (!state.panel) {
        var box = map.panel.addGroup("道路拥堵");
        state.panel = box;
        var note = text("div", "color:#8fa6bb;font-size:11px;white-space:normal",
          "还没有路况数据。需要：① 游戏在跑（1x、别暂停）→ mod 会每 5 分钟自己采一份；"
          + "② 地图服务在跑（它会自动把新数据切出来）；③ 跑一次 tools/build-road-geometry.py 出几何。");
        box.appendChild(note);
      }
    });
  }

  function start(map) {
    if (state.ready || !map) return;
    state.ready = true;
    state.map = map;
    // 先挂每帧回调再画东西：渲染中途抛错就不会让回调挂不上（踩过：图标黏在原地不动）
    map.onViewport(function () { applyZoom(map); });
    loadTraffic(map, true);
  }

  if (window.TPF2Map) start(window.TPF2Map);
  else window.addEventListener("tpf2map:ready", function () { start(window.TPF2Map); });
})();
