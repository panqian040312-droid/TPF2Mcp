/* CTC 调度页：线路 / 车辆 / 告警 / 设置 —— 全部数据来自本地只读接口，不写游戏。 */
(() => {
    'use strict';

    const aux = document.querySelector('#aux');
    const workspace = document.querySelector('.workspace');
    if (!aux || !workspace) return;

    const NAV = {
        timetable: document.querySelector('#nav-timetable'),
        lines: document.querySelector('#nav-lines'),
        vehicles: document.querySelector('#nav-vehicles'),
        alerts: document.querySelector('#nav-alerts'),
        settings: document.querySelector('#nav-settings'),
    };

    const DEFAULT_SETTINGS = { refreshSeconds: 10, flagRows: true };
    const loadSettings = () => {
        try {
            return Object.assign({}, DEFAULT_SETTINGS, JSON.parse(localStorage.getItem('tpf2-ctc-settings') || '{}'));
        } catch {
            return Object.assign({}, DEFAULT_SETTINGS);
        }
    };
    const saveSettings = value => {
        try { localStorage.setItem('tpf2-ctc-settings', JSON.stringify(value)); } catch { /* ignore */ }
    };
    let settings = loadSettings();

    async function fetchJSON(path) {
        const response = await fetch(path, { cache: 'no-store' });
        if (!response.ok) throw new Error(`${path} -> HTTP ${response.status}`);
        return response.json();
    }

    const num = (value, digits = 0) =>
        value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(digits);
    const km = value => (value == null ? '—' : (Number(value) / 1000).toFixed(1));
    const mmss = value => {
        if (value == null) return '—';
        const seconds = Math.round(Number(value));
        return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    };
    const el = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text != null) node.textContent = text;
        return node;
    };
    const badge = (text, kind) => el('span', `badge ${kind || ''}`.trim(), text);
    const clock = value => (value ? new Date(Number(value) * 1000).toLocaleTimeString('zh-CN', { hour12: false }) : '—');

    function table(columns, rows, rowClass) {
        const node = el('table');
        const thead = el('thead');
        const headRow = el('tr');
        columns.forEach(column => headRow.appendChild(el('th', null, column.label)));
        thead.appendChild(headRow);
        node.appendChild(thead);
        const tbody = el('tbody');
        rows.forEach(row => {
            const tr = el('tr');
            if (rowClass) {
                const extra = rowClass(row);
                if (extra) tr.className = extra;
            }
            columns.forEach(column => {
                const cell = el('td', column.num ? 'num' : null);
                const value = column.render(row);
                if (value instanceof Node) cell.appendChild(value);
                else cell.textContent = value == null ? '—' : String(value);
                tr.appendChild(cell);
            });
            tbody.appendChild(tr);
        });
        node.appendChild(tbody);
        return node;
    }

    function kpis(items) {
        const wrap = el('div', 'kpis');
        items.forEach(item => {
            const box = el('div', 'kpi');
            box.appendChild(el('div', 'k', item.label));
            const value = el('div', item.small ? 'v small' : 'v', item.value);
            box.appendChild(value);
            wrap.appendChild(box);
        });
        return wrap;
    }

    // 游戏内时间相对挂钟的速率：低于 1 表示本机仿真跑不满实时，
    // 此时用挂钟测出的时长必须除以 wall_seconds_per_game_second 才是游戏时间。
    function clockRateText(status) {
        const rate = (status || {}).game_clock;
        if (!rate || !rate.rate) return '';
        const slow = rate.rate < 0.9;
        return `｜游戏时间速率 ${rate.rate.toFixed(2)}×` + (slow ? `（挂钟 ${rate.wall_seconds_per_game_second} 秒 = 游戏 1 秒）` : '');
    }

    function toolbar(title, subtitle) {
        const head = el('h2', null, title);
        const sub = el('p', 'sub', subtitle);
        const bar = el('div', 'aux-toolbar');
        const refresh = el('button', 'ghost', '刷新');
        const stamp = el('span', 'sub');
        const spacer = el('div', 'spacer');
        bar.append(refresh, spacer, stamp);
        const frag = document.createDocumentFragment();
        frag.append(head, sub, bar);
        return { frag, refresh, stamp };
    }

    const diagBadge = diag => {
        const map = {
            POSSIBLE_BUNCHING: ['疑似串车', 'bad'],
            UNEVEN_SPACING: ['间距不匀', 'warn'],
            INSUFFICIENT_TRAINS: ['车不足', 'warn'],
            BALANCED: ['正常', 'ok'],
        };
        const [text, kind] = map[diag] || [diag || '未知', 'info'];
        return badge(text, kind);
    };

    async function apiBundle() {
        const [live, plan, status, demand, cost, trunk, demandLive] = await Promise.all([
            fetchJSON('/api/live'),
            fetchJSON('/api/timetable-plan').catch(() => ({ lines: [] })),
            fetchJSON('/api/status'),
            fetchJSON('/api/line-demand').catch(() => ({ lines: [] })),
            fetchJSON('/line-cost-profile.json').catch(() => ({ lines: {} })),
            fetchJSON('/trunk-traffic.json').catch(() => null),
            fetchJSON('/api/demand-live').catch(() => ({ lines: {}, sweep: {} })),
        ]);
        return { live, plan, status, demand, cost, trunk, demandLive };
    }

    function joinLines(live, plan, demand, cost, demandLive) {
        const planById = new Map((plan.lines || []).map(line => [Number(line.line_id), line]));
        const demandById = new Map((demand.lines || []).map(line => [Number(line.line_id), line]));
        const costById = (cost && cost.lines) || {};
        const realById = (demandLive && demandLive.lines) || {};
        return (live.line_diagnostics || []).map(d => {
            const p = planById.get(Number(d.line_id)) || {};
            const m = demandById.get(Number(d.line_id)) || {};
            const c = costById[String(d.line_id)] || {};
            // 真实客流（引擎实测，来自 /api/demand-live）
            const real = realById[String(d.line_id)] || {};
            const realPax = real.pax || {};
            const realCargo = real.cargo || {};
            const routeLength = d.route_length_m || 0;
            const vehicles = d.vehicle_count || 0;
            const target = d.target_spacing_m || 0;
            const minSpacing = d.minimum_spacing_m || 0;
            const ratio = target > 0 ? minSpacing / target : null;
            return {
                id: d.line_id,
                name: d.name,
                service: p.service_class,
                speed: p.speed_class_kmh,
                vehicles,
                routeLength,
                kmPerVehicle: vehicles ? routeLength / 1000 / vehicles : null,
                target,
                minSpacing,
                ratio,
                cv: d.spacing_cv,
                diagnosis: d.diagnosis,
                platform: (p.platform_feasibility || {}).status,
                allFit: (p.platform_feasibility || {}).all_stops_fit,
                longestTrain: (p.platform_feasibility || {}).longest_assigned_train_m,
                headway: p.headway_seconds,
                throughput: m.throughput,
                stops: m.stop_count,
                // 兼容旧版接口：capacity_per_vehicle_per_year 缺失时用 rate/车数 现算
                perVehicle: m.capacity_per_vehicle_per_year != null
                    ? m.capacity_per_vehicle_per_year
                    : (m.vehicle_count ? m.throughput / m.vehicle_count : null),
                capacity: m.fleet_capacity_total,
                seatsTotal: m.seats_total,
                seatsPerTrain: m.capacity_per_train != null
                    ? m.capacity_per_train
                    : (m.vehicle_count ? m.fleet_capacity_total / m.vehicle_count : null),
                serviceClass: m.service_class,
                rateCheck: m.rate_formula_check,
                // --- 真实客流 ---
                paxOnboard: realPax.onboard,
                paxWaiting: realPax.waiting,
                paxAvgWait: realPax.avg_wait_s,
                paxMedianWait: realPax.median_wait_s,
                paxP90Wait: realPax.p90_wait_s,
                paxWaitOver1h: realPax.waiting_over_1h,
                paxWaitSuspect: realPax.wait_suspect,
                realLoad: real.load_factor,
                realSeats: real.seats,
                cargoOnboard: realCargo.onboard,
                cargoWaiting: realCargo.waiting,
                cargoAvgWait: realCargo.avg_wait_s,
                cargoCapacity: real.cargo_capacity,
                cargoTrend: real.cargo_trend || {},
                demandSampledAt: real.sampled_at,
                vehicleLoad: real.vehicle_load || [],
                journey: real.by_journey || [],
                cargoTypes: real.cargo_types || [],
                freePurchase: c.free_purchase || 0,
                cheapRunning: c.cheap_running || 0,
                explicitCost: c.explicit || 0,
                pricePerCar: c.price_per_car_max,
                runPerCar: c.running_per_car_max,
                runScale: c.run_scale,
            };
        });
    }

    const LINE_COLUMNS = [
        { label: '铁路线', render: r => r.name },
        { label: '类型', render: r => r.serviceClass === 'PASSENGER' ? badge('客运', 'info') : (r.serviceClass === 'FREIGHT' ? badge('货运', '') : badge(r.service || '—', 'info')) },
        { label: '车', num: true, render: r => r.vehicles },
        { label: '车上/候车', num: true, render: r => (r.paxOnboard == null ? '—' : `${num(r.paxOnboard)} / ${num(r.paxWaiting)}`) },
        { label: '实载率', num: true, render: r => {
            if (r.realLoad == null) return '—';
            const pct = r.realLoad * 100;
            const text = `${pct.toFixed(0)}%`;
            if (pct >= 90) return badge(text, 'bad');
            if (pct >= 70) return badge(text, 'warn');
            return badge(text, 'ok');
        } },
        { label: '等待(中位)', num: true, render: r => {
            if (r.paxMedianWait != null) {
                return r.paxWaitOver1h ? badge(`${mmss(r.paxMedianWait)} ·${r.paxWaitOver1h}超1h`, 'warn') : mmss(r.paxMedianWait);
            }
            if (r.paxAvgWait == null) return '—';
            return r.paxWaitSuspect ? badge('异常', 'warn') : mmss(r.paxAvgWait);
        } },
        { label: '货 车/候', num: true, render: r => {
            if (r.cargoOnboard == null || (!r.cargoOnboard && !r.cargoWaiting)) return '—';
            const t = r.cargoTrend || {};
            if (t.suspect_stuck) return `${num(r.cargoOnboard)} / ${num(r.cargoWaiting)} ↗`;
            const rising = t.rising && !t.ever_onboard;
            return `${num(r.cargoOnboard)} / ${num(r.cargoWaiting)}${rising ? ' ↗' : ''}`;
        } },
        { label: '年运力(引擎rate)', num: true, render: r => num(r.throughput) },
        { label: '★每车年运力', num: true, render: r => num(r.perVehicle) },
        { label: '载客/载重·列', num: true, render: r => num(r.seatsPerTrain) },
        { label: '里程km', num: true, render: r => km(r.routeLength) },
        { label: '班次', num: true, render: r => mmss(r.headway) },
        { label: '列车容量/列', num: true, render: r => (r.vehicles ? num(r.capacity / r.vehicles) : '—') },
        { label: '最小/目标间距', num: true, render: r => (r.ratio == null ? '—' : `${(r.ratio * 100).toFixed(0)}%`) },
        { label: '离散度CV', num: true, render: r => num(r.cv, 2) },
        { label: '诊断(参考)', render: r => diagBadge(r.diagnosis) },
        { label: '成本属性', render: r => {
            if (r.freePurchase) return badge('零购置成本', 'ok');
            if (r.cheapRunning) return badge(`运行成本 ${r.runScale ?? ''}×`, 'warn');
            if (r.explicitCost && r.pricePerCar) {
                const wan = (r.pricePerCar / 10000).toFixed(0);
                return badge(`显式定价 ${wan}万/节`, 'warn');
            }
            return badge('按自动定价', '');
        } },
        { label: '站台适配', render: r => {
            if (r.platform === 'TOO_SHORT') return badge('站台偏短', 'bad');
            if (r.allFit === false) return badge('未通过校验', 'warn');
            if (r.platform === 'VERIFIED_FIT') return badge('已校验', 'ok');
            return badge(r.platform || '—', '');
        } },
    ];

    const flagLine = r => {
        if (!settings.flagRows) return '';
        if ((r.realLoad || 0) >= 0.9) return 'flagged';
        if ((r.paxWaiting || 0) >= 2 * Math.max(r.paxOnboard || 0, 1) && (r.paxWaiting || 0) >= 200) return 'flagged';
        if (r.diagnosis === 'POSSIBLE_BUNCHING') return 'flagged';
        return '';
    };

    async function renderLines() {
        const { live, plan, status, demand, cost, demandLive } = await apiBundle();
        const rows = joinLines(live, plan, demand, cost, demandLive)
            .filter(r => r.vehicles > 0)
            .sort((a, b) => {
                const la = a.realLoad, lb = b.realLoad;
                if (la != null && lb != null) return lb - la;
                if (la != null) return -1;
                if (lb != null) return 1;
                return (b.perVehicle || 0) - (a.perVehicle || 0);
            });
        const oneCar = rows.filter(r => r.vehicles === 1).length;
        const freeLines = rows.filter(r => r.freePurchase > 0).length;
        const cheapLines = rows.filter(r => r.cheapRunning > 0).length;
        const sampled = rows.filter(r => r.paxOnboard != null);
        const paxOnboard = sampled.reduce((sum, r) => sum + (r.paxOnboard || 0), 0);
        const paxWaiting = sampled.reduce((sum, r) => sum + (r.paxWaiting || 0), 0);
        const cargoOnboard = sampled.reduce((sum, r) => sum + (r.cargoOnboard || 0), 0);
        const cargoWaiting = sampled.reduce((sum, r) => sum + (r.cargoWaiting || 0), 0);
        const busiest = sampled.slice().sort((a, b) => (b.realLoad || 0) - (a.realLoad || 0))[0];
        const paxLines = rows.filter(r => r.serviceClass === 'PASSENGER').length;
        const sweep = (demandLive && demandLive.sweep) || {};
        const { frag, refresh, stamp } = toolbar(
            '铁路线路总览（有实测客流者按载客率排序）',
            '客流＝引擎实测（simPersonSystem/simCargoSystem），只读；运力＝引擎 rate，仅供对照。'
        );
        const sweepButton = el('button', 'ghost', sweep.running ? `采样中 ${sweep.done || 0}/${sweep.total || 0}` : '采样全线路客流');
        sweepButton.addEventListener('click', async () => {
            sweepButton.disabled = true;
            sweepButton.textContent = '采样中…';
            try { await fetchJSON('/api/demand/sweep'); } catch { /* 忽略，下面的轮询会给结果 */ }
            pollSweep();
        });
        refresh.after(sweepButton);
        async function pollSweep() {
            try {
                const state = await fetchJSON('/api/demand-live');
                const progress = state.sweep || {};
                if (progress.running) {
                    sweepButton.textContent = `采样中 ${progress.done || 0}/${progress.total || 0}`;
                    setTimeout(pollSweep, 2000);
                } else {
                    sweepButton.disabled = false;
                    sweepButton.textContent = '采样全线路客流';
                    run('lines');
                }
            } catch {
                sweepButton.disabled = false;
                sweepButton.textContent = '采样全线路客流';
            }
        }
        if (sweep.running) setTimeout(pollSweep, 2000);
        frag.appendChild(kpis([
            { label: '铁路线（客/货）', value: `${rows.length}（${paxLines}/${rows.length - paxLines}）` },
            { label: '已采样线路', value: `${sampled.length}/${rows.length}` },
            { label: '在车乘客', value: paxOnboard.toLocaleString('zh-CN') },
            { label: '候车乘客', value: paxWaiting.toLocaleString('zh-CN') },
            { label: '在车货物', value: cargoOnboard.toLocaleString('zh-CN') },
            { label: '候运货物', value: cargoWaiting.toLocaleString('zh-CN') },
            { label: '最挤的线', value: busiest ? `${busiest.name} ${((busiest.realLoad || 0) * 100).toFixed(0)}%` : '—' },
            { label: '只有 1 辆车的线', value: oneCar },
            { label: '零购置成本线', value: freeLines },
            { label: '运行成本打折线', value: cheapLines },
            { label: '闭塞占用', value: `${status.live_counts ? status.live_counts.occupied_blocks : '—'} / ${status.live_counts ? status.live_counts.blocks : '—'}` },
        ]));
        const warn = el('p', 'note');
        warn.innerHTML = '✅ <b>客流是引擎实测值</b>：来自 <code>simPersonSystem / simCargoSystem.getSimPersonsForLine</code>，'
            + '由 mod 的 <code>line_demand.lua</code> 分类后经 Bridge 返回（只读）。'
            + '<b>车上</b>＝此刻在车内，<b>候车</b>＝此刻在站排队，<b>实载率</b>＝车上÷在册座位。'
            + '首次打开会自动开一轮全线路采样（约 1.5 分钟），也可点右上角「采样全线路客流」重采。'
            + '⚠ 对照用的 <b>年运力(引擎rate)</b> 是 <code>round(730.5 × 单车容量 ÷ 发车间隔)</code>，'
            + '<u>不含需求信息</u>——它只反映配车与频率，不能替代客流判断（实测已证伪：rate 最高的 IS炼钢 实际几乎无需求）。'
            + '「诊断(参考)」列是 Mod 按"车辆应均匀铺满线路"的服务水平判据，与需求无关。'
            + '<b>成本属性</b>来自车辆 .mdl：<code>price=-1</code> 是游戏自动定价，只有显式 0 才是免费。'
            + '分线收入/成本在引擎里仍为 <code>nil</code>，只能在游戏内财务图里看。'
            + '<b>时间口径</b>：本页与运行图的班次、周期、停站时长全部以<b>游戏内时间</b>为准；'
            + '右上角显示游戏时间速率，低于 1 表示本机仿真跑不满实时（用挂钟测出的秒数要除以它才是游戏时间）。'
            + '<br>⚠ <b>客货判据不同，别混用</b>：客运看「实载率 + 候车 + 等待中位」；'
            + '<b>货运只要「每趟运得完、供给 ≥ 消耗、站点不溢出」就是正常</b> —— '
            + '低实载率、候运量大都不是问题指标（用最小运力让货在站点攒够一趟拉走，是省成本的做法）。'
            + '货运只有出现「候运持续增长 <b>且</b> 车从不取货」才会在告警页报出来（列里记作 <code>↗</code>）。';
        frag.appendChild(warn);
        frag.appendChild(table(LINE_COLUMNS, rows, flagLine));
        stamp.textContent = `实时采样 ${clock(live.sampled_at)}` + clockRateText(status);
        refresh.addEventListener('click', () => run('lines'));
        aux.replaceChildren(frag);
    }

    async function renderVehicles() {
        const { live, status } = await apiBundle();
        const planById = new Map(((await fetchJSON('/api/timetable-plan').catch(() => ({ lines: [] }))).lines || [])
            .map(line => [Number(line.line_id), line]));
        const rows = (live.vehicles || []).map(v => ({
            id: v.entity_id,
            name: v.name,
            line: (planById.get(Number(v.line_id)) || {}).line_name || `线路 ${v.line_id}`,
            stopIndex: v.stop_index,
            distance: v.rail_distance_m,
            edge: v.edge_id,
            block: v.block_id,
            speed: v.speed_kmh,
            state: v.raw_state,
            source: v.position_source,
            stale: v.position_stale,
            doors: v.doors_open,
            depart: v.time_until_departure,
            load: v.time_until_load,
        })).sort((a, b) => String(a.line).localeCompare(String(b.line), 'zh-CN'));
        const counts = live.counts || {};
        const { frag, refresh, stamp } = toolbar('在轨铁路车辆', '数据为采样时刻的轨道位置；位置来源 FALLBACK 表示该车刚换边、暂用上一有效位置（最多 30 秒）。');
        frag.appendChild(kpis([
            { label: '在轨铁路车辆', value: counts.rail_vehicles ?? rows.length },
            { label: '行驶中（>1 km/h）', value: rows.filter(r => Number(r.speed) > 1).length },
            { label: '开门中', value: rows.filter(r => r.doors).length },
            { label: '使用回退位置', value: counts.position_fallback_vehicles ?? 0 },
            { label: '位置已过期', value: rows.filter(r => r.stale).length },
            { label: '占用闭塞区间', value: `${counts.occupied_blocks ?? '—'} / ${counts.blocks ?? '—'}` },
            { label: '仿真', value: (live.simulation || {}).status || '—', small: true },
            { label: '速度倍率', value: `${(live.simulation || {}).speed_multiplier ?? '—'}×`, small: true },
        ]));
        frag.appendChild(table([
            { label: '车号', render: r => r.name },
            { label: '所属线路', render: r => r.line },
            { label: '速度km/h', num: true, render: r => num(r.speed, 1) },
            { label: '停站序', num: true, render: r => r.stopIndex },
            { label: '里程位置 m', num: true, render: r => num(r.distance) },
            { label: '闭塞区间', num: true, render: r => r.block },
            { label: '轨道边', num: true, render: r => r.edge },
            { label: '发车倒计时', num: true, render: r => (r.depart == null ? '—' : mmss(r.depart)) },
            { label: '车门', render: r => (r.doors ? badge('开', 'warn') : badge('关', '')) },
            { label: '位置来源', render: r => (r.source === 'FALLBACK' ? badge('回退', 'warn') : badge(r.source || '—', 'ok')) },
            { label: '新鲜度', render: r => (r.stale ? badge('过期', 'bad') : badge('正常', 'ok')) },
        ], rows));
        stamp.textContent = `实时采样 ${clock(live.sampled_at)}`;
        refresh.addEventListener('click', () => run('vehicles'));
        aux.replaceChildren(frag);
    }

    async function renderAlerts() {
        const { live, plan, status, demand, cost, trunk, demandLive } = await apiBundle();
        const all = joinLines(live, plan, demand, cost, demandLive).filter(r => r.vehicles > 0 && r.perVehicle != null);
        const values = all.map(r => r.perVehicle).sort((a, b) => b - a);
        const q1 = values[Math.floor(values.length * 0.75)];
        const alerts = [];
        // 等待时间优先用中位数；只有均值且被判定异常（>1 小时）时视为不可用
        const waitOf = r => (r.paxMedianWait != null ? r.paxMedianWait : (r.paxWaitSuspect ? null : r.paxAvgWait));

        // ---- 测量环境告警：仿真跑不满实时会让"挂钟测出的时长"整体变长 ----
        const clockRate = (status || {}).game_clock;
        if (clockRate && clockRate.rate && clockRate.rate < 0.8) {
            alerts.push({
                level: 'mid', what: '仿真速度偏低（影响实测口径）',
                why: `游戏内时间只以 ${clockRate.rate.toFixed(2)}× 推进（挂钟 ${clockRate.wall_seconds_per_game_second} 秒才走 1 游戏秒），`
                    + '说明本机 CPU 跑不满实时仿真。受影响的只有"用挂钟计时"的量（墙上秒数要除以'
                    + ` ${clockRate.wall_seconds_per_game_second} 才是游戏时间）；相位图、班次、停站时长、`
                    + '候车等待这些游戏内计时不受影响。画面上的时长若与本页对不上，先看这个比率。',
            });
        }

        // ---- 真实客流告警（引擎实测，优先级最高）----
        const sampled = all.filter(r => r.paxOnboard != null);
        sampled.filter(r => (r.realLoad || 0) >= 0.9 && (r.paxOnboard || 0) > 0).forEach(r => {
            alerts.push({
                level: 'high', what: `${r.name} · 运力饱和`,
                why: `实载率 ${((r.realLoad || 0) * 100).toFixed(0)}%（车上 ${num(r.paxOnboard)} / 座位 ${num(r.realSeats)}），`
                    + `另有 ${num(r.paxWaiting)} 人在站候车。这是**实测**的运力不足 —— 加车或缩短周转能直接消化队列。`,
            });
        });
        sampled.filter(r => (r.paxWaiting || 0) >= 2 * Math.max(r.paxOnboard || 0, 1) && (r.paxWaiting || 0) >= 200).forEach(r => {
            alerts.push({
                level: 'high', what: `${r.name} · 候车远多于在车`,
                why: `候车 ${num(r.paxWaiting)} 人 vs 车上 ${num(r.paxOnboard)} 人（${((r.paxWaiting || 0) / Math.max(r.paxOnboard || 1, 1)).toFixed(1)} 倍），`
                    + `等待中位 ${mmss(waitOf(r))}。实载率仅 ${r.realLoad == null ? '—' : ((r.realLoad * 100).toFixed(0) + '%')}，`
                    + '说明车没坐满但**班次不够** —— 优先压缩发车间隔（例如拆分编组把同一批车跑成两列）。',
            });
        });
        sampled.filter(r => (waitOf(r) || 0) > 600 && (r.paxWaiting || 0) > 50).forEach(r => {
            alerts.push({
                level: 'mid', what: `${r.name} · 等待偏长`,
                why: `等待中位 ${mmss(waitOf(r))}，候车 ${num(r.paxWaiting)} 人。建议核对班次 ${mmss(r.headway)} 与停站等待上限。`,
            });
        });
        // ---- 货运线判据（与客运不同）----
        // 游戏逻辑：货运只要「每趟都运得完、供给 ≥ 消耗、站点不溢出」就是健康的。
        // 所以实载率、候运的绝对量都不是问题指标 —— 只有"队列持续增长且车从不取货"才可疑。
        const freight = all.filter(r => r.serviceClass === 'FREIGHT'
            || (r.serviceClass == null && !r.realSeats && ((r.cargoWaiting || 0) > 0 || (r.cargoOnboard || 0) > 0)));
        freight.filter(r => (r.cargoTrend || {}).suspect_stuck).forEach(r => {
            const t = r.cargoTrend;
            alerts.push({
                level: 'mid', what: `${r.name} · 货可能运不走`,
                why: `候运在观测窗口内从 ${num(t.waiting_first)} 涨到 ${num(t.waiting_last)}（${t.observations} 次观测，`
                    + `游戏时间跨度 ${t.game_span_s == null ? '—' : Math.round(t.game_span_s) + ' 秒'}），`
                    + '且**从未观测到车上有货** —— 队列只涨不进车，值得排查（车是否到收货站、货种是否匹配、是否卡在某处）。',
            });
        });
        const freightOk = freight.filter(r => !(r.cargoTrend || {}).suspect_stuck);
        if (freightOk.length) {
            const detail = freightOk.slice(0, 8).map(r => {
                const t = r.cargoTrend || {};
                const tail = t.ever_onboard
                    ? `车上见到过 ${t.max_onboard} 件 → 在取货`
                    : (t.observations >= 2
                        ? `候运 ${t.waiting_min}–${t.waiting_max} 间波动（未持续增长）`
                        : '观测点不足');
                return `${r.name}（候运 ${num(r.cargoWaiting)}：${tail}）`;
            });
            alerts.push({
                level: 'info', what: '货运线按需运行（正常）',
                why: `${detail.join('、')}。\n`
                    + '货运的判据不是实载率、也不是候运的绝对量 —— 只要「每趟能运完、供给 ≥ 消耗、站点不溢出」就是正常的：'
                    + '用最小运力配上少量车，让货物在站点攒够一趟拉走，是刻意为之的省成本做法。'
                    + '本页只在「队列持续增长 + 从不取货」时才报货运问题。',
            });
        }

        // 运力配置偏低：只是"配车/频率低"的事实陈述，不构成需求判断
        const thin = all.filter(r => r.perVehicle <= q1 && r.vehicles >= 2)
            .map(r => `${r.name}(${r.vehicles}辆·每车年运力 ${Math.round(r.perVehicle)})`);
        if (thin.length) {
            alerts.push({
                level: 'info', what: '运力配置偏低的线（非需求判断）',
                why: `每车年运力位于下四分位（≤${Math.round(q1)}）且配车 ≥2 辆：${thin.join('、')}。`
                    + '引擎 rate 只反映「容量×频率」，低不等于没需求 —— 是否减车必须用游戏内实测数据判断。',
            });
        }
        all.filter(r => r.headway > 600 && r.vehicles <= 2).forEach(r => {
            alerts.push({
                level: 'mid', what: r.name,
                why: `班次间隔长（${mmss(r.headway)}）而只配 ${r.vehicles} 辆车 —— 这是**可观测的服务频率事实**，`
                    + '会直接抬高乘客等待时间；但"是否需要加车"取决于实际客流，需从游戏内 UI 读取。',
            });
        });
        (plan.lines || []).forEach(line => {
            const feasibility = line.platform_feasibility || {};
            if (feasibility.status === 'TOO_SHORT') {
                alerts.push({
                    level: 'mid', what: line.line_name,
                    why: `站台长度不足以容纳当前编组：判定 ${feasibility.status}，最长编组 ${num(feasibility.longest_assigned_train_m)} m。`
                        + '扩编组前需要先延长站台。',
                });
            } else if (feasibility.all_stops_fit === false) {
                alerts.push({
                    level: 'mid', what: line.line_name,
                    why: `站台适配未通过校验：最长编组 ${num(feasibility.longest_assigned_train_m)} m，有停站站台长度不满足 —— 加长编组前必须先核实。`,
                });
            }
        });
        all.filter(r => r.diagnosis === 'POSSIBLE_BUNCHING').forEach(r => {
            alerts.push({
                level: 'ref', what: r.name,
                why: `【参考，非需求判据】Mod 判定疑似串车：最小间距 ${num(r.minSpacing)} m 仅为目标 ${num(r.target)} m 的 `
                    + `${r.ratio == null ? '—' : (r.ratio * 100).toFixed(0)}%，CV=${num(r.cv, 2)}。`
                    + '该判据假设"车辆应均匀铺满线路"，与需求无关；是否先调节奏再加车，需结合实测客流判断。',
            });
        });
        (live.vehicles || []).filter(v => v.position_stale).forEach(v => {
            alerts.push({ level: 'ref', what: v.name, why: `位置过期：超过 30 秒未解析出有效轨道边（edge_id=${v.edge_id}），已排除在占用与间距分析之外。` });
        });
        const counts = status.live_counts || {};
        if (counts.blocks && counts.occupied_blocks / counts.blocks > 0.6) {
            alerts.push({ level: 'high', what: '全网闭塞', why: `闭塞区间占用率 ${(counts.occupied_blocks / counts.blocks * 100).toFixed(0)}%，接近饱和。` });
        }
        if (status.rail_counts && status.rail_counts.disconnected_segments) {
            alerts.push({
                level: 'mid', what: '轨道连通性',
                why: `检出 ${status.rail_counts.disconnected_segments} 处与主网不连通的区段（共 ${status.rail_counts.edges} 条轨道边）。`
                    + '若同一运营线路跨越这些区段，会导致无法直达或必须绕行。',
            });
        }
        if (status.live_counts && status.live_counts.rail_vehicles) {
            const liveRail = status.live_counts.rail_vehicles;
            const idleLines = all.filter(r => r.perVehicle <= q1 && r.vehicles >= 2);
            if (idleLines.length) {
                alerts.push({
                    level: 'info', what: '车辆配置',
                    why: `${idleLines.length} 条线的每车年运力位于下四分位，占用 ${idleLines.reduce((s, r) => s + r.vehicles, 0)} 辆车（在轨铁路车共 ${liveRail} 辆）。`
                        + '运力配置低 = 容量小或频率低，**不等于需求低**；要不要调车请看游戏内实测客流（车站候客数 / 车辆财务收入）。',
                });
            }
        }
        const conflict = (plan && plan.global_conflict_plan) || {};
        if (conflict.conflicts_after_shift) {
            alerts.push({
                level: 'mid', what: '干线相位冲突',
                why: `运行图在 1 小时视窗内检出 ${conflict.conflicts_after_shift} 次停站相位冲突`
                    + `（相位优化前 ${conflict.conflicts_before_shift} 次，已消除 ${conflict.conflicts_removed} 次，清空间隔 ${conflict.clearance_seconds}s）。`
                    + '这是**车流量层面**的拥堵信号：加车前应先看这些冲突集中在哪些共用区段。',
            });
        }
        if (trunk && (trunk.trunk_pairs || []).length) {
            const top = trunk.trunk_pairs.slice().sort((a, b) => b.edges - a.edges).slice(0, 3).map(pair => {
                const a = (trunk.line_names || {})[String(pair.a)] || pair.a;
                const b = (trunk.line_names || {})[String(pair.b)] || pair.b;
                return `${a}+${b}（共用 ${pair.edges} 段，合计理论 ${Math.round(pair.traffic)} 列/小时）`;
            }).join('；');
            alerts.push({
                level: 'mid', what: '干线段共用',
                why: `实测存在共用轨道的线路对：${top}。`
                    + '这些区段是加车时的拥堵风险点 —— 车流叠加后区间占用会上升，需要按已并入的车流一起算余量。',
            });
            const cross = Object.keys(trunk.cross_line_blocks || {}).length;
            if (cross) {
                alerts.push({
                    level: 'ref', what: '跨线争用区间',
                    why: `采样期间有 ${cross} 个闭塞区间被两条以上铁路线的车辆占用过。`
                        + '若这些区间为单线（无越行条件），加车会导致排队而不是提高运力。',
                });
            }
        }
        const freeLines = all.filter(r => r.freePurchase > 0);
        const cheapLines = all.filter(r => r.cheapRunning > 0 && !r.freePurchase);
        const pricedLines = all.filter(r => r.explicitCost > 0 && !r.freePurchase && !r.cheapRunning);
        if (freeLines.length || cheapLines.length) {
            alerts.push({
                level: 'info', what: '成本豁免线',
                why: `零购置成本：${freeLines.map(r => r.name).join('、') || '无'}；`
                    + `运行成本打折：${cheapLines.map(r => `${r.name}(${r.runScale}×)`).join('、') || '无'}。`
                    + '这些线路的成本约束弱于普通线，调整配车时应先看游戏内实测客流（车站候客数），而不是先算成本。',
            });
        }
        if (pricedLines.length) {
            const worst = pricedLines.slice().sort((a, b) => (b.pricePerCar || 0) - (a.pricePerCar || 0))[0];
            const runText = worst.runPerCar
                ? `每节运行费 ${Math.round(worst.runPerCar)}（≈$${Math.round(worst.runPerCar * 0.5)}），`
                : '';
            alerts.push({
                level: 'mid', what: '显式定价车型',
                why: `${pricedLines.length} 条线使用显式定价车辆，最高为 ${worst.name}（${(worst.pricePerCar / 10000).toFixed(0)} 万/节），`
                    + runText
                    + '复兴号 CR400AF 即属此类：一列 8 节约 $24.57M（京广客运那列为 16 节重联，约 $49.14M），'
                    + '但每列运行费仅 ≈$24,571 —— 在游戏财务图以「百万」为刻度时会被显示成 0.0 M，'
                    + '所以复兴号实际是"运营成本可忽略、主要约束是购置价"的资产，加车回本快但要一次付清车价。',
            });
        }

        Object.entries(live.limitations || {}).filter(([, text]) => String(text).startsWith('UNKNOWN')).forEach(([key, text]) => {
            alerts.push({ level: 'info', what: `数据盲区 · ${key}`, why: String(text) });
        });
        alerts.push({
            level: 'info', what: '客流数据已接入（引擎实测）',
            why: `本页客流来自引擎 simPersonSystem/simCargoSystem，由 /api/demand-live 提供，已采样 ${sampled.length} 条铁路线。`
                + '车上＝此刻在车，候车＝此刻在站排队，实载率＝车上÷在册座位。'
                + '仍读不到的只有**分线收入/成本**（引擎返回 nil），那部分只能看游戏内财务图。',
        });
        (plan.limitations || []).slice(0, 6).forEach(text => {
            alerts.push({ level: 'info', what: '运行图限制', why: String(text) });
        });

        const order = { high: 0, mid: 1, ref: 2, info: 3 };
        alerts.sort((a, b) => order[a.level] - order[b.level]);
        const { frag, refresh, stamp } = toolbar(
            '告警与风险（实测客流优先）',
            '优先级：高 = 客运实测运力饱和 / 候车远多于在车；中 = 客运等待偏长、货运队列持续增长且不取货、干线拥堵；参考 = Mod 的服务水平启发式判据；信息 = 数据边界与正常运行的货运线。'
        );
        frag.appendChild(kpis([
            { label: '高', value: alerts.filter(a => a.level === 'high').length },
            { label: '中', value: alerts.filter(a => a.level === 'mid').length },
            { label: '参考', value: alerts.filter(a => a.level === 'ref').length },
            { label: '信息', value: alerts.filter(a => a.level === 'info').length },
            { label: '铁路每车年运力', value: (all.length ? Math.round(all.reduce((s, r) => s + (r.throughput || 0), 0) / Math.max(all.reduce((s, r) => s + r.vehicles, 0), 1)) : '—').toLocaleString('zh-CN') },
        ]));
        if (!alerts.length) {
            frag.appendChild(el('p', 'note', '当前没有检出告警。'));
        } else {
            const levelText = { high: ['高', 'bad'], mid: ['中', 'warn'], ref: ['参考', ''], info: ['信息', 'info'] };
            alerts.forEach(alert => {
                const row = el('div', 'alert-row');
                const [text, kind] = levelText[alert.level];
                row.appendChild(badge(text, kind));
                row.appendChild(el('div', 'what', alert.what));
                row.appendChild(el('div', 'why', alert.why));
                frag.appendChild(row);
            });
        }
        if (demand.company) {
            const money = el('p', 'note');
            money.innerHTML = `<b>公司级财务</b>（唯一可得的财务数据）：余额 ${Number(demand.company.balance).toLocaleString('zh-CN')} ｜ `
                + `贷款 ${Number(demand.company.loan).toLocaleString('zh-CN')}`;
            frag.appendChild(money);
        }
        stamp.textContent = `采样 ${clock(live.sampled_at)}`;
        refresh.addEventListener('click', () => run('alerts'));
        aux.replaceChildren(frag);
    }

    async function renderSettings() {
        const { frag } = toolbar('设置', '设置只保存在本机浏览器，不改动游戏与 Mod 配置。');
        const refreshRow = el('div', 'setting-row');
        refreshRow.appendChild(el('label', null, '自动刷新间隔'));
        const select = el('select');
        [['5', '5 秒'], ['10', '10 秒'], ['30', '30 秒'], ['60', '60 秒'], ['0', '关闭']].forEach(([value, text]) => {
            const option = el('option', null, text);
            option.value = value;
            if (String(settings.refreshSeconds) === value) option.selected = true;
            select.appendChild(option);
        });
        select.addEventListener('change', () => {
            settings.refreshSeconds = Number(select.value);
            saveSettings(settings);
            scheduleRefresh();
        });
        refreshRow.appendChild(select);
        frag.appendChild(refreshRow);

        const flagRow = el('div', 'setting-row');
        flagRow.appendChild(el('label', null, '高亮问题行'));
        const flagBox = document.createElement('input');
        flagBox.type = 'checkbox';
        flagBox.checked = !!settings.flagRows;
        flagBox.addEventListener('change', () => {
            settings.flagRows = flagBox.checked;
            saveSettings(settings);
        });
        flagRow.appendChild(flagBox);
        frag.appendChild(flagRow);

        const resetRow = el('div', 'setting-row');
        resetRow.appendChild(el('label', null, '恢复默认'));
        const reset = el('button', 'ghost', '重置设置');
        reset.addEventListener('click', () => {
            settings = Object.assign({}, DEFAULT_SETTINGS);
            saveSettings(settings);
            run('settings');
        });
        resetRow.appendChild(reset);
        frag.appendChild(resetRow);

        const note = el('p', 'note');
        note.innerHTML = '<b>数据来源</b>（全部只读，来自本地服务与游戏 Bridge）：<br>'
            + '<code>/api/demand-live</code> <b>引擎实测客流</b>（车上/候车/平均等待/实载率/OD）· '
            + '<code>/api/line-demand</code> 引擎 rate（=运力）与车队容量 · <code>/api/live</code> 实时车辆与线路诊断 · '
            + '<code>/api/timetable-plan</code> 运行图计划 · <code>/api/status</code> 计数与采样序号 · '
            + '<code>/api/rail/manifest</code> 路网几何 · <code>/api/control</code> 信号与闭塞<br><br>'
            + '<b>客流怎么来的</b>：引擎接口 <code>api.engine.system.simPersonSystem / simCargoSystem.getSimPersonsForLine / '
            + 'getSimCargosForLine</code>，实体归属由组件判定（<code>SIM_ENTITY_AT_VEHICLE</code>＝在车，'
            + '<code>SIM_ENTITY_AT_TERMINAL</code>＝在站候车，<code>lineStop0/1</code>＝OD）。'
            + '地图服务按需逐线采样并缓存，写入 <code>bridge/line-demand-live.json</code>；采完一轮约 36 条线 / 1.5 分钟。<br><br>'
            + '<b>客货判据不同（重要）</b>：客运看「实载率 + 候车 + 等待中位」三者同看，单次快照不作判据；'
            + '<b>货运只看「队列是否持续增长 + 车是否真的在取货」</b> —— '
            + '游戏里货运只要每趟运得完、供给 ≥ 消耗、站点不溢出就是正常，'
            + '用最小运力配少量车让货在站点攒够一趟拉走是正常的省成本做法，'
            + '因此<b>实载率低、候运量大都不构成问题</b>。服务端为每条线保留货运队列的时间序列（存在 '
            + '<code>line-demand-live.json</code> 的 <code>cargo_history</code>），'
            + '只有「候运持续上涨（>1.2 倍且 ≥3 次观测）且从未见到车上有货」才判为可疑。<br><br>'
            + '<b>两个"运力"不要混</b>：引擎的「吞吐量」<code>line.rate</code> 经 271 条线实测 = '
            + '<code>round(730.5 × 单车容量 ÷ 发车间隔)</code>（269 条精确吻合）——它是运力公式，'
            + '<b>不含需求信息</b>，已实测证伪其排序价值（rate 第一的线实际几乎无需求）。'
            + 'Mod 自带的 <code>INSUFFICIENT_TRAINS / POSSIBLE_BUNCHING</code> 是"车辆应均匀铺满线路"的启发式，已降级为「参考」。<br><br>'
            + '<b>仍读不到</b>：分线收入/成本/利润（引擎返回 <code>nil</code>），只能在游戏内财务图逐车查看。<br><br>'
            + '<b>写操作</b>：本页与附件脚本均不向游戏写入任何内容。';
        frag.appendChild(note);
        aux.replaceChildren(frag);
    }

    const RENDERERS = { lines: renderLines, vehicles: renderVehicles, alerts: renderAlerts, settings: renderSettings };
    let current = null;
    let timer = null;
    let renderedView = null;

    function scheduleRefresh() {
        if (timer) clearInterval(timer);
        if (settings.refreshSeconds > 0 && current && current !== 'settings') {
            timer = setInterval(() => run(current, true), settings.refreshSeconds * 1000);
        }
    }

    async function run(view, automatic = false) {
        // 自动刷新不先清空面板：原实现在每次刷新前插入「载入中…」，
        // 于是每 10 秒白屏一次——这就是"每次刷新闪一下"的来源。
        const switching = renderedView !== view;
        current = view;
        workspace.classList.add('aux-mode');
        aux.hidden = false;
        Object.entries(NAV).forEach(([key, button]) => button && button.classList.toggle('active', key === view));
        const keepTop = switching ? 0 : aux.scrollTop;
        const keepWindowY = switching ? 0 : window.scrollY;
        if (switching) aux.replaceChildren(el('p', 'sub', '载入中…'));
        try {
            await RENDERERS[view]();
            renderedView = view;
        } catch (error) {
            if (switching) aux.replaceChildren(el('p', 'err', `载入失败：${error.message || error}`));
        }
        // 保留滚动位置，避免刷新时内容"跳回顶部"看起来像闪屏。
        aux.scrollTop = keepTop;
        if (keepWindowY) window.scrollTo(0, keepWindowY);
        scheduleRefresh();
    }

    function showTimetable() {
        current = null;
        if (timer) clearInterval(timer);
        workspace.classList.remove('aux-mode');
        aux.hidden = true;
        Object.entries(NAV).forEach(([key, button]) => button && button.classList.toggle('active', key === 'timetable'));
    }

    NAV.lines && NAV.lines.addEventListener('click', () => run('lines'));
    NAV.vehicles && NAV.vehicles.addEventListener('click', () => run('vehicles'));
    NAV.alerts && NAV.alerts.addEventListener('click', () => run('alerts'));
    NAV.settings && NAV.settings.addEventListener('click', () => run('settings'));
    NAV.timetable && NAV.timetable.addEventListener('click', showTimetable);
    document.querySelector('#network-view')?.addEventListener('click', showTimetable);
})();
