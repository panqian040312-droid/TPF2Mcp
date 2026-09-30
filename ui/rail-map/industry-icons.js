// 产业图标层（只读）—— 用**游戏原版图标**画出每个产业的「原料 → 产品」
//
// 用户 2026-09-30 诉求：
//   ① 地图上的产业要能一眼认出是什么，**用游戏原版图标**，不要自造；
//   ② 「加工厂是一个或者两个原料生成一个产品，这个关系也要写出来」。
//   游戏里产业头顶就是 `原料图标[ 原料图标] > 产品图标`，这里照着画。
//
// ── 图标从哪来 ────────────────────────────────────────────────────────────────
// 游戏本体的 UI 纹理包 `res/textures/ui/ui.zip` 里，`hud/cargo_*@2x.tga` 是一套 50×50 的
// **货物图标**（橙多面体=铁矿、蓝水滴=原油、紫立方=塑料、淡蓝扳手=工具、褐纸箱=成品…）。
// TGA 浏览器不认，先由 `tools/extract-industry-icons.py` 转成 PNG 放在 `ui/rail-map/icons/cargo/`。
//
// 为什么不用另一套 `construction/industry/*.tga`：那是 240×150 的等轴测**产业全景图**
// （露天矿坑、农场鸟瞰），当地图标记太大太糊。适合当标记的是这里这套方形小图标。
//
// ── 配方从哪来 ────────────────────────────────────────────────────────────────
// `ui/rail-map/industry-recipes.json`，由 `tools/extract-industry-recipes.py` 从
// `res/construction/construction.zip` 的 `industry/*.con` 里解析出来（游戏自己的定义，权威）。
// 例：钢铁厂 = 铁矿 + 煤 → 钢；加工厂 = 塑料 + 钢 → 成品；煤矿 = （无原料）→ 煤。
//
// ── 产业类型怎么认 ────────────────────────────────────────────────────────────
// 游戏没把产业类型采出来（mod 里 `industry_type` 是硬编码的 UNKNOWN），只能**从产业名推**。
// 命名很规整：城市名 + 类型（"Zhongshan铁矿"、"Pune森林"、"Jeddah食物加工厂"），
// 实测 215 个全部能归类。
// ⚠️ 匹配顺序必须**长词在前**，否则"食物加工厂"会被"加工厂"或"厂"抢走。
//
// ── 坐标与刷新 ────────────────────────────────────────────────────────────────
// 挂 svg 根、用 screenPoint() 每帧重算 —— 图标要"固定屏幕尺寸"；
// 挂进 mapLayer 会跟缩放一起变大变小。每帧重绘统一走 TPF2Map.onViewport，
// **不要**自己开 rAF/setInterval（会跟地图的绘制节奏错开一帧，拖动时滞后）。

(function () {
  'use strict';

  var OVERVIEW_URL = '/layers/industry-overview.json';
  var RECIPE_URL = 'industry-recipes.json';
  var ICON_DIR = 'icons/cargo/';

  // 每个图标在屏幕上的边长。原图 50×50。
  // 用户 2026-09-30 反馈：「这个缩放下还行，放大了就太大了」—— 从 16 收到 12。
  var ICON_SIZE = 12;
  var ICON_GAP = 2;          // 相邻图标的间距
  var ARROW_WIDTH = 11;      // 「原料 → 产品」之间那个箭头的宽度
  var PLUS_WIDTH = 6;        // 多个原料之间那个 `+` 的宽度
  // 缩到比这还小（也就是全局总览）时**整层收起来** —— 这是本层唯一一条跟缩放有关的规则。
  // 用户原话：「全局总览的时候甚至是可以不显示的，非常小也没关系」——
  // 总览下 200 多组图标会糊满地图，而那时本来也看不清细节，不如不画。
  var MIN_ZOOM = 1.4;

  // ── 产业名关键词 → 产业类型 key ────────────────────────────────────────────
  // ⚠️ key 必须与 industry-recipes.json 的键（= 游戏 .con 文件名）完全一致，
  //    配方和图标都是靠它查的。顺序即优先级，**长词必须在前**。
  // 类型表搬到 `industry-kinds.js` 了 —— 图标层和产业链层共用一份，免得两处走样。
  // （那张表必须在本文件之前加载，index.html 里就是这么排的。）
  var KIND_API = window.TPF2IndustryKinds;
  var KINDS = KIND_API ? KIND_API.LIST : [];

  function kindOf(name) {
    return KIND_API ? KIND_API.of(name) : null;
  }

  var KIND_BY_KEY = {};
  KINDS.forEach(function (kind) { KIND_BY_KEY[kind.key] = kind; });

  // 货物名（"IRON_ORE"）→ 图标文件（"cargo_iron_ore"）。
  // 游戏这两套命名是对齐的：cargo_types 目录下就是 iron_ore.cargo.lua，图标就是 cargo_iron_ore。
  function cargoIconFile(cargoName) {
    return ICON_DIR + 'cargo_' + String(cargoName).toLowerCase() + '.png';
  }

  // ── 状态 ────────────────────────────────────────────────────────────────────
  var state = {
    map: null,
    items: [],            // 每个产业一个条目
    group: null,
    master: false,        // 总开关，默认关（215 组图标一起上会糊满地图）
    kinds: {},            // 产业 key → bool
    recipes: null,
    lastProbe: null,
    hidden: false,        // 整层是否被"总览收起"藏起来了（见 hideAll）
    calls: 0              // updatePositions 被调用的次数（自检用：拖一下地图这个数该涨）
  };

  // ===== 启动 =================================================================

  function boot(map) {
    state.map = map;
    Promise.all([
      fetch(OVERVIEW_URL, { cache: 'no-store' }).then(function (r) {
        if (!r.ok) throw new Error('industry-overview: ' + r.status);
        return r.json();
      }),
      fetch(RECIPE_URL, { cache: 'no-store' }).then(function (r) {
        if (!r.ok) throw new Error('industry-recipes: ' + r.status);
        return r.json();
      }).catch(function (error) {
        // 配方拿不到就只画产品图标 —— 别让整层挂掉
        console.warn('[地图] 产业图标：配方数据读不到，只画产品图标', error);
        return { industries: {} };
      })
    ]).then(function (results) {
      state.recipes = results[1].industries || {};
      buildLayer(map, results[0].points || []);
    }).catch(function (error) {
      console.error('[地图] 产业图标：读数据失败', error);
    });
  }

  if (window.TPF2Map) {
    boot(window.TPF2Map);
  } else {
    window.addEventListener('tpf2map:ready', function () { boot(window.TPF2Map); }, { once: true });
  }

  // ===== 画图层 ===============================================================

  function buildLayer(map, points) {
    if (!points.length) {
      console.warn('[地图] 产业图标：产业数据是空的，不建层');
      return;
    }

    var group = map.S('g', { id: 'industry-icon-layer', 'pointer-events': 'none' }, '', map.svg);
    state.group = group;
    // 🔴 每帧回调**必须在画任何东西之前就挂上**。
    //    放在函数末尾曾经出过事：渲染中途一旦抛错，后面的注册就整段跳过 ——
    //    图标照样画出来了，却永远不跟着地图走（拖动画布，图标黏在原地）。
    //    先注册，后面再抛错最多是少几个图标，不会整层黏住。
    map.onViewport(updatePositions);

    var tally = {};
    var missing = [];

    points.forEach(function (point) {
      // 每条 7 个元素：[x, y, level, entity_id, name, 占地x, 占地y]
      var x = point[0];
      var y = point[1];
      var name = point[4];
      if (typeof x !== 'number' || typeof y !== 'number') return;

      var kind = kindOf(name);
      tally[kind.label] = (tally[kind.label] || 0) + 1;
      if (name == null || name === '') missing.push(point[3]);

      var recipe = state.recipes[kind.key] || {};
      var inputs = recipe.inputs || [];
      var outputs = recipe.outputs || [];
      if (!outputs.length) outputs = ['GOODS'];      // 配方缺了就画个成品箱子，别留空

      var item = map.S('g', {}, '', group);
      var slots = [];
      // 读起来就是「甲 + 乙 → 丙」：多个原料之间用 `+` 连，原料与产品之间用箭头。
      inputs.forEach(function (cargo, index) {
        if (index > 0) slots.push({ type: 'plus' });
        slots.push({ type: 'icon', cargo: cargo });
      });
      if (inputs.length && outputs.length) slots.push({ type: 'arrow' });
      outputs.forEach(function (cargo) { slots.push({ type: 'icon', cargo: cargo }); });

      var widthOf = function (slot) {
        if (slot.type === 'arrow') return ARROW_WIDTH;
        if (slot.type === 'plus') return PLUS_WIDTH;
        return ICON_SIZE;
      };

      // 整行居中在产业坐标上：先算总宽，再从 -总宽/2 往右摆
      var total = 0;
      slots.forEach(function (slot) { total += widthOf(slot); });
      total += Math.max(0, slots.length - 1) * ICON_GAP;

      var cursor = -total / 2;
      slots.forEach(function (slot) {
        var holder = function () {
          return map.S('g', { transform: 'translate(' + cursor.toFixed(1) + ' 0)' }, '', item);
        };
        if (slot.type === 'arrow') {
          // 带箭杆的箭头（不是 `>` 折线）：一横 + 一个箭头两撇
          var tip = ARROW_WIDTH - 1.5;
          var back = tip - 4;
          map.S('path', {
            d: 'M0,0 L' + tip.toFixed(1) + ',0 M' + back.toFixed(1) + ',-3.4 L'
              + tip.toFixed(1) + ',0 L' + back.toFixed(1) + ',3.4',
            fill: 'none', stroke: '#e8f2f8', 'stroke-width': '1.5',
            'stroke-linecap': 'round', 'stroke-linejoin': 'round'
          }, '', holder());
        } else if (slot.type === 'plus') {
          map.S('path', {
            d: 'M-2.6,0 L2.6,0 M0,-2.6 L0,2.6',
            fill: 'none', stroke: '#cfe2ee', 'stroke-width': '1.5',
            'stroke-linecap': 'round'
          }, '', holder());
        } else {
          map.S('image', {
            href: cargoIconFile(slot.cargo),
            x: cursor.toFixed(1),
            y: (-ICON_SIZE / 2).toFixed(1),
            width: ICON_SIZE,
            height: ICON_SIZE,
            preserveAspectRatio: 'xMidYMid meet'
          }, '', item);
        }
        cursor += widthOf(slot) + ICON_GAP;
      });

      // 只画图标，不在地图上写产业名 —— 名字在「产业链」面板的列表里看。
      // 这里原本还有一套「放大到几倍才显示名字 + 名字之间做碰撞规避」的逻辑，
      // 已经整段删掉：本层不再按缩放分级，只保留「缩到总览就整层消失」这一条。
      state.items.push({
        name: String(name == null ? '' : name),
        kind: kind,
        x: x,
        y: y,
        item: item
      });
    });

    state.kinds = {};
    KINDS.forEach(function (kind) { state.kinds[kind.key] = false; });

    buildPanel(tally, missing);
    applyVisibility();

    var summary = KINDS
      .filter(function (kind) { return tally[kind.label]; })
      .map(function (kind) { return kind.label + ' ' + tally[kind.label]; })
      .join(' / ');
    console.log('[地图] 产业图标：' + state.items.length + ' 个（' + summary + '）');
    // 自检出口：控制台敲 __industryIcons 就能看这层的状态。
    // calls = 每帧回调被调用的次数；drawn = 真正写了 transform 的次数。
    window.__industryIcons = state;
    if (missing.length) {
      console.warn('[地图] 产业图标：有 ' + missing.length + ' 个产业没名字，已按"工厂"兜底', missing.slice(0, 5));
    }
  }

  // ===== 位置：每帧重算 =======================================================

  function updatePositions() {
    // 自检计数：拖一下地图，控制台敲 __industryIcons.calls 看它涨不涨。
    // 不涨 = 每帧回调压根没接上（问题在主文件那条 hook 链）；涨而不动 = 卡在别的判断上。
    state.calls += 1;
    if (!state.group) return;
    var map = state.map;

    // 视口没动就整段跳过 —— 200 多个元素每帧重写 transform 是纯浪费。
    // 指纹用 (缩放, 世界原点在屏幕上的位置)：给定这两个值，平移量是唯一解。
    var origin = map.screenPoint({ x: 0, y: 0 });
    var probe = map.currentZoom() + '|' + origin.x + '|' + origin.y;
    if (probe === state.lastProbe) return;
    state.lastProbe = probe;

    var zoom = map.currentZoom();

    // 全局总览：整层收起来。这一层只管"这层该不该出现"；
    // 每个产业自己的显隐仍由总开关 + 类型筛选控制（见 applyVisibility）。
    if (zoom < MIN_ZOOM) {
      hideAll();
      return;
    }
    showAll();

    state.items.forEach(function (item) {
      var q = map.screenPoint({ x: item.x, y: item.y });
      item.item.setAttribute('transform', 'translate(' + q.x.toFixed(1) + ' ' + q.y.toFixed(1) + ')');
    });
  }

  // ===== 可见性 ===============================================================

  function applyVisibility() {
    state.items.forEach(function (item) {
      var show = state.master && state.kinds[item.kind.key] === true;
      item.item.setAttribute('visibility', show ? 'visible' : 'hidden');
    });
  }

  // 整层收起 / 展开（缩到全局总览时用）。
  //
  // ⚠️ 这里必须用 display，绝不能用 visibility。visibility 是**继承**属性，
  // 而 applyVisibility() 会给每个图标显式写 visibility="visible" ——
  // 子元素显式设的值会盖过父元素的 hidden，于是父级那层的"藏"等于没藏。
  // 后果特别隐蔽：缩到总览时层没藏住（图标还亮着），偏偏下面的位置更新又被
  // `return` 跳过了 —— 图标就黏在原地，拖动地图它不动。2026-09-30 踩到。
  // display:none 是让整个子树不生成渲染盒，子元素怎么设都盖不过来。
  function hideAll() {
    if (state.hidden) return;          // 状态没变就别每帧写 style
    state.hidden = true;
    state.group.style.display = 'none';
  }

  function showAll() {
    if (!state.hidden) return;
    state.hidden = false;
    state.group.style.display = '';
  }

  // ===== 图层面板 =============================================================

  function buildPanel(tally) {
    var map = state.map;
    var panelApi = map.panel;
    if (!panelApi || typeof panelApi.addGroup !== 'function') {
      console.warn('[地图] 产业图标：面板接口不可用，只画不加开关（默认隐藏）');
      return;
    }
    var group = panelApi.addGroup('产业 · 图标');
    var add = panelApi.addOption;

    var masterBox = add(group, '产业图标（全部）', {
      checked: false,
      count: state.items.length,
      title: '用游戏原版图标画出每个产业的「原料 + 原料 → 产品」。'
        + '图标固定在屏幕上大小不变；缩到全局总览（1.4 倍以下）时整层自动收起。'
        + '产业名请在「产业链」面板的列表里看',
      onChange: function (checked) { state.master = checked; applyVisibility(); }
    });

    // 类型多（十六种），塞进一个可滚动的子容器，免得把面板撑老长
    var list = document.createElement('div');
    list.className = 'layer-subgroup is-scroll';
    list.setAttribute('style', 'max-height:150px;overflow:auto');
    group.appendChild(list);

    var keys = [];
    KINDS.forEach(function (kind) {
      var count = tally[kind.label];
      if (!count) return;
      keys.push(kind.key);
      var recipe = state.recipes[kind.key] || {};
      var ins = (recipe.inputs || []).join('+') || '（直接采集）';
      var outs = (recipe.outputs || []).join('/') || '?';
      add(list, kind.label, {
        checked: false,
        count: count,
        title: '名字里含「' + kind.words.join(' / ') + '」的产业；配方 ' + ins + ' → ' + outs,
        onChange: function (checked) {
          state.kinds[kind.key] = checked;
          applyVisibility();
        }
      });
    });

    var bulk = document.createElement('div');
    bulk.className = 'layer-bulk';
    var makeButton = function (text, hint, handler) {
      var button = document.createElement('button');
      button.type = 'button';
      button.textContent = text;
      button.title = hint;
      button.onclick = handler;
      bulk.appendChild(button);
    };
    // ⚠️ 这两个按钮是直接改 state 的，必须把勾选框也同步设上，否则界面显示"没勾"、用户以为没生效。
    makeButton('全选', '勾上所有类型并打开总开关', function () {
      state.master = true;
      masterBox.checked = true;
      keys.forEach(function (key) { state.kinds[key] = true; });
      list.querySelectorAll('input[type=checkbox]').forEach(function (box) { box.checked = true; });
      applyVisibility();
    });
    makeButton('全不选', '全部收起（总开关也一起关）', function () {
      state.master = false;
      masterBox.checked = false;
      keys.forEach(function (key) { state.kinds[key] = false; });
      list.querySelectorAll('input[type=checkbox]').forEach(function (box) { box.checked = false; });
      applyVisibility();
    });
    group.appendChild(bulk);
  }
})();
