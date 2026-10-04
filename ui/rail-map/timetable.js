(async () => {
  await window.RAIL_MAP_TEMPLATES_READY;
  const templates = window.RailMapTemplates;
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.querySelector('#diagram');
  const list = document.querySelector('#lines');
  const info = document.querySelector('#info');
  const S = (tag, attrs, text, parent = svg) => {
    const element = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, value));
    if (text != null) element.textContent = text;
    parent.appendChild(element);
    return element;
  };
  const fmt = value => {
    const seconds = Math.round(value);
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  };
  const plan = await fetch('/api/timetable-plan', {cache: 'no-store'}).then(response => {
    if (!response.ok) throw new Error(response.status);
    return response.json();
  });

  const summary = templates.instantiate('timetable-summary-template');
  templates.setText(summary, 'planned-lines', plan.counts.planned_lines);
  templates.setText(summary, 'conflicts-removed', plan.global_conflict_plan.conflicts_removed);
  document.querySelector('#summary').replaceChildren(summary);

  // ── 线路地图（简化版）────────────────────────────────────────────────
  // 用户 2026-09-29：不要在站场图/主窗口之间来回切，**就在这里看**；
  // 而且"可以省略高程图" —— 所以这里只画三层：路网（灰）、这条线（红）、站点（圆点+名字）。
  // 几何来自 rail-network-data.json（6.4 MB，**按需加载**，只在第一次切到地图时拉）。
  const mapSvg = document.querySelector('#linemap');
  let geoData = null, geoRequest = null, currentLine = null, currentView = 'diagram';
  const ensureGeo = () => {
    if (geoData) return Promise.resolve(geoData);
    if (!geoRequest) {
      geoRequest = fetch('/rail-network-data.json')
        .then(response => response.ok ? response.json() : null)
        .then(data => { geoData = data; return data; })
        .catch(error => { console.error('[timetable] 线路几何加载失败', error); return null; });
    }
    return geoRequest;
  };

  const drawLineMap = async line => {
    if (!line) return;
    const geo = await ensureGeo();
    mapSvg.replaceChildren();
    if (!geo) {
      S('text', {x: 600, y: 360, fill: '#ff8d95', 'font-size': 14, 'text-anchor': 'middle'}, '线路几何数据不可用（rail-network-data.json 缺失）', mapSvg);
      return;
    }
    // ⚠️ 投影基准 **不能用整张地图的 bounds** —— 地图 16 km 宽，而一条线往往只有 1~2 km，
    //    按整图缩放的话线只有 ~95 px，站点和走向全看不清（实测踩过）。
    //    改成：**旋转后按这条线的包围盒外扩 15% 自适应铺满画布**（朝向仍用 90°，与站场图一致）。
    const hRad = 90 * Math.PI / 180, hCos = Math.cos(hRad), hSin = Math.sin(hRad);
    const rot = (x, y) => ({x: x * hCos - y * hSin, y: x * hSin + y * hCos});

    const nodeById = new Map((geo.nodes || []).map(node => [node.entity_id, node.position]));
    const edgeById = new Map((geo.edges || []).map(edge => [edge.entity_id, edge]));
    // 站点索引：**坐标只能从几何文件拿** —— 运行图 plan 的 stops 只有 station_group_id 和
    // station_name，没有坐标（它本来就是时刻表数据，不是地图数据）。
    const stationById = new Map((geo.stations || []).map(item => [Number(item.entity_id), item]));
    const src = (geo.lines || []).find(item => Number(item.entity_id) === Number(line.line_id));
    const edgeIds = (src && src.route_edge_ids) || [];

    const lineNodes = edgeIds.map(id => edgeById.get(Number(id))).filter(Boolean)
      .flatMap(edge => [edge.node0, edge.node1]).map(id => nodeById.get(id)).filter(Boolean);
    const rotated = (lineNodes.length ? lineNodes : (geo.nodes || []).map(n => n.position)).map(point => rot(point.x, point.y));
    const rxs = rotated.map(v => v.x), rys = rotated.map(v => v.y);
    let minX = Math.min(...rxs), maxX = Math.max(...rxs);
    let minY = Math.min(...rys), maxY = Math.max(...rys);
    const padX = (maxX - minX) * 0.15 + 150, padY = (maxY - minY) * 0.15 + 150;
    minX -= padX; maxX += padX; minY -= padY; maxY += padY;
    const mapScale = Math.min(1080 / Math.max(1, maxX - minX), 620 / Math.max(1, maxY - minY));
    const originX = 600 - (minX + maxX) * mapScale / 2, originY = 360 + (minY + maxY) * mapScale / 2;
    const P = point => { const r = rot(point.x, point.y); return {x: originX + r.x * mapScale, y: originY - r.y * mapScale}; };
    const W = value => { const r = rot(value.x, value.y); return {x: r.x * mapScale, y: -r.y * mapScale}; };
    const edgePathRaw = (edge, nodeByIdRef) => {
      const a = nodeByIdRef.get(edge.node0), c = nodeByIdRef.get(edge.node1);
      if (!a || !c) return '';
      const pa = P(a), pc = P(c), fallback = {x: c.x - a.x, y: c.y - a.y};
      const ta = W(edge.tangent0 || fallback), tc = W(edge.tangent1 || fallback);
      return `M${pa.x.toFixed(1)},${pa.y.toFixed(1)}C${(pa.x + ta.x / 3).toFixed(1)},${(pa.y + ta.y / 3).toFixed(1)} `
        + `${(pc.x - tc.x / 3).toFixed(1)},${(pc.y - tc.y / 3).toFixed(1)} ${pc.x.toFixed(1)},${pc.y.toFixed(1)}`;
    };

    // ① 背景路网：只画**这条线包围盒外扩 800 m** 以内的边 —— 全画 9765 条太浪费，
    //    而只画这一条又看不出"在路网里的位置"。
    let bg = '';
    if (lineNodes.length) {
      // 外扩量按"这条线自身的**尺寸**"给（不是坐标绝对值！），画布已 fit 到它，
      // 这样边角不空、也不会白画几十公里外用不到的边。
      const lxs = lineNodes.map(p => p.x), lys = lineNodes.map(p => p.y);
      const span = Math.max(Math.max(...lxs) - Math.min(...lxs), Math.max(...lys) - Math.min(...lys), 1);
      const pad = Math.max(300, Math.min(4000, span * 0.35));
      const xs = lineNodes.map(p => p.x), ys = lineNodes.map(p => p.y);
      const x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad;
      const y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
      (geo.edges || []).forEach(edge => {
        const a = nodeById.get(edge.node0), c = nodeById.get(edge.node1);
        if (!a || !c) return;
        if (a.x < x0 || a.x > x1 || a.y < y0 || a.y > y1) return;
        if (c.x < x0 || c.x > x1 || c.y < y0 || c.y > y1) return;
        bg += edgePathRaw(edge, nodeById);
      });
    }
    if (bg) S('path', {d: bg, fill: 'none', stroke: '#2b4053', 'stroke-width': 3.2, 'stroke-linecap': 'round'}, null, mapSvg);

    // ② 这条线：红色覆盖（和站场图同一个红）+ 断连缺口补偿
    let d = '', gaps = 0;
    edgeIds.forEach(id => { const edge = edgeById.get(Number(id)); if (edge) d += edgePathRaw(edge, nodeById); });
    ((geo.routing && geo.routing.disconnected_segments) || []).forEach(seg => {
      if (Number(seg.line_id) !== Number(line.line_id)) return;
      const a = nodeById.get(Number(seg.from)), c = nodeById.get(Number(seg.to));
      if (!a || !c) return;
      if (Math.hypot(a.x - c.x, a.y - c.y) > 3000) return;
      const pa = P(a), pc = P(c);
      d += `M${pa.x.toFixed(1)},${pa.y.toFixed(1)}L${pc.x.toFixed(1)},${pc.y.toFixed(1)}`;
      gaps++;
    });
    // 环线收口（同站场图）：合并 ≤10 m 的接缝节点后，把"没画过的另一半"补上，环才闭得起来
    let ringSegments = 0;
    if (/环/.test(line.line_name || '') && window.RailGraph) {
      window.RailGraph.findRingClosure(geo, edgeIds).forEach(id => {
        const edge = edgeById.get(Number(id));
        if (edge) { d += edgePathRaw(edge, nodeById); ringSegments++; }
      });
    }
    if (d) {
      S('path', {d, fill: 'none', stroke: '#ff3b30', 'stroke-width': 8, opacity: .32, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}, null, mapSvg);
      S('path', {d, fill: 'none', stroke: '#ffd9d5', 'stroke-width': 2, opacity: .95, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}, null, mapSvg);
    } else {
      S('text', {x: 600, y: 340, fill: '#ffbd52', 'font-size': 13, 'text-anchor': 'middle'}, `「${line.line_name}」没有路径数据（route_edge_ids 为空）`, mapSvg);
    }

    // ③ 站点：圆点 + 名字（这一层的"站点信息同步"就体现在这里）
    (line.stops || []).forEach((stop, index) => {
      const station = stationById.get(Number(stop.station_group_id));
      if (!station) return;
      const q = P(station.center);
      // 与站场图一致：游戏里那种"编号方块 + 站名"（方块里是停靠顺序）
      S('rect', {x: q.x - 9, y: q.y - 9, width: 18, height: 18, rx: 3, fill: '#ff3b30', stroke: '#3d0b07', 'stroke-width': 1.3}, null, mapSvg);
      S('text', {x: q.x, y: q.y + 4.5, 'text-anchor': 'middle', fill: '#fff', 'font-size': 11, 'font-weight': 'bold', 'font-family': 'Consolas'}, String(index + 1), null, mapSvg);
      S('text', {x: q.x + 13, y: q.y + 4.5, fill: '#ffe6e2', 'font-size': 11, 'font-family': 'Consolas, Microsoft YaHei', 'paint-order': 'stroke', stroke: '#100405', 'stroke-width': 3, 'stroke-linejoin': 'round'}, `${index + 1}. ${stop.station_name || station.name || `站 ${stop.station_group_id}`}`, mapSvg);
    });
    S('text', {x: 16, y: 24, fill: '#8fdcf5', 'font-size': 12, 'font-family': 'Consolas'},
      `${line.line_name} · ${edgeIds.length} 段`
      + (gaps ? ` + 补缺口 ${gaps} 段` : '')
      + (ringSegments ? ` + 环线收口 ${ringSegments} 段` : ''), mapSvg);
  };

  const setChartView = view => {
    currentView = view;
    document.querySelector('#diagram').style.display = view === 'diagram' ? '' : 'none';
    mapSvg.style.display = view === 'map' ? '' : 'none';
    document.querySelector('#view-diagram').classList.toggle('active', view === 'diagram');
    document.querySelector('#view-map').classList.toggle('active', view === 'map');
    if (view === 'map' && currentLine) drawLineMap(currentLine);
  };
  document.querySelector('#view-diagram').addEventListener('click', () => setChartView('diagram'));
  document.querySelector('#view-map').addEventListener('click', () => setChartView('map'));

  const render = line => {
    currentLine = line;                    // 地图视图要用（切过去时才知道画哪条）
    svg.replaceChildren();
    document.querySelectorAll('.line').forEach(element => {
      element.classList.toggle('active', Number(element.dataset.id) === line.line_id);
    });
    const left = 150;
    const right = 1160;
    const top = 70;
    const bottom = 660;
    const cycle = line.cycle_seconds;
    const stops = line.stops;
    const stopIntervals = Math.max(1, stops.length - 1);
    const x = time => left + (time / cycle) * (right - left);
    const y = index => top + index * (bottom - top) / stopIntervals;

    S('rect', {x: left, y: top, width: right - left, height: bottom - top, fill: '#071019', stroke: '#365269'});
    for (let time = 0; time <= cycle; time += Math.max(30, Math.ceil(cycle / 12 / 30) * 30)) {
      S('line', {x1: x(time), y1: top, x2: x(time), y2: bottom, stroke: '#17293a'});
      S('text', {x: x(time), y: top - 12, fill: '#7890a4', 'font-size': 10, 'text-anchor': 'middle', 'font-family': 'Consolas'}, fmt(time));
    }
    stops.forEach((stop, index) => {
      const fit = stop.platform_fit?.status;
      S('line', {x1: left, y1: y(index), x2: right, y2: y(index), stroke: fit === 'TOO_SHORT' ? '#8f3f45' : '#294154'});
      S('text', {x: left - 10, y: y(index) + 4, fill: fit === 'TOO_SHORT' ? '#ff8d95' : '#c8f3ff', 'font-size': 11, 'text-anchor': 'end'}, `${stop.station_name || `站 ${stop.station_group_id}`}${fit === 'TOO_SHORT' ? ' ⚠' : ''}`);
    });
    const colors = ['#42dcff', '#ffe06c', '#6dffa7', '#ff7f9d', '#b89bff', '#ffad66'];
    line.phase_offsets_seconds.forEach((phase, phaseIndex) => {
      for (const base of [phase - cycle, phase, phase + cycle]) {
        let path = '';
        stops.forEach((stop, index) => {
          const arrival = base + stop.arrival_offset_seconds;
          const departure = base + stop.departure_offset_seconds;
          path += `${index ? 'L' : 'M'}${x(arrival)},${y(index)} L${x(departure)},${y(index)} `;
          if (index < stops.length - 1) path += `L${x(departure + stop.next_leg_running_seconds)},${y(index + 1)} `;
        });
        S('path', {d: path, fill: 'none', stroke: colors[phaseIndex % colors.length], 'stroke-width': 2.2, 'clip-path': 'url(#plotclip)', opacity: .9});
      }
    });
    const defs = S('defs', {});
    const clip = S('clipPath', {id: 'plotclip'}, null, defs);
    S('rect', {x: left, y: top, width: right - left, height: bottom - top}, null, clip);
    svg.insertBefore(defs, svg.firstChild);

    const basis = line.speed_basis || {};
    const platform = line.platform_feasibility || {};
    const detail = templates.instantiate('timetable-line-detail-template');
    templates.setText(detail, 'line-name', line.line_name);
    templates.setText(detail, 'service-class', line.service_class);
    templates.setText(detail, 'schedule-speed', line.speed_class_kmh ?? 'UNKNOWN');
    templates.setText(detail, 'consist-speed', basis.consist_top_speed_kmh ?? '待采');
    templates.setText(detail, 'infrastructure-speed', basis.infrastructure_min_speed_limit_kmh ?? '待采');
    templates.setText(detail, 'longest-train', platform.longest_assigned_train_m ?? '待采');
    const platformStatus = templates.setText(detail, 'platform-status', platform.status ?? 'UNKNOWN');
    platformStatus.classList.add(platform.status === 'VERIFIED_FIT' ? 'ok' : 'warn');
    templates.setText(detail, 'vehicle-count', line.vehicle_count);
    templates.setText(detail, 'headway', fmt(line.headway_seconds));
    templates.setText(detail, 'cycle', fmt(cycle));
    templates.setText(detail, 'phase-shift', line.global_phase_shift_seconds);
    templates.setText(detail, 'conflicts-before', line.station_conflicts_before_shift);
    templates.setText(detail, 'conflicts-after', line.station_conflicts_after_shift);
    info.replaceChildren(detail);

    // 「在地图上看这条线」：跳回站场图并带 ?line=，那边会沿**实际轨道**把这条线的
    // 走行路径高亮覆盖出来（依据是 rail-network-data.json 里按顺序的 route_edge_ids）。
    const mapLink = document.createElement('button');
    mapLink.type = 'button';
    mapLink.className = 'line-map-link';
    mapLink.textContent = '在地图上看这条线（沿轨道高亮）';
    mapLink.addEventListener('click', () => {
      location.href = `/?view=network&line=${line.line_id}`;
    });
    info.appendChild(mapLink);
    if (currentView === 'map') drawLineMap(line);   // 已经在地图视图里就直接跟着换线
  };

  plan.lines.forEach((line, index) => {
    const row = templates.instantiate('timetable-line-row-template');
    row.dataset.id = line.line_id;
    templates.setText(row, 'line-name', line.line_name);
    templates.setText(row, 'summary', `${line.service_class} · ${line.speed_class_kmh ?? '—'} km/h · ${line.vehicle_count}车 · ${fmt(line.headway_seconds)}`);
    row.addEventListener('click', () => render(line));
    list.appendChild(row);
    if (index === 0) render(line);
  });
})().catch(error => {
  console.error(error);
  const info = document.querySelector('#info');
  const templates = window.RailMapTemplates;
  try {
    const message = templates.instantiate('timetable-error-template');
    templates.setText(message, 'message', error.message || error);
    info.replaceChildren(message);
  } catch {
    info.textContent = `运行图载入失败：${error.message || error}`;
    info.classList.add('warn');
  }
});
