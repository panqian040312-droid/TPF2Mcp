(async () => {
  await window.RAIL_MAP_TEMPLATES_READY;
  const query = new URLSearchParams(window.location.search);
  if (query.get('view') !== 'local') {
    window.renderRailNetwork();
    return;
  }

  const templates = window.RailMapTemplates;
  const manifest = window.RAIL_NETWORK_DATA;
  const stationIdText = query.get('station');
  const stationId = /^\d+$/.test(stationIdText || '') ? Number(stationIdText) : null;
  const $svg = $('#board');
  const $tooltip = $('#track-tooltip');
  const $boardWrap = $('#board-wrap');
  let zoom = 1;
  let panX = 0;
  let panY = 0;
  let dragging = false;
  let pointerId = null;
  let lastX = 0;
  let lastY = 0;
  const NS = 'http://www.w3.org/2000/svg';
  const S = (tag, attrs = {}, text = '', $parent = $svg) => {
    const $node = $(document.createElementNS(NS, tag)).attr(attrs);
    if (text !== '') $node.text(text);
    $parent.append($node);
    return $node;
  };
  const showMessage = (code, message, warning = true) => {
    const sidebar = templates.instantiate('pending-sidebar-template');
    templates.slot(sidebar, 'message').appendChild(templates.message(code, message, warning));
    $('#sidebar').empty().append(sidebar);
    S('text', {
      x: 600, y: 360, fill: warning ? '#ffbd52' : '#c8f3ff',
      'font-size': 16, 'text-anchor': 'middle', 'font-family': 'Microsoft YaHei',
    }, message);
  };

  $('#local-view').addClass('selected').off('.stationPreview').on('click.stationPreview', event => event.preventDefault());
  $('#network-view').removeClass('selected').off('.stationPreview').on('click.stationPreview', event => {
    event.preventDefault();
    const target = new URL(window.location.href);
    target.search = '';
    target.searchParams.set('view', 'network');
    window.location.assign(target.href);
  });

  if (!stationId) {
    $('#station-name').text('未选择枢纽');
    $('.mode').text('HUB · NO SELECTION');
    showMessage('SELECT', '先在全网视图点一个车站，再点侧边栏的「查看整个枢纽」');
    return;
  }
  const stationIndex = manifest?.stations?.find(item => item.entity_id === stationId);
  if (!stationIndex) {
    $('#station-name').text('车站不存在');
    $('.mode').text('HUB · INVALID');
    showMessage('UNKNOWN', '当前存档中没有该车站');
    return;
  }

  $('.mode').text('HUB · 枢纽');
  $('#station-name').text(stationIndex.name || `车站 ${stationId}`);
  $('#snapshot').text(`枢纽视图 · 基准站 ${stationId}`);

  // 🔴 站场几何（`station-previews/station-<id>.json`）**改成可选** —— 2026-10-03
  //   ① 它只覆盖 73 / 565 座站（09-29 生成后再没更新过）；
  //   ② 它带 `save_id` 校验，存档一变就不认；
  //   ③ 旧代码在这两件事上**直接 throw** ⇒ 整个页面挂掉，**后面的枢纽逻辑一行都执行不到**。
  //   这就是「关联车站做了半天没做出来」的直接原因。
  //   ⇒ 现在：拿得到就画站台/轨道细节，拿不到就**只画枢纽**。枢纽才是这一页的主体。
  let preview = null;
  try {
    const cached = await $.ajax({
      url: `station-previews/station-${stationId}.json`,
      method: 'GET',
      dataType: 'json',
      cache: false,
    });
    const problems = [];
    if (cached.station?.entity_id !== stationId) problems.push('ID 不匹配');
    if (manifest?.save_id && cached.save_id !== manifest.save_id) problems.push('不属于当前存档');
    if (cached.source_status !== 'ENGINE_OBSERVED') problems.push('非引擎实测');
    if (cached.diagram_type !== 'ENGINE_OBSERVED_STATION_PHYSICAL_PREVIEW') problems.push('类型无效');
    if (problems.length) throw new Error(problems.join(' / '));
    preview = cached;
  } catch (error) {
    console.warn('[hub] 站场几何不可用，降级为只画枢纽：', (error && error.message) || error);
  }
  // 站场细节缺席时合成一个**空骨架** —— 后面的取景与绘制代码原样复用，不必处处判空。
  if (!preview) {
    const anchor = (stationIndex && stationIndex.position) || { x: 0, y: 0 };
    const PAD_M = 60;
    preview = {
      station: { entity_id: stationId },
      nodes: [], edges: [], platforms: [], station_groups: null,
      scope: null, grade_separated_crossings: null,
      bounds: {
        min: { x: anchor.x - PAD_M, y: anchor.y - PAD_M },
        max: { x: anchor.x + PAD_M, y: anchor.y + PAD_M },
      },
    };
  }

  // ===== 枢纽相关的常量与助手 ============================================
  // ⚠️ 这一整段必须待在**取景与绘制之前** —— 全是 const，
  //    放到后面会让 P()/setZoom() 一带的调用踩到暂时性死区（白屏）。
  //
  // 图标全部取自游戏本体 `res/textures/ui/ui.zip`（hud/ 与 icons/ 目录），
  // 用纯标准库写的 TGA→PNG 转换脚本导出到 `assets/icons/`，所以样式和游戏内一致。
  // 用户明确要求「码头要做成船的图标」，所以交通方式一律用**交通工具**图标
  // （vehicle_ship / vehicle_bus / vehicle_aircraft / vehicle_train_*），
  // 而不是游戏建筑上方那块"箱子 + 人"的通用站位图标（station_*）——
  // 后者四种交通方式长得几乎一样，看不出码头和汽车站的区别。
  //
  // ⚠️ 顺序即优先级（首个命中就返回）。
  // 🔴 交通方式靠**建筑文件路径**判定。这里有个坑（2026-09-29 实测）：
  //    `CONSTRUCTION.fileName` 用的是 **construction 目录**，四类站分别是
  //      `station/rail|train`（铁路）· **`station/street`（汽车站）** ·
  //      `station/water`（码头）· `station/air`（机场）
  //    —— **汽车站是 `street` 不是 `road`**！`road` 只出现在模型路径
  //    `station/road/streetstation/*.mdl` 里（另一套命名），所以只写 `/road/`
  //    会把所有汽车站判成"车站"、连图标都没有（用户 2026-09-29 报的现象）。
  //    两种写法都留着：`/street/` 匹配 construction 路径，`/road/` 匹配模型路径。
  //    `/bus/`、`/tram/` 是给 mod 自定名兜底。
  const SERVICE_KINDS = [
    ['/rail/', 'rail'], ['/train/', 'rail'],
    ['/street/', 'road'], ['/road/', 'road'], ['/bus/', 'road'], ['/tram/', 'road'],
    ['/air/', 'air'],
    ['/harbor/', 'water'], ['/water/', 'water'],
  ];
  // 交通方式 × 客货 的**二维**判断。把整座站压成一个"汽车站"会丢掉三件事：
  // ① 同一个站群常常客运货运都有；② 公路客运与公路货运是两种东西（巴士 vs 卡车）；
  // ③ 海运客运与海运货运也分开。数据来源：建筑路径给交通方式、子车站的 cargo 给客货。
  const SERVICE_TEXT = {
    'rail|pax': '铁路客运', 'rail|cargo': '铁路货运',
    'road|pax': '公路客运', 'road|cargo': '公路货运',
    'air|pax': '航空客运', 'air|cargo': '航空货运',
    'water|pax': '海运客运', 'water|cargo': '海运货运',
  };
  const SERVICE_ICON = {
    'rail|pax': 'vehicle_train_diesel', 'rail|cargo': 'vehicle_train_diesel',
    'road|pax': 'vehicle_bus', 'road|cargo': 'vehicle_truck',
    'air|pax': 'vehicle_aircraft', 'air|cargo': 'vehicle_aircraft',
    'water|pax': 'vehicle_ship', 'water|cargo': 'vehicle_ship',
  };
  // 交通方式 → 名称 / 取色 / 默认图标（图上标记与侧边栏共用同一套）
  const MODE_INFO = {
    rail: { label: '火车站', color: '#69c7e5', icon: 'vehicle_train_diesel' },
    road: { label: '汽车站', color: '#8fd58a', icon: 'vehicle_bus' },
    water: { label: '码头', color: '#5cbfe8', icon: 'vehicle_ship' },
    air: { label: '机场', color: '#c79bf0', icon: 'vehicle_aircraft' },
  };
  const HUB_ICONS = {
    '火车站': 'vehicle_train_diesel',
    '汽车站': 'vehicle_bus',
    '码头': 'vehicle_ship',
    '机场': 'vehicle_aircraft',
    '产业': 'industry',
  };
  const CARRIER_MODE = { RAIL: 'rail', ROAD: 'road', WATER: 'water', AIR: 'air' };
  // 用「线路停靠点」反推交通方式的阈值。一条线路的 `points` 就是它的停靠站坐标，
  // 站点与某个点重合即说明它停那条线，而线路自带 carrier。
  // 全量审计：565 座站里 89% 重合于 5 m 内、96% 于 100 m 内。
  // 交叉验证：73 座铁路站里 3 例误判（108 / 138 / 242 m）**全部**落在 30 m 之外 → 卡 30 m 安全。
  const HUB_POINT_MATCH_M = 30;
  const modeFromFiles = files => {
    const text = (files || []).filter(Boolean).join(' ').toLowerCase();
    if (!text) return null;
    const found = SERVICE_KINDS.find(entry => text.includes(entry[0]));
    return found ? found[1] : null;
  };
  const hubKindOfFiles = files => {
    const mode = modeFromFiles(files);
    return mode ? MODE_INFO[mode].label : null;
  };
  const hubKindByName = name => {
    const text = String(name || '');
    if (/机场|航空/.test(text)) return '机场';
    if (/港|码头/.test(text)) return '码头';
    return null;
  };
  // 把采集器给的 services（每座子车站一条 {file, cargo}）折成去重后的
  // "交通方式|客货" 键，例如 ['road|pax', 'road|cargo']。**新版采集器部署后才有。**
  const stationServices = item => {
    const keys = new Set();
    (item.services || []).forEach(service => {
      const path = String(service.file || '').toLowerCase();
      const found = SERVICE_KINDS.find(entry => path.includes(entry[0]));
      if (found) keys.add(`${found[1]}|${service.cargo ? 'cargo' : 'pax'}`);
    });
    return [...keys];
  };
  const distanceText = meters => meters < 1000 ? `${Math.round(meters)} m` : `${(meters / 1000).toFixed(2)} km`;

  // ===== 枢纽：同一换乘片（同 cluster）里的全部车站 ======================
  // 用户 2026-09-29 指出：广州北站 / 广州分站 ×2 / 广州中央车站 / 广州西站 / 广州机场 …
  // **是一整个交通枢纽**，局部图只画铁路站台等于把它拆散了。
  //   · 为什么按 cluster 而不按距离：3 km 半径在本存档会捞进 117 项（大半属于别的枢纽），
  //     而 cluster 是游戏自己的"步行可换乘"片，广州这片 28 座。全存档 73 个多成员片，
  //     跨度中位 316 m、最大 1768 m。
  //   · 数据用**已导出**的 `layers/stations-data.json`（565 座，含 cluster / position / cargo），
  //     不需要重新部署 mod。
  let hubCluster = null, hubSelf = null, hubMembers = [], hubAllStations = [], hubLinePoints = [];
  try {
    const hubResponses = await Promise.all([
      $.ajax({ url: 'layers/stations-data.json', method: 'GET', dataType: 'json', cache: false }),
      $.ajax({ url: 'layers/lines-data.json', method: 'GET', dataType: 'json', cache: false })
        .then(value => value, () => null),
    ]);
    hubAllStations = (hubResponses[0] && hubResponses[0].stations) || [];
    ((hubResponses[1] && hubResponses[1].lines) || []).forEach(line => {
      const mode = CARRIER_MODE[line.carrier];
      if (!mode) return;
      (line.points || []).forEach(point => hubLinePoints.push({ x: point.x, y: point.y, mode }));
    });
    hubSelf = hubAllStations.find(item => Number(item.entity_id) === Number(stationId)) || null;
    if (hubSelf && hubSelf.cluster != null) {
      hubCluster = Number(hubSelf.cluster);
      hubMembers = hubAllStations.filter(item => Number(item.cluster) === hubCluster);
    }
  } catch (error) {
    console.warn('[local] 站群数据读取失败，局部图只画本站', error);
  }
  // 某座站的交通方式。三条来源依次退让：
  //   ① 真实建筑类型（services / construction_files）—— 部署新版采集器后才有
  //   ② 线路停靠点反推（阈值 HUB_POINT_MATCH_M）
  //   ③ 站名兜底，只认机场/码头 —— 站名认不出汽车站（565 座里含「汽车」的是 0 座）
  const modeOf = member => {
    const byBuilding = modeFromFiles(member.construction_files)
      || modeFromFiles((member.services || []).map(service => service.file));
    if (byBuilding) return byBuilding;
    const point0 = member.position;
    if (point0 && Number.isFinite(point0.x) && hubLinePoints.length) {
      let best = null;
      for (const point of hubLinePoints) {
        const gap = Math.hypot(point.x - point0.x, point.y - point0.y);
        if (best === null || gap < best.gap) best = { gap, mode: point.mode };
      }
      if (best && best.gap <= HUB_POINT_MATCH_M) return best.mode;
    }
    const byName = hubKindByName(member.name);
    if (byName === '机场') return 'air';
    if (byName === '码头') return 'water';
    return null;
  };
  // 图标按"交通方式 × 客货"给：公路货运用卡车、公路客运用巴士，其余按方式。
  const iconOfMember = (member, mode) => {
    if (!mode) return null;
    if (mode === 'road' && member.cargo) return 'vehicle_truck';
    return MODE_INFO[mode].icon;
  };
  const HUB_VIEW_MAX_M = 2500;     // 取景硬上限：全存档最大片跨度 1768 m

  $svg.empty();
  // ⚠️ 不要直接沿用 preview.bounds —— 下面要并进枢纽成员，直接改会污染 preview。
  // 🔴 站场几何缺席时（降级模式）preview.bounds 只是 ±60 m 的**占位框**，必须丢掉：
  //    否则取景区会横跨"占位框 + 整个枢纽"，缩放小到什么都看不见（2026-10-03）。
  //    改用**枢纽中心**（hubSelf）为基准 —— 下面并进 hubMembers 后就是正确的枢纽范围。
  const hasGeometry = Array.isArray(preview.nodes) && preview.nodes.length > 0;
  const bounds = { min: { ...preview.bounds.min }, max: { ...preview.bounds.max } };
  if (!hasGeometry) {
    const base = (hubSelf && hubSelf.position) || (stationIndex && stationIndex.position) || { x: 0, y: 0 };
    const BASE_PAD_M = 40;
    bounds.min = { x: base.x - BASE_PAD_M, y: base.y - BASE_PAD_M };
    bounds.max = { x: base.x + BASE_PAD_M, y: base.y + BASE_PAD_M };
  }
  // 本站单独取景的缩放，用来算"因为并进枢纽而缩小了多少" → 标签字号要跟着放大，
  // 否则并进枢纽后站名会缩到读不出来。
  // 降级模式没有"本站单独取景"可言，直接给 null（labelBoost 取 1，不放大）。
  const stationScale = hasGeometry
    ? Math.min(
        1080 / Math.max(1, preview.bounds.max.x - preview.bounds.min.x),
        620 / Math.max(1, preview.bounds.max.y - preview.bounds.min.y),
      )
    : null;
  if (hubMembers.length > 1 && hubSelf && hubSelf.position) {
    const HUB_EDGE_MARGIN_M = 70;
    hubMembers.forEach(member => {
      const item = member.position;
      if (!item || !Number.isFinite(item.x) || !Number.isFinite(item.y)) return;
      if (Math.hypot(item.x - hubSelf.position.x, item.y - hubSelf.position.y) > HUB_VIEW_MAX_M) return;
      bounds.min.x = Math.min(bounds.min.x, item.x - HUB_EDGE_MARGIN_M);
      bounds.min.y = Math.min(bounds.min.y, item.y - HUB_EDGE_MARGIN_M);
      bounds.max.x = Math.max(bounds.max.x, item.x + HUB_EDGE_MARGIN_M);
      bounds.max.y = Math.max(bounds.max.y, item.y + HUB_EDGE_MARGIN_M);
    });
  }
  const width = Math.max(1, bounds.max.x - bounds.min.x);
  const height = Math.max(1, bounds.max.y - bounds.min.y);
  const baseScale = Math.min(1080 / width, 620 / height);
  const PLATFORM_DECK_WIDTH_M = 5.2;
  const PLATFORM_BORDER_WIDTH_M = 1.6;
  const PLATFORM_HIT_PADDING_M = 3;
  const PASSENGER_PLATFORM_COLOR = '#69c7e5';
  const CARGO_PLATFORM_COLOR = '#d6a04f';
  const platformStrokeWidths = widthUnits => {
    const deck = PLATFORM_DECK_WIDTH_M * widthUnits * baseScale;
    return {
      deck,
      outline: deck + PLATFORM_BORDER_WIDTH_M * baseScale,
      hit: deck + PLATFORM_HIT_PADDING_M * baseScale,
    };
  };
  const originX = 600 - (bounds.min.x + bounds.max.x) * baseScale / 2;
  const originY = 360 + (bounds.min.y + bounds.max.y) * baseScale / 2;
  const P = point => ({ x: originX + point.x * baseScale, y: originY - point.y * baseScale });
  const T = value => ({ x: value.x * baseScale, y: -value.y * baseScale });
  const nodeById = new Map(preview.nodes.map(node => [node.entity_id, node.position]));
  const pathForEdge = edge => {
    const a = nodeById.get(edge.node0);
    const b = nodeById.get(edge.node1);
    const pa = P(a);
    const pb = P(b);
    const fallback = { x: b.x - a.x, y: b.y - a.y };
    const tangent0 = T(edge.tangent0 || fallback);
    const tangent1 = T(edge.tangent1 || fallback);
    return `M${pa.x.toFixed(2)},${pa.y.toFixed(2)}C${(pa.x + tangent0.x / 3).toFixed(2)},${(pa.y + tangent0.y / 3).toFixed(2)} ${(pb.x - tangent1.x / 3).toFixed(2)},${(pb.y - tangent1.y / 3).toFixed(2)} ${pb.x.toFixed(2)},${pb.y.toFixed(2)}`;
  };
  const pathForPoints = points => points.map((point, index) => {
    const screen = P({ x: point[0], y: point[1] });
    return `${index ? 'L' : 'M'}${screen.x.toFixed(2)},${screen.y.toFixed(2)}`;
  }).join('');
  const $mapLayer = S('g', { id: 'station-preview-layer' });
  const $platformLayer = S('g', { id: 'station-preview-platforms' }, '', $mapLayer);
  const $trackLayer = S('g', { id: 'station-preview-tracks' }, '', $mapLayer);
  const $bridgeLayer = S('g', { id: 'station-preview-bridges' }, '', $mapLayer);
  const $switchLayer = S('g', { id: 'station-preview-switches' }, '', $mapLayer);
  // 枢纽标记层：**故意不放进 $mapLayer** —— 那一层被 clip-path 裁成"本站站场范围"
  //（见下面 `station-scope-*` 的 clipPath），而枢纽成员大多在这个范围之外，
  //  放进去会被整片裁掉（实测对照方块 0 像素）。所以它单独一层，
  //  只跟着同一套平移缩放走（transform 在 updateViewport 里同步），不做裁剪。
  const $hubLayer = S('g', { id: 'station-preview-hub' });
  // 枢纽标签层：挂 **svg 根**（屏幕坐标），尺寸不随缩放变化。
  //   ⚠️ 第一版把标签也画在世界坐标里 —— 字号用世界单位、缩放时同比放大，
  //     27 个标签的相对重叠**永远不变**，直接糊成一团黑（实测截图确认）。
  //     所以标签必须固定屏幕字号 + 逐个避让：重叠的不显示文字，放大后自然逐一展开。
  const $hubScreenLayer = S('g', { id: 'station-preview-hub-labels', 'pointer-events': 'none' });
  // 固定在图面（不随平移缩放动）的说明，文案由 updateHubMarks() 刷新
  const $hubLegend = S('text', {
    x: 58, y: 636, fill: '#9fb6c6', 'font-size': 11, 'font-family': 'Consolas, Microsoft YaHei',
  });
  const hubMarkers = [];        // { group, label, x, y } —— x/y 是底图坐标（P() 的输出）
  const HUB_MARK_PX = 18;       // 图标边长（屏幕像素）
  const HUB_LABEL_PX = 11;      // 标签字号（屏幕像素）
  // 底图坐标 → 屏幕坐标。必须与 $mapLayer 的 transform 完全一致：
  //   translate(panX panY) translate(600 360) scale(zoom) translate(-600 -360)
  const toScreen = point => ({
    x: 600 + panX + (point.x - 600) * zoom,
    y: 360 + panY + (point.y - 360) * zoom,
  });
  const updateHubMarks = () => {
    if (!hubMarkers.length) return;
    const inverse = 1 / zoom;
    const placed = [];
    hubMarkers.forEach(mark => {
      // 位置跟地图走，但尺寸固定：translate(底图坐标) 之后反向缩放掉地图的 zoom
      mark.group.setAttribute('transform',
        `translate(${mark.x.toFixed(1)} ${mark.y.toFixed(1)}) scale(${inverse.toFixed(4)})`);
      const at = toScreen(mark);
      const text = mark.label.textContent || '';
      // 粗略估宽：中文按 1em、西文按 0.62em。只用于避让，不需要精确。
      let width = 0;
      for (const ch of text) width += ch.charCodeAt(0) > 255 ? HUB_LABEL_PX : HUB_LABEL_PX * 0.62;
      // 标签放在标记**正下方居中**（比一律放右边更不容易互相压）
      const rect = {
        x: at.x - width / 2 - 2,
        y: at.y + HUB_MARK_PX / 2 + 2,
        w: width + 4,
        h: HUB_LABEL_PX * 1.5,
      };
      const clash = placed.some(other =>
        rect.x < other.x + other.w && rect.x + rect.w > other.x
        && rect.y < other.y + other.h && rect.y + rect.h > other.y);
      const onScreen = rect.x > 4 && rect.x + rect.w < 1196 && rect.y > 4 && rect.y + rect.h < 712;
      const visible = !clash && onScreen;
      mark.label.setAttribute('x', (at.x - width / 2).toFixed(1));
      mark.label.setAttribute('y', (at.y + HUB_MARK_PX / 2 + HUB_LABEL_PX).toFixed(1));
      mark.label.setAttribute('visibility', visible ? 'visible' : 'hidden');
      if (visible) placed.push(rect);
    });
    $hubLegend.text(`整个枢纽 ${hubMembers.length} 座站（同站群 #${hubCluster}）`
      + ` · 当前显示 ${placed.length}/${hubMarkers.length} 个站名（放大后逐一展开）`);
  };
  const $labelLayer = S('g', { id: 'station-preview-labels' }, '', $mapLayer);
  if (Array.isArray(preview.scope?.polygon) && preview.scope.polygon.length === 4) {
    const clipId = `station-scope-${stationId}`;
    const $definitions = S('defs');
    const $clip = S('clipPath', { id: clipId }, '', $definitions);
    const scopePoints = preview.scope.polygon.map(point => [point.x, point.y]);
    S('path', { d: `${pathForPoints(scopePoints)}Z` }, '', $clip);
    $mapLayer.attr('clip-path', `url(#${clipId})`);
  }

  preview.edges.forEach(edge => {
    if (!nodeById.has(edge.node0) || !nodeById.has(edge.node1)) return;
    S('path', {
      d: pathForEdge(edge), fill: 'none', stroke: '#83a9bd', 'stroke-width': 1.4,
      'vector-effect': 'non-scaling-stroke', 'pointer-events': 'none',
    }, '', $trackLayer);
  });
  const bridgeCrossings = preview.grade_separated_crossings || window.RailBridgeCrossings.detect(preview.edges, nodeById);
  const edgeById = new Map(preview.edges.map(edge => [Number(edge.entity_id), edge]));
  const edgePathById = new Map(preview.edges.map(edge => [Number(edge.entity_id), pathForEdge(edge)]));
  const edgeIdsByNode = new Map();
  preview.edges.forEach(edge => [edge.node0, edge.node1].forEach(nodeId => {
    const values = edgeIdsByNode.get(Number(nodeId)) || [];
    values.push(Number(edge.entity_id));
    edgeIdsByNode.set(Number(nodeId), values);
  }));
  const bridgeStructureCount = window.RailBridgeCrossings.renderSvg(bridgeCrossings, P, S, $bridgeLayer, {
    trackStrokeWidth: 1.4,
    upperPathForEdge: edgeId => edgePathById.get(Number(edgeId)),
    upperEdgeIdsForBridge: (crossing, shape) => window.RailBridgeCrossings.expandUpperEdgeIds(
      crossing, shape, edgeById, nodeById, edgeIdsByNode,
    ),
    upperPointsForEdge: edgeId => {
      const edge = edgeById.get(Number(edgeId));
      return edge ? window.RailBridgeCrossings.sampleEdge(edge, nodeById) : null;
    },
  });

  const moveTooltip = event => {
    const rect = $boardWrap[0].getBoundingClientRect();
    $tooltip.css({ left: `${event.clientX - rect.left + 12}px`, top: `${event.clientY - rect.top + 12}px` });
  };
  const sideOfPolyline = (points, point) => {
    let bestDistance = Infinity;
    let bestSide = 0;
    for (let index = 0; index + 1 < points.length; index += 1) {
      const a = points[index];
      const b = points[index + 1];
      const dx = b[0] - a[0];
      const dy = b[1] - a[1];
      const lengthSquared = dx * dx + dy * dy;
      if (lengthSquared <= 1e-9) continue;
      const ratio = Math.max(0, Math.min(1, ((point.x - a[0]) * dx + (point.y - a[1]) * dy) / lengthSquared));
      const nearest = { x: a[0] + dx * ratio, y: a[1] + dy * ratio };
      const distance = (point.x - nearest.x) ** 2 + (point.y - nearest.y) ** 2;
      if (distance < bestDistance) {
        bestDistance = distance;
        bestSide = dx * (point.y - nearest.y) - dy * (point.x - nearest.x);
      }
    }
    return bestSide;
  };
  const eventWorldPoint = event => {
    const original = event.originalEvent || event;
    const rect = $svg[0].getBoundingClientRect();
    const screenX = (original.clientX - rect.left) * 1200 / rect.width;
    const screenY = (original.clientY - rect.top) * 720 / rect.height;
    const baseX = (screenX - panX - 600) / zoom + 600;
    const baseY = (screenY - panY - 360) / zoom + 360;
    return { x: (baseX - originX) / baseScale, y: (originY - baseY) / baseScale };
  };
  const stationGroups = preview.station_groups || [preview.station];
  const allTerminals = stationGroups.flatMap(station => station.terminals || []);
  const terminalByNode = new Map(allTerminals.map(terminal => [terminal.node_id, terminal]));
  const faceForPointer = (platform, event) => {
    const faces = platform.terminal_faces || [];
    if (faces.length < 2) return faces[0];
    const pointerSide = sideOfPolyline(platform.platform_centerline, eventWorldPoint(event));
    return faces.reduce((best, face) => {
      const terminal = terminalByNode.get(face.node_id);
      const track = terminal?.operating_track_centerline || terminal?.platform_centerline || [];
      if (track.length < 2) return best;
      const middle = track[Math.floor(track.length / 2)];
      const score = sideOfPolyline(platform.platform_centerline, { x: middle[0], y: middle[1] }) * pointerSide;
      return !best || score > best.score ? { face, score } : best;
    }, null)?.face || faces[0];
  };
  const groupPlatforms = stationGroups.flatMap(station => (station.platforms || []).map(platform => ({
    ...platform,
    station_group_id: station.entity_id,
    station_group_name: station.name,
  })));
  const physicalPlatforms = preview.platforms || (groupPlatforms.length ? groupPlatforms : allTerminals.map((terminal, index) => ({
    platform_index: index,
    platform_kind: 'SIDE_OR_SINGLE_FACE',
    cargo: terminal.cargo,
    terminal_faces: [{
      station_index: terminal.station_index,
      terminal_index: terminal.terminal_index,
      node_id: terminal.node_id,
    }],
    platform_centerline: terminal.platform_centerline || terminal.operating_track_centerline || [],
    platform_length_m: terminal.platform_length_m,
  })));
  physicalPlatforms.forEach(platform => {
    const points = platform.platform_centerline || [];
    if (points.length < 2) return;
    const path = pathForPoints(points);
    const widthUnits = platform.platform_width_units || (platform.platform_kind === 'ISLAND' ? 2 : 1);
    const strokeWidths = platformStrokeWidths(widthUnits);
    const platformColor = platform.cargo ? CARGO_PLATFORM_COLOR : PASSENGER_PLATFORM_COLOR;
    S('path', {
      d: path, fill: 'none', stroke: '#26343d', 'stroke-width': strokeWidths.outline,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      'pointer-events': 'none',
    }, '', $platformLayer);
    S('path', {
      d: path, fill: 'none', stroke: platformColor, 'stroke-width': strokeWidths.deck,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      'pointer-events': 'none',
    }, '', $platformLayer);
    const $divider = platform.platform_kind === 'ISLAND' ? S('path', {
      d: path, fill: 'none', stroke: '#58656d', 'stroke-width': 1,
      'stroke-dasharray': '4 3', 'vector-effect': 'non-scaling-stroke',
      'pointer-events': 'none', display: 'none',
    }, '', $platformLayer) : null;
    const $hit = S('path', {
      d: path, fill: 'none', stroke: 'transparent', 'stroke-width': strokeWidths.hit,
      'stroke-linecap': 'round', 'pointer-events': 'stroke', cursor: 'help',
    }, '', $platformLayer);
    const length = Number.isFinite(platform.platform_length_m) ? `${platform.platform_length_m.toFixed(1)} m` : '长度 UNKNOWN';
    $hit.on('pointerenter.stationPreview pointermove.stationPreview', event => {
      const face = faceForPointer(platform, event);
      if ($divider) $divider.attr('display', 'block');
      $tooltip.text(`${Number(face?.terminal_index ?? platform.platform_index) + 1}站台（${platform.cargo ? '货' : '客'}） · ${length}`).show();
      moveTooltip(event);
    }).on('pointerleave.stationPreview', () => {
      if ($divider) $divider.attr('display', 'none');
      $tooltip.hide();
    });
  });

  preview.nodes.filter(node => node.degree >= 3).forEach(node => {
    const point = P(node.position);
    S('circle', {
      cx: point.x, cy: point.y, r: 2.3, fill: '#ffd35a', stroke: '#584613', 'stroke-width': .7,
      'vector-effect': 'non-scaling-stroke', 'pointer-events': 'none',
    }, '', $switchLayer);
  });
  // 标签字号要按"并进枢纽后缩小了多少"放大 —— 否则枢纽一进来，站名就缩到读不出来。
  const labelBoost = stationScale == null ? 1 : Math.max(1, stationScale / baseScale);
  [preview.station].forEach(station => {
    const point = P(station.center);
    const selected = station.entity_id === stationId;
    S('circle', {
      cx: point.x, cy: point.y, r: selected ? 5 : 3, fill: selected ? '#56dcff' : '#08141e',
      stroke: '#83ecff', 'stroke-width': 1.2, 'vector-effect': 'non-scaling-stroke',
    }, '', $labelLayer);
    S('text', {
      x: point.x + 8 * labelBoost, y: point.y - 7 * labelBoost, fill: selected ? '#d9f9ff' : '#8eaaba',
      'font-size': (selected ? 12 : 9) * labelBoost, 'font-family': 'Consolas, Microsoft YaHei',
      'paint-order': 'stroke', stroke: '#061019', 'stroke-width': 3 * labelBoost,
    }, station.name || `车站 ${station.entity_id}`, $labelLayer);
  });

  const scaleBarPixels = 92;
  const barX = 58;
  const barY = 682;
  S('line', { x1: barX, y1: barY, x2: barX + scaleBarPixels, y2: barY, stroke: '#dce7ef', 'stroke-width': 3 });
  S('line', { x1: barX, y1: barY - 5, x2: barX, y2: barY + 5, stroke: '#dce7ef', 'stroke-width': 2 });
  S('line', { x1: barX + scaleBarPixels, y1: barY - 5, x2: barX + scaleBarPixels, y2: barY + 5, stroke: '#dce7ef', 'stroke-width': 2 });
  const $scaleText = S('text', { x: barX + scaleBarPixels / 2, y: barY - 9, fill: '#dce7ef', 'font-size': 10, 'font-family': 'Consolas', 'text-anchor': 'middle' });
  const platformLegendX = barX + scaleBarPixels + 24;
  [
    { y: barY - 9, color: PASSENGER_PLATFORM_COLOR, label: '客台' },
    { y: barY + 7, color: CARGO_PLATFORM_COLOR, label: '货台' },
  ].forEach(item => {
    S('line', { x1: platformLegendX, y1: item.y, x2: platformLegendX + 20, y2: item.y, stroke: item.color, 'stroke-width': 5, 'stroke-linecap': 'round' });
    S('text', { x: platformLegendX + 27, y: item.y + 3.5, fill: '#dce7ef', 'font-size': 10, 'font-family': 'Microsoft YaHei' }, item.label);
  });
  const formatDistance = value => value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)} km` : `${value.toFixed(value < 10 ? 1 : 0)} m`;

  const updateViewport = () => {
    const viewTransform = `translate(${panX} ${panY}) translate(600 360) scale(${zoom}) translate(-600 -360)`;
    $mapLayer.attr('transform', viewTransform);
    // 枢纽标记层不在 $mapLayer 内（那层带 clip-path），这里手动跟同一套平移缩放
    $hubLayer.attr('transform', viewTransform);
    updateHubMarks();          // 枢纽标记的位置/反缩放/标签避让都要跟着视口重算
    $('#zoom-value').text(`${Math.round(zoom * 100)}%`);
    $('#zoom-out').prop('disabled', zoom <= 1 + 1e-9);
    $scaleText.text(formatDistance(scaleBarPixels / baseScale / zoom));
  };
  const setZoom = (value, focusX = 600, focusY = 360) => {
    const next = Math.min(20, Math.max(1, value));
    if (Math.abs(next - zoom) < 1e-9) return;
    const ratio = next / zoom;
    panX = focusX - 600 - ratio * (focusX - 600 - panX);
    panY = focusY - 360 - ratio * (focusY - 360 - panY);
    zoom = next;
    updateViewport();
  };
  $('#zoom-in').off('.stationPreview').on('click.stationPreview', () => setZoom(zoom * 1.4));
  $('#zoom-out').off('.stationPreview').on('click.stationPreview', () => setZoom(zoom / 1.4));
  $('#zoom-reset').off('.stationPreview').on('click.stationPreview', () => { zoom = 1; panX = 0; panY = 0; updateViewport(); });
  $svg.on('wheel.stationPreview', event => {
    event.preventDefault();
    const original = event.originalEvent;
    const rect = $svg[0].getBoundingClientRect();
    const focusX = (original.clientX - rect.left) * 1200 / rect.width;
    const focusY = (original.clientY - rect.top) * 720 / rect.height;
    setZoom(zoom * (original.deltaY < 0 ? 1.15 : 1 / 1.15), focusX, focusY);
  }).on('dragstart.stationPreview selectstart.stationPreview', event => event.preventDefault())
    .on('pointerdown.stationPreview', event => {
      const original = event.originalEvent;
      if (!original.isPrimary || original.button !== 0) return;
      event.preventDefault();
      dragging = true;
      pointerId = original.pointerId;
      lastX = original.clientX;
      lastY = original.clientY;
      $svg[0].setPointerCapture(pointerId);
      $svg.addClass('dragging');
    }).on('pointermove.stationPreview', event => {
      const original = event.originalEvent;
      if (!dragging || original.pointerId !== pointerId) return;
      event.preventDefault();
      const rect = $svg[0].getBoundingClientRect();
      panX += (original.clientX - lastX) * 1200 / rect.width;
      panY += (original.clientY - lastY) * 720 / rect.height;
      lastX = original.clientX;
      lastY = original.clientY;
      updateViewport();
    }).on('pointerup.stationPreview pointercancel.stationPreview lostpointercapture.stationPreview', () => {
      dragging = false;
      pointerId = null;
      $svg.removeClass('dragging');
    });

  const station = preview.station;
  const sidebar = templates.instantiate('local-station-sidebar-template');
  templates.setText(sidebar, 'station-name', station.name || `车站 ${stationId}`);
  const servingLines = [...new Set((preview.lines || []).map(line => line.name || `线路 ${line.entity_id}`))];
  templates.setText(sidebar, 'serving-lines', servingLines.join(' / ') || '无');
  // 🔴 降级模式（无站场几何）下 `margin_m` / `generated_at` 都是空 —— 直接渲染会印出
  //    "undefined" 和 "Invalid Date"，所以统一给 '—'（2026-10-03）。
  templates.setText(sidebar, 'display-radius', Number.isFinite(preview.margin_m) ? `${Math.round(preview.margin_m)} m` : '—');
  templates.setText(sidebar, 'generated-at', Number.isFinite(preview.generated_at)
    ? new Date(preview.generated_at * 1000).toLocaleString('zh-CN', { hour12: false })
    : '—');
  templates.setText(sidebar, 'save-id', preview.save_id || 'UNKNOWN');
  const rows = templates.slot(sidebar, 'platform-rows');
  physicalPlatforms.forEach(platform => {
    const row = templates.instantiate('local-platform-row-template');
    const faces = platform.terminal_faces || [];
    templates.setText(row, 'platform', `P${Number(platform.platform_index) + 1}`);
    templates.setText(row, 'service-class', `${platform.cargo ? '货运' : '客运'} · ${platform.platform_kind === 'ISLAND' ? '岛式' : '侧式'}`);
    templates.setText(row, 'length', Number.isFinite(platform.platform_length_m) ? `${platform.platform_length_m.toFixed(1)} m` : 'UNKNOWN');
    templates.setText(row, 'terminal-faces', faces.map(face => `T${Number(face.terminal_index) + 1}`).join(' / ') || 'UNKNOWN');
    templates.setText(row, 'node-id', faces.map(face => face.node_id ?? 'UNKNOWN').join(' / '));
    rows.appendChild(row);
  });
  $('#sidebar').empty().append(sidebar);
  $('#station-name').text(station.name || `车站 ${stationId}`);
  $('#snapshot').text(`SAVE ${preview.save_id || 'UNKNOWN'} / STATION ${stationId}`);
  $('.clock').text('STATIC');
  $('.watermark').text('Powered By BlackIce.');
  $('#footer-info').text(`${hasGeometry ? '站场几何为静态缓存' : '无站场几何缓存，仅显示枢纽成员'} · 立交桥 ${bridgeStructureCount} 座 · 不同步列车信息`);

  // ---- 本站客货 / 附近交通枢纽（异步回填，不阻塞上面的静态拓扑先显示）----
  //
  // 枢纽相关的常量与助手（SERVICE_KINDS / MODE_INFO / modeOf / stationServices …）
  // 都已经前移到文件上半部分 —— 那里要用来算取景范围，放在这里会踩暂时性死区。
  //
  // 附近枢纽 = **同一换乘片（cluster）的全部车站**，见上面的说明。
  // 客货：引擎的 STATION 组件**没有** waiting / passengers 字段（探针实测为 nil），
  //   所以车站级的候客数拿不到。这里用的是 /api/demand-live 的**线路级**数据 ——
  //   把"停靠本站的线路"汇总起来，口径在界面上写明，别当成"本站候车人数"。
  const origin = stationIndex.center || preview.station.position || null;
  const servedLineIds = (preview.lines || []).map(line => Number(line.entity_id)).filter(Number.isFinite);

  // ---- 枢纽全景：把同片的车站标到图上 ----------------------------------
  // 只画**位置 + 图标**，不画它们的内部站台几何 —— 那些几何在各自的
  // `station-previews/station-<id>.json` 里（本站那份就 228 KB），一次拉十几份不值当；
  // 而且铁路成员的几何在本站这份里已经包含了。
  // 图标挂 $hubLayer（世界坐标定位，加 1/zoom 反缩放），站名挂 $hubScreenLayer（屏幕坐标）。
  const renderHub = () => {
    if (hubMembers.length < 2 || !hubSelf || !hubSelf.position) return;
    let drawn = 0;
    hubMembers.forEach(member => {
      if (Number(member.entity_id) === Number(stationId)) return;   // 本站由 $labelLayer 负责
      const item = member.position;
      if (!item || !Number.isFinite(item.x) || !Number.isFinite(item.y)) return;
      if (Math.hypot(item.x - hubSelf.position.x, item.y - hubSelf.position.y) > HUB_VIEW_MAX_M) return;
      const mode = modeOf(member);
      const icon = iconOfMember(member, mode);
      const color = mode ? MODE_INFO[mode].color : '#9fb6c6';
      const point = P(item);
      const group = S('g', { 'pointer-events': 'none' }, '', $hubLayer);
      if (icon) {
        const iconUrl = `assets/icons/${icon}.png`;
        // ⚠️ 这些图标是从游戏 ui.zip 里原样取出来的，本来画在**浅色**底板上
        //   （深蓝描边 + 淡蓝填充 + 透明背景）。直接放到深色地图上等于隐形 ——
        //   实测：白底上清清楚楚、地图上完全看不见。
        //   所以按游戏内标记的做法来：**彩色圆角底板 + 把符号刷成白色**
        //   （`filter: brightness(0) invert(1)` 见 network.css 的 .hub-mark-icon）。
        S('rect', {
          x: -HUB_MARK_PX / 2, y: -HUB_MARK_PX / 2, width: HUB_MARK_PX, height: HUB_MARK_PX,
          rx: 4, fill: color, opacity: 0.92,
        }, '', group);
        const inset = 2.5;
        const image = S('image', {
          href: iconUrl, class: 'hub-mark-icon',
          x: -HUB_MARK_PX / 2 + inset, y: -HUB_MARK_PX / 2 + inset,
          width: HUB_MARK_PX - inset * 2, height: HUB_MARK_PX - inset * 2,
        }, '', group);
        // SVG `<image>` 两种写法都写上。⚠️ S() 返回 **jQuery 对象**，
        //   要调 setAttributeNS 必须先取 [0]（否则 "setAttributeNS is not a function"）。
        image[0].setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', iconUrl);
        image.attr('preserveAspectRatio', 'xMidYMid meet');
      } else {
        S('rect', {
          x: -HUB_MARK_PX / 2, y: -HUB_MARK_PX / 2, width: HUB_MARK_PX, height: HUB_MARK_PX,
          rx: 4, fill: 'none', stroke: color, 'stroke-width': 1.6, opacity: 0.9,
        }, '', group);
      }
      const label = S('text', {
        x: 0, y: 0, fill: color, 'font-size': HUB_LABEL_PX,
        'font-family': 'Consolas, Microsoft YaHei', 'paint-order': 'stroke',
        stroke: '#061019', 'stroke-width': 3, 'stroke-linejoin': 'round',
      }, member.name || `车站 ${member.entity_id}`, $hubScreenLayer);
      hubMarkers.push({ group: group[0], label: label[0], x: point.x, y: point.y });
      drawn += 1;
    });
    if (drawn) updateHubMarks();
  };

  // ① 附近设施 = **整个枢纽**（同一换乘片的全部车站）＋ 附近的产业
  //    为什么按 cluster 而不按 3 km 半径：半径在本存档会捞进 117 项（大半是别的枢纽的路边站）。
  //    cluster 取不到时才退回半径。产业入口用 overview —— 一次带全部 215 个点，不必拉几十个分块。
  if (origin) {
    const nearbySlot = templates.slot(sidebar, 'nearby-hub-rows');
    const nearbyNote = text => templates.setText(sidebar, 'nearby-hub-note', text);
    const RADIUS = 3000;
    // 有没有拿到"真实建筑类型"（部署新版 layer_stations.lua 之后才有）
    const typedByBuilding = hubAllStations.some(item =>
      (item.services || []).length || (item.construction_files || []).length);
    const describe = (item, distance) => {
      const services = stationServices(item);
      const labels = services.map(key => SERVICE_TEXT[key]).filter(Boolean);
      const iconKey = services.find(key => SERVICE_ICON[key]);
      const mode = modeOf(item);
      return {
        kind: labels.length
          ? labels.join(' · ')
          : (mode ? MODE_INFO[mode].label : (hubKindByName(item.name) || '车站')),
        icon: (iconKey && SERVICE_ICON[iconKey]) || iconOfMember(item, mode),
        name: item.name,
        distance,
      };
    };
    const nearby = [];
    if (hubMembers.length > 1) {
      hubMembers.forEach(item => {
        if (Number(item.entity_id) === Number(stationId)) return;
        if (!item.position || !Number.isFinite(item.position.x)) return;
        nearby.push(describe(item, Math.hypot(item.position.x - origin.x, item.position.y - origin.y)));
      });
    } else {
      hubAllStations.forEach(item => {
        if (Number(item.entity_id) === Number(stationId)) return;
        if (!item.position || !Number.isFinite(item.position.x)) return;
        const distance = Math.hypot(item.position.x - origin.x, item.position.y - origin.y);
        if (distance <= RADIUS) nearby.push(describe(item, distance));
      });
    }
    const renderNearby = () => {
      // 逐行兜住：一行出问题不该让整张表空掉，也不该只留一句无信息量的"读取失败"。
      try {
        const found = nearby.sort((a, b) => a.distance - b.distance).slice(0, 40);
        found.forEach(item => {
          const row = templates.instantiate('local-hub-row-template');
          // ⚠️ 图标格是 `data-field`（不是 data-slot）。用 slot() 取会拿到 null，
          //    再 appendChild 就是 "Cannot read properties of null" —— 而且它会把整个
          //    列表循环打断，后面的行全都不渲染（2026-09-29 踩过）。
          const iconCell = templates.field(row, 'hub-icon');
          if (item.icon && iconCell) {
            const img = document.createElement('img');
            img.src = `assets/icons/${item.icon}.png`;
            img.alt = item.kind;
            img.className = 'hub-icon';
            img.loading = 'lazy';
            iconCell.appendChild(img);
          }
          templates.setText(row, 'hub-kind', item.kind);
          templates.setText(row, 'hub-name', item.name || `车站 ${item.entity_id}`);
          templates.setText(row, 'hub-distance', distanceText(item.distance));
          nearbySlot.appendChild(row);
        });
        const kinds = new Set(found.map(item => item.kind)).size;
        const scope = hubMembers.length > 1
          ? `站群 #${hubCluster} 整个枢纽共 ${hubMembers.length} 座站`
          : `${RADIUS / 1000} km 内 ${found.length} 项`;
        const method = typedByBuilding
          ? '类型来自车站建筑文件（精确）'
          : `类型由「线路停靠点」反推：站点与某条线路的停靠点重合 ≤ ${HUB_POINT_MATCH_M} m 才认`;
        nearbyNote(`${scope}（${kinds} 类）· ${method}` + ' · 产业为 3 km 内的');
      } catch (error) {
        console.error('[local] 附近设施渲染失败', error);
        nearbySlot.append(templates.message('UNKNOWN', `附近设施渲染失败：${error.message || error}`, true));
      }
    };
    fetch('/layers/industry-overview.json', { cache: 'no-store' })
      .then(response => response.ok ? response.json() : null)
      .then(industry => {
        ((industry && industry.points) || []).forEach(entry => {
          if (!Number.isFinite(entry[0]) || !Number.isFinite(entry[1])) return;
          nearby.push({
            kind: '产业',
            icon: HUB_ICONS['产业'],
            name: entry[4] || (entry[3] != null ? `产业 #${entry[3]}` : '产业'),
            distance: Math.hypot(entry[0] - origin.x, entry[1] - origin.y),
          });
        });
        renderNearby();
      })
      .catch(error => {
        console.warn('[local] 产业层读取失败', error);
        renderNearby();
      });
  }

  // ② 本站客货（线路级口径）
  fetch('/api/demand-live', { cache: 'no-store' })
    .then(response => response.ok ? response.json() : null)
    .then(demand => {
      const lines = (demand && demand.lines) || null;
      if (!lines || !servedLineIds.length) {
        templates.setText(sidebar, 'demand-note', '停靠本站的线路暂无需求数据');
        return;
      }
      const sum = { paxWaiting: 0, paxOnboard: 0, cargoWaiting: 0, cargoOnboard: 0, paxWait: 0, cargoWait: 0, paxSamples: 0, cargoSamples: 0 };
      let matched = 0;
      let newest = 0;
      servedLineIds.forEach(id => {
        const entry = lines[String(id)];
        if (!entry) return;
        matched += 1;
        // 各线的 sampled_at 差异很大（缓存里的可能是几天前的），取最新的那个当"数据时间"
        if (Number.isFinite(Number(entry.sampled_at))) newest = Math.max(newest, Number(entry.sampled_at));
        const pax = entry.pax || {}, cargo = entry.cargo || {};
        sum.paxWaiting += Number(pax.waiting) || 0;
        sum.paxOnboard += Number(pax.onboard) || 0;
        sum.cargoWaiting += Number(cargo.waiting) || 0;
        sum.cargoOnboard += Number(cargo.onboard) || 0;
        const paxWait = Number(pax.median_wait_s), cargoWait = Number(cargo.median_wait_s);
        if (Number.isFinite(paxWait)) { sum.paxWait += paxWait; sum.paxSamples += 1; }
        if (Number.isFinite(cargoWait)) { sum.cargoWait += cargoWait; sum.cargoSamples += 1; }
      });
      const waitText = (total, samples) => samples ? `${(total / samples / 60).toFixed(1)} 分钟（各线中位数均值）` : '—';
      templates.setText(sidebar, 'pax-waiting', `${sum.paxWaiting} 人`);
      templates.setText(sidebar, 'pax-onboard', `${sum.paxOnboard} 人`);
      templates.setText(sidebar, 'cargo-waiting', `${sum.cargoWaiting} 件`);
      templates.setText(sidebar, 'cargo-onboard', `${sum.cargoOnboard} 件`);
      templates.setText(sidebar, 'pax-wait-time', waitText(sum.paxWait, sum.paxSamples));
      templates.setText(sidebar, 'cargo-wait-time', waitText(sum.cargoWait, sum.cargoSamples));
      const stamp = newest ? new Date(newest * 1000).toLocaleString('zh-CN', { hour12: false }) : 'UNKNOWN';
      templates.setText(sidebar, 'demand-note',
        `口径：停靠本站 ${matched} 条线路的合计（引擎车站组件没有候车字段，拿不到单站数） · 采样时间 ${stamp}`);
    })
    .catch(() => templates.setText(sidebar, 'demand-note', '客货数据读取失败'));
  // 枢纽标注是"加值"内容：单独兜住异常，别让它把整个局部图带崩。
  try {
    renderHub();
  } catch (error) {
    console.warn('[local] 枢纽标注失败', error);
  }
  updateViewport();
})().catch(error => {
  console.error(error);
  $('#station-name').text('局部图不可用');
  $('.mode').text('STATION PREVIEW · ERROR');
  $('#sidebar').text(`局部站场图加载失败：${error.message || error}`);
  window.showRailMapNotice?.('局部站场图加载失败');
});
