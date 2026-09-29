/* 铁路图工具：把"同一位置、不同节点编号"的轨道接缝合并后再寻路。
 *
 * 为什么需要这个：
 *   TPF2 在轨道接缝处会生成**同一坐标的两个节点**（实测环线两端各相距 **5 m**）。
 *   按 node id 建图时，一条**物理上连通**的环会被切成两棵独立的树 ——
 *   表现就是"线路画出来不闭合 / 环线认不出是环 / 图上看着像被盖住了"。
 *   把 ≤ TOL 米的近邻节点合并成同一个点之后，4 条环线的收口段都能找出来
 *   （实测收口段与主路径 **0 重叠**，即真正的"环的另一半"）。
 *
 * 用法：
 *   const closure = RailGraph.findRingClosure(geo, line.route_edge_ids);
 *   closure 为空 → 不是环（或没有另一半）；非空 → 把这些边也画上，环就闭了。
 *
 * 注意：**不要对所有线路都补收口** —— 非环线也可能存在并行第二条路，补了会多画。
 * 当前只在"名字含『环』"的线路上调用（用户约定：环线命名为「xx环线」）。
 */
(function () {
  const TOL = 10;                     // 节点合并阈值（米）
  const cache = new WeakMap();        // geo → { parent, find, adj }

  const build = geo => {
    if (cache.has(geo)) return cache.get(geo);
    const parent = new Map();
    (geo.nodes || []).forEach(node => parent.set(node.entity_id, node.entity_id));
    const find = x => {
      let root = x;
      while (parent.get(root) !== root) root = parent.get(root);
      let cur = x;
      while (parent.get(cur) !== root) { const next = parent.get(cur); parent.set(cur, root); cur = next; }
      return root;
    };
    const union = (a, b) => { const ra = find(a), rb = find(b); if (ra !== rb) parent.set(ra, rb); };

    // 10 m 网格索引：只和相邻格子比，避免 O(n²)
    const grid = new Map();
    (geo.nodes || []).forEach(node => {
      const key = Math.floor(node.position.x / TOL) + '|' + Math.floor(node.position.y / TOL);
      if (!grid.has(key)) grid.set(key, []);
      grid.get(key).push(node);
    });
    for (const [key, list] of grid) {
      const [gx, gy] = key.split('|').map(Number);
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          const other = grid.get((gx + dx) + '|' + (gy + dy));
          if (!other) continue;
          for (const a of list) {
            for (const b of other) {
              if (a.entity_id === b.entity_id) continue;
              if (Math.hypot(a.position.x - b.position.x, a.position.y - b.position.y) <= TOL) {
                union(a.entity_id, b.entity_id);
              }
            }
          }
        }
      }
    }

    // 用"合并后的根"建邻接表
    const adj = new Map();
    const push = (from, to, edgeId) => {
      if (!adj.has(from)) adj.set(from, []);
      adj.get(from).push([to, edgeId]);
    };
    (geo.edges || []).forEach(edge => {
      const a = find(edge.node0), b = find(edge.node1);
      push(a, b, edge.entity_id);
      push(b, a, edge.entity_id);
    });

    const entry = { parent, find, adj };
    cache.set(geo, entry);
    return entry;
  };

  // 把一条 route_edge_ids 展成连续的节点序列（相邻边共享端点，方向自适应）
  const nodeSequence = (edgeIds, edgeById) => {
    const seq = [];
    let prev = null;
    edgeIds.forEach(id => {
      const edge = edgeById.get(id);
      if (!edge) return;
      if (prev === null) { seq.push(edge.node0, edge.node1); prev = edge.node1; return; }
      if (edge.node0 === prev) { seq.push(edge.node1); prev = edge.node1; }
      else if (edge.node1 === prev) { seq.push(edge.node0); prev = edge.node0; }
      else { seq.push(edge.node0, edge.node1); prev = edge.node1; }
    });
    return seq;
  };

  const RailGraph = {
    nodeSequence,

    /* 找"环的另一半"：从主路径**末端**出发，只用**没画过的边**走到**起点**。
     * 找到就返回这些边（按顺序），找不到返回 []。 */
    findRingClosure(geo, routeEdgeIds) {
      if (!geo || !Array.isArray(routeEdgeIds) || routeEdgeIds.length < 2) return [];
      const { find, adj } = build(geo);
      const edgeById = new Map((geo.edges || []).map(edge => [edge.entity_id, edge]));
      const seq = nodeSequence(routeEdgeIds, edgeById);
      if (seq.length < 2) return [];
      const source = find(seq[seq.length - 1]);
      const target = find(seq[0]);
      if (source === target) return [];

      const blocked = new Set(routeEdgeIds);
      const came = new Map([[source, null]]);
      const queue = [source];
      while (queue.length) {
        const cur = queue.shift();
        if (cur === target) break;
        for (const [next, edgeId] of (adj.get(cur) || [])) {
          if (came.has(next) || blocked.has(edgeId)) continue;
          came.set(next, { from: cur, edge: edgeId });
          queue.push(next);
        }
      }
      if (!came.has(target)) return [];
      const out = [];
      let cur = target;
      while (came.get(cur)) { const step = came.get(cur); out.push(step.edge); cur = step.from; }
      return out.reverse();
    },
  };

  window.RailGraph = RailGraph;
})();
