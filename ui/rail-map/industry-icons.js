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
  // 货流数据（1.5 MB）—— 用来判「这个产业到底有没有在干活」：
  //   只要它没出现在任何一条货流里，就是**未启用**，整组调灰（用户 2026-10-03 要求）。
  var FREIGHT_URL = 'layers/freight-data.json';
  var ICON_DIR = 'icons/cargo/';

  // 🔴 这个 12 是**设计基准**，不等于屏幕像素 —— 实际大小由下面的 ICON_SIZE_M
  //    经「世界米 → 屏幕像素」换算后缩放得到（见 updatePositions）。
  var ICON_SIZE = 12;
  var ICON_GAP = 2;          // 相邻图标的间距
  var ARROW_WIDTH = 11;      // 「原料 → 产品」之间那个箭头的宽度
  var PLUS_WIDTH = 6;        // 多个原料之间那个 `+` 的宽度

  // 图标在**世界**里代表多大（米）：屏幕尺寸 = ICON_SIZE_M × baseScale × zoom。
  // 这样它就和站台、线路一样**真正跟着地图缩放**，而不是"固定屏幕尺寸"。
  // 🔴 2026-10-03 用户报「图标这么大，也没缩放啊」的根因：
  //    上一版写的是 clamp(zoom, 0.8, 3)，而 zoom 的实际范围是 **1 ~ 256**
  //    （`network-app.js` 的 `setZoom`：`Math.max(1, Math.min(256, value))`），
  //    所以 zoom 一超过 3 图标就锁死 48 px —— 缩放它当然不动，而且偏大。
  // 取 90 m：本存档产业占地中位约 200 m，整行图标大致等于"一座产业的一半"。
  // 👉 **觉得偏大／偏小就改这个数**（调大 = 图标更大），它是唯一的总开关。
  var ICON_SIZE_M = 90;
  // 屏幕像素的上下限：太小看不清，太大只剩遮挡。
  var ICON_MIN_PX = 6;
  var ICON_MAX_PX = 36;

  // 点击热区在图标上下各多出来的高度。图标只有 16 px 高，
  // 用户 2026-10-03 反馈「点击点太小了很难点上」⇒ 热区撑到约 32 px 高。
  var HIT_PAD_Y = 8;
  // 缩到比这还小才整层收起来。**原来是 1.4，2026-10-03 降到 1.0（≈ 基本不再收起）**：
  // 图标现在跟着地图一起缩小（见 updatePositions），"总览下固定尺寸的图标会糊满地图"
  // 这个前提已经不成立；而用户的原话是「全局总览的时候非常小也没关系」，不是"干脆别显示"。
  // 1.0 正是 `setZoom` 的下限（zoom ∈ [1, 256]），所以等于全局视图也照画。
  var MIN_ZOOM = 1.0;

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

  // 扫一遍货流，得出两件事（用户 2026-10-03）：
  //   ① active      —— 有物流的产业（其余调灰，用户："没有任何物流即可"）
  //   ② inboundOnly —— **只进不出**：有进货、没出货。用户的原话是「正在规划交通线中」——
  //      进料线通了，往外运的那条线还没建/还没排，所以单独标出来。
  // 实测本存档：214 个产业 → 140 个有物流（74 个调灰）、**只进不出 1 个**（郑州工具厂）。
  // ⚠️ 判据只用现成字段，不猜含义、不加阈值。读不到货流数据时返回 null（= 什么都不做）。
  function scanIndustries(freight) {
    if (!freight) return null;
    var active = new Set(), inbound = new Set(), outbound = new Set();
    var stockToIndustry = new Map();
    (freight.industry_index || []).forEach(function (row) {
      var ind = Number(row.industry), stock = Number(row.stock);
      if (Number.isFinite(ind) && Number.isFinite(stock)) stockToIndustry.set(stock, ind);
    });
    (freight.links || []).forEach(function (link) {
      var source = Number(link.source_industry), target = Number(link.target_industry);
      if (source > 0) { active.add(source); outbound.add(source); }
      if (target > 0) { active.add(target); inbound.add(target); }
      var stock = Number(link.source_stock);
      if (stock > 0 && stockToIndustry.has(stock)) {
        var owner = stockToIndustry.get(stock);
        active.add(owner);
        outbound.add(owner);                 // 库存被运走 = 它在出货，不算"只进不出"
      }
    });
    var inboundOnly = new Set();
    inbound.forEach(function (id) { if (!outbound.has(id)) inboundOnly.add(id); });
    return { active: active, inboundOnly: inboundOnly };
  }

  // ── 状态 ────────────────────────────────────────────────────────────────────
  var state = {
    map: null,
    items: [],            // 每个产业一个条目
    group: null,
    // 总开关默认**开**（用户 2026-10-02 要求"产业的图表改为默认显示"）。
    // 注意它跟下面的 kind 子开关是"与"关系：只有 state.kinds[key] 明确为 true 才画，
    // 所以 buildPanel 里必须把每个 kind 也一起置 true，光开总开关是看不到东西的。
    master: true,
    // 产业 key → bool。**这里就置 true**，不依赖 buildPanel 去填 —— 否则一旦
    // applyVisibility 早于 buildPanel 跑（数据慢、面板晚建），判据
    // `state.master && state.kinds[key] === true` 会全落空，默认显示就失效了。
    kinds: KINDS.reduce(function (acc, kind) { acc[kind.key] = true; return acc; }, {}),
    recipes: null,
    // 货流扫描结果 `{active, inboundOnly}`。null = 数据没读到 ⇒ **不做任何标记**
    //（宁可全亮也不要因为读不到数据把 214 个产业全调灰）。
    scan: null,
    lastProbe: null,
    hidden: false,        // 整层是否被"总览收起"藏起来了（见 hideAll）
    calls: 0              // updatePositions 被调用的次数（自检用：拖一下地图这个数该涨）
  };

  // 「按下记候选、松手看位移」用的临时状态（详见 buildLayer 里那段说明）。
  // 只有"指针确实从图标上按下"且"松手时位移 ≤ 5px"才算点击 —— 拖动地图经过图标不算。
  var pendingPick = null;
  // 这一次手势是不是已经由 pointerup 处理过了 —— 给兜底的 click 路径去重。
  // 🔴 **按手势去重、不按时间窗口**：用「600ms 内忽略 click」的办法会把
  //    "手快连点两个产业"里的第二次吃掉（2026-10-02 写测试时发现的）。
  var pickHandledByPointer = false;

  // 广播"选中这个产业"。所有触发路径都走这里。
  function emitSelect(id) {
    // 用事件广播而不是直接调函数：产业图标层与产业链层各自监听 tpf2map:ready，
    // 谁先加载说不准，广播能让两边解耦。
    window.dispatchEvent(new CustomEvent('tpf2industry:select',
      { detail: { id: id, source: 'map' } }));
  }

  // ===== 启动 =================================================================

  function boot(map) {
    state.map = map;

    // 为什么不在图标上直接挂 `click`：见 buildLayer 里的长注释（主文件的指针捕获会把
    // click 重定向到 svg，子元素上的 click 永远收不到）。这里统一在 window 上收口。
    // 每次新的按下先清一遍 —— 顺手也把上一次没配对的候选清掉（正常不会有，
    // 但 pointerdown 与 pointerup 万一不配对时，清掉比留个陈旧候选安全）。
    window.addEventListener('pointerdown', function () {
      pickHandledByPointer = false;
      pendingPick = null;
    }, true);
    window.addEventListener('pointerup', function (event) {
      var hit = pendingPick;
      pendingPick = null;
      if (!hit || event.pointerId !== hit.pointerId) return;
      // 这次手势**是从图标上开始的** ⇒ 无论最后算不算"点击"，都先把这个标记立起来，
      // 免得随后补发的 click 再来一遍。特别是拖动的情形：位移超了不选中，
      // 但如果不立标记，松手后那个 click 会让它"莫名其妙选中刚拖过的那个产业"。
      pickHandledByPointer = true;
      if (Math.hypot(event.clientX - hit.x, event.clientY - hit.y) > 5) return;   // 是拖动
      emitSelect(hit.id);
    }, true);
    window.addEventListener('pointercancel', function () { pendingPick = null; }, true);
    window.addEventListener('blur', function () { pendingPick = null; });

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
      }),
      // 货流数据只为判「未启用」，读不到也不该拦住这一层 → 自己吞掉错误返回 null。
      fetch(FREIGHT_URL, { cache: 'no-store' }).then(function (r) {
        if (!r.ok) throw new Error('freight-data: ' + r.status);
        return r.json();
      }).catch(function (error) {
        console.warn('[地图] 产业图标：货流数据读不到，不做「未启用」灰化', error);
        return null;
      })
    ]).then(function (results) {
      state.recipes = results[1].industries || {};
      state.scan = scanIndustries(results[2]);
      if (state.scan) {
        var allPoints = results[0].points || [];
        var idle = allPoints.filter(function (p) { return !state.scan.active.has(p[3]); }).length;
        console.log('[地图] 产业图标：' + state.scan.active.size + ' 个有物流 · '
          + idle + ' 个未启用（调灰） · '
          + state.scan.inboundOnly.size + ' 个只进不出（琥珀虚线框，出货线还没规划）');
      }
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

      // 🔴 地图上直接点产业就选中（用户 2026-10-02：「我不想在左边的栏里面选，
      //    我根本不知道是哪一个，我要在地图上直接点击」）。
      //    父层写了 `pointer-events:none`，但**子元素可以自己再打开** —— 这是 SVG 的规矩，
      //    跟 visibility/display 不一样，pointer-events 不是"封锁"。
      // 🔴 **不要**在 pointerdown 上 stopPropagation：那会把地图拖拽挡掉。
      //    主文件的做法是「按下后移动超过 4px 就在捕获阶段吞掉这次 click」，
      //    所以拖动经过图标既照常平移、也不会误选中。
      //
      // 🔴🔴 2026-10-02 修：**不能再只挂 `click`** —— 用户反馈「点产业没反应」，根因是
      //    主文件在 svg 的 pointerdown 里调了 `svg.setPointerCapture()`，
      //    **指针捕获会把随后的 pointerup / mouseup 统统重定向到捕获元素（svg）**，
      //    浏览器据此算出来的 `click` 目标是「按下点与松开点的最近公共祖先」= svg，
      //    压根不会派发到我们这些子元素上 ⇒ 挂在 `<g>` 上的 click 永远不触发。
      //    📌 **反证在主文件自己身上**：站点标记（network-app.js 那两行 `data-station-id`
      //    的 group）之所以点得动，是因为它挂了一句
      //    `group.addEventListener('pointerdown', e => e.stopPropagation())` ——
      //    pointerdown 传不到 svg，捕获就不会被设上，click 才照常落到自己头上。
      //    我们为了不挡地图拖拽**故意没有拦** pointerdown，正好掉进这个陷阱。
      //    （`node --check` 查不出这种问题，只能按运行时语义推 + 真机验。）
      // ⇒ 改成自己做「按下记候选、松手看位移」：
      //    · pointerdown 在图标上**先**触发 —— 地图那个监听器在祖先 svg 上、又是冒泡阶段，
      //      跑不过目标元素自己；
      //    · 松手在 window 的**捕获阶段**收（指针被 svg 捕获后事件照样冒泡到 window）；
      //    · 位移 ≤ 5px 才算点击（主文件那边是 4px，这里留一点余量）。
      //    这样不依赖浏览器怎么处理指针捕获，拖动地图经过图标也不会误选。
      var entityId = point[3];
      // 「未启用」= 一条货流都不沾（判据见 scanIndustries）。
      // state.scan 为 null（货流数据没读到）时**不做任何标记** —— 宁可全亮也别全灰。
      var inactive = state.scan ? !state.scan.active.has(entityId) : false;
      // 「只进不出」= 有进货、没出货 —— 往外运的交通线还在规划（用户 2026-10-03）。
      var inboundOnly = state.scan ? state.scan.inboundOnly.has(entityId) : false;
      var item = map.S('g', {
        'pointer-events': 'all',
        style: inactive ? 'cursor:pointer;filter:grayscale(1)' : 'cursor:pointer',
        'data-industry-id': entityId,
        'data-inactive': inactive ? '1' : '0',
        'data-inbound-only': inboundOnly ? '1' : '0'
      }, '', group);
      // 原生 SVG title → 浏览器自带的悬停提示，不依赖主文件那套 tooltip
      map.S('title', {}, (name || '（无名产业）') + '（产业 ' + entityId + '）· 点击选中', item);
      item.addEventListener('pointerdown', function (event) {
        if (!event.isPrimary || event.button !== 0) return;   // 只认左键 / 主指针
        pendingPick = { id: entityId, pointerId: event.pointerId, x: event.clientX, y: event.clientY };
      });
      // 兜底：万一将来主文件不再用指针捕获（或浏览器改了行为），click 这条路也能选中。
      // 去重按**手势**：同一次按下里 pointerup 已经处理过，就忽略紧随其后的 click
      // （按下时那个 window 监听器会把这个标记清掉，所以下一次点击照常生效）。
      item.addEventListener('click', function (event) {
        if (event.button !== 0) return;
        if (pickHandledByPointer) { pickHandledByPointer = false; return; }   // 这次手势已处理过
        event.preventDefault();
        emitSelect(entityId);
      });
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

      // 「未启用」铺一块**灰色底板**（用户 2026-10-03：煤炭这类图标本身就是灰黑的，
      // 光靠 `filter: grayscale` 根本分辨不出来 —— 得有底色才认得出）。
      // ⚠️ 必须画在槽位循环**之前**：它是底层，后面的图标要压在它上面。
      if (inactive) {
        map.S('rect', {
          x: (-total / 2 - 3).toFixed(1),
          y: (-ICON_SIZE / 2 - 3).toFixed(1),
          width: (total + 6).toFixed(1),
          height: (ICON_SIZE + 6).toFixed(1),
          rx: 3,
          fill: '#9aa0a6',
          opacity: 0.8,
          'pointer-events': 'none'
        }, '', item);
      }

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

      // 点击热区：图标本身只有 ICON_SIZE 高，实测「很难点上」（用户 2026-10-03）。
      // 铺一块透明矩形把可点区域撑到**整行宽 × 约 32 px 高**；事件照样冒泡到 item 上的监听器。
      // ⚠️ 必须 `fill:transparent` + `pointer-events:all` —— 用 `fill:none` 指针会直接穿过去。
      map.S('rect', {
        x: (-total / 2 - 4).toFixed(1),
        y: (-ICON_SIZE / 2 - HIT_PAD_Y).toFixed(1),
        width: (total + 8).toFixed(1),
        height: (ICON_SIZE + HIT_PAD_Y * 2).toFixed(1),
        fill: 'transparent',
        'pointer-events': 'all'
      }, '', item);

      // 「只进不出」的产业套一圈**琥珀虚线框** —— 用户 2026-10-03：
      // 「只有进货没有出货的、正在规划交通线中，也特殊标注一下」。
      // 和「未启用」的灰化是两件事：**灰化 = 完全没有物流；虚线框 = 进得来、出不去**。
      if (inboundOnly) {
        map.S('rect', {
          x: (-total / 2 - 3.5).toFixed(1),
          y: (-ICON_SIZE / 2 - 3.5).toFixed(1),
          width: (total + 7).toFixed(1),
          height: (ICON_SIZE + 7).toFixed(1),
          rx: 3,
          fill: 'none',
          stroke: '#e0a33a',
          'stroke-width': 1.3,
          'stroke-dasharray': '3 2',
          'pointer-events': 'none'
        }, '', item);
      }

      // 只画图标，不在地图上写产业名 —— 名字在「产业链」面板的列表里看。
      // 这里原本还有一套「放大到几倍才显示名字 + 名字之间做碰撞规避」的逻辑，
      // 已经整段删掉：本层不再按缩放分级，只保留「缩到总览就整层消失」这一条。
      state.items.push({
        id: entityId,
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
    // worldPerPx 也进指纹：窗口 resize 会改 baseScale（= 每米多少像素），
    // 而 resize 不一定改 origin —— 少了它，改窗口大小后图标尺寸不会跟着更新。
    var worldPerPx = typeof map.worldPerMeter === 'function' ? map.worldPerMeter() : 1;
    var probe = map.currentZoom() + '|' + origin.x + '|' + origin.y + '|' + worldPerPx;
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

    // 图标跟着地图缩放（用户 2026-10-03：「图标大一点、做成随地图缩放的」，
    // 紧接着又补「再缩小图标就要同步缩放了」）。做法是把它按**世界尺寸**换算成屏幕像素：
    //     屏幕像素 = ICON_SIZE_M × baseScale × zoom
    // 和站台、线路用的是同一套换算 ⇒ **放大、缩小都同步**，
    // 不会再出现旧写法那种"缩到某个值就不动"（旧：clamp(zoom, 0.8, 3)，
    // 而 zoom 最小就是 1 ⇒ 下限从未生效、上限 3 一碰就锁死，等于只能放大不能缩小）。
    // 最后卡在 [ICON_MIN_PX, ICON_MAX_PX]：太小看不清、太大只剩遮挡。
    var iconPixels = ICON_SIZE_M * worldPerPx * zoom;
    var iconScale = Math.max(ICON_MIN_PX, Math.min(ICON_MAX_PX, iconPixels)) / ICON_SIZE;

    state.items.forEach(function (item) {
      var q = map.screenPoint({ x: item.x, y: item.y });
      item.item.setAttribute('transform',
        'translate(' + q.x.toFixed(1) + ' ' + q.y.toFixed(1) + ') scale(' + iconScale.toFixed(3) + ')');
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
      checked: true,
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
      // 默认就把这一类的开关置 true —— 只改面板勾选框不改这里，是看不到图标的
      // （渲染判据是 `state.master && state.kinds[key] === true`）。
      state.kinds[kind.key] = true;
      var recipe = state.recipes[kind.key] || {};
      var ins = (recipe.inputs || []).join('+') || '（直接采集）';
      var outs = (recipe.outputs || []).join('/') || '?';
      add(list, kind.label, {
        checked: true,
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
    // ⚠️ 这两个按钮**不再直接改 state**：改成拨一下勾选框 + 派发 change 事件，
    //    让面板统一的那条路（写记忆 → 应用）跑一遍。
    //    直接改 state 会出现两种错位：① 界面显示"没勾"、其实生效了；
    //    ② 勾选状态记不下来（2026-10-02 加了勾选记忆之后，这一条才成问题）。
    var setBoxes = function (value) {
      masterBox.checked = value;
      masterBox.dispatchEvent(new Event('change'));
      list.querySelectorAll('input[type=checkbox]').forEach(function (box) {
        box.checked = value;
        box.dispatchEvent(new Event('change'));
      });
    };
    makeButton('全选', '勾上所有类型并打开总开关', function () { setBoxes(true); });
    makeButton('全不选', '全部收起（总开关也一起关）', function () { setBoxes(false); });
    group.appendChild(bulk);
  }
})();
