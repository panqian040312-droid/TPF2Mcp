// 等高线生成：从高度网格里抽出等值线（Marching squares）。
//
// 为什么单独一个文件：这是纯计算，不碰 DOM。独立出来之后浏览器和 Node 都能用同一份
// 代码 —— 几何对不对可以在 Node 里直接验证，不必靠"打开页面看一眼"。
//
// 输入：
//   grid     {origin:{x,y}, step_x, step_y, cols, rows, scale, missing}
//   heights  扁平数组，行优先，长度 cols*rows；值 = round(高度 × scale)
//   interval 等高距（米）
//   window   （可选）只算这一块：{ i0, i1, j0, j1 }，网格下标，范围 [i0, i1) × [j0, j1)。
//            不传就整图。
//            为什么需要它：官方"细节等高线"是 2 m 一级，整图实测 **21.4 万段 / 411 ms**，
//            路径串约 4 MB —— 一次性铺出来会把浏览器卡死（本项目已经栽过一次：
//            4.6 万格的逐格 SVG 四边形 = 2.6 MB 路径串，平移一次就卡）。
//            所以细则级别只在"放大到看得见"时**按视口裁窗**生成。
// 输出：
//   { groups:[{level, segments:[[[x,y],[x,y]], …]}], minH, maxH }
//   坐标是世界坐标，调用方自己转屏幕。minH/maxH 始终是全图范围（与窗口无关），
//   这样按高度配的色阶不会在平移时跟着窗口跳。
//
// 实现要点：
//   * 格子四角相对某条等高线的高低决定了线怎么穿。四条边上线性插值得到穿点。
//   * 整格都在同一侧就直接跳过 —— 这是绝大多数格子，先排掉才跑得动。
//   * 四个穿点的情况（鞍点）要看哪一对对角同侧，否则两根线会连错。
//   * 缺失值（grid.missing）参与的格子整格跳过，不猜。
(function (global, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (global) global.RailTerrainContour = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  function buildContours(grid, heights, interval, window) {
    if (!grid || !heights || !heights.length) return { groups: [], minH: 0, maxH: 0 };
    const cols = grid.cols, rows = grid.rows;
    const stepX = grid.step_x, stepY = grid.step_y;
    const scale = grid.scale || 1, missing = grid.missing;
    const originX = grid.origin.x, originY = grid.origin.y;
    const step = interval > 0 ? interval : 50;

    // 只算视口窗口。留 0 余量不行（平移会露白），调用方负责把窗口放大好再传进来。
    let i0 = 0, i1 = cols, j0 = 0, j1 = rows;
    if (window) {
      const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v | 0));
      i0 = clamp(window.i0, 0, cols); i1 = clamp(window.i1, 0, cols);
      j0 = clamp(window.j0, 0, rows); j1 = clamp(window.j1, 0, rows);
      if (i1 <= i0 || j1 <= j0) return { groups: [], minH: 0, maxH: 0 };
    }

    const at = (i, j) => {
      const value = heights[j * cols + i];
      return (value === missing || value == null) ? NaN : value / scale;
    };

    let minH = Infinity, maxH = -Infinity;
    for (let k = 0; k < heights.length; k++) {
      const value = heights[k];
      if (value === missing || value == null) continue;
      const height = value / scale;
      if (height < minH) minH = height;
      if (height > maxH) maxH = height;
    }
    if (!isFinite(minH) || !isFinite(maxH) || maxH <= minH) return { groups: [], minH: 0, maxH: 0 };

    const levels = [];
    for (let level = Math.ceil(minH / step) * step; level <= maxH; level += step) {
      // 0 是海平面（海岸线）—— 也生成，但由**谁**来画由调用方决定：
      // 等高线层跳过它（那是陆地高程的事），海陆底色层单独把它画成一条亮海岸线。
      levels.push(level);
    }

    const xAt = i => originX + i * stepX;
    const yAt = j => originY + j * stepY;
    const ratio = (v0, v1, level) => (level - v0) / (v1 - v0);

    const groups = [];
    for (let li = 0; li < levels.length; li++) {
      const level = levels[li];
      const segments = [];
      for (let j = j0; j < j1 - 1; j++) {
        for (let i = i0; i < i1 - 1; i++) {
          const a = at(i, j), b = at(i + 1, j), c = at(i + 1, j + 1), d = at(i, j + 1);
          if (Number.isNaN(a) || Number.isNaN(b) || Number.isNaN(c) || Number.isNaN(d)) continue;
          if (level < Math.min(a, b, c, d) || level > Math.max(a, b, c, d)) continue;
          const cross = [];
          if ((a < level) !== (b < level)) { const t = ratio(a, b, level); cross.push([xAt(i) + t * stepX, yAt(j)]); }
          if ((b < level) !== (c < level)) { const t = ratio(b, c, level); cross.push([xAt(i + 1), yAt(j) + t * stepY]); }
          if ((c < level) !== (d < level)) { const t = ratio(c, d, level); cross.push([xAt(i + 1) - t * stepX, yAt(j + 1)]); }
          if ((d < level) !== (a < level)) { const t = ratio(d, a, level); cross.push([xAt(i), yAt(j + 1) - t * stepY]); }
          if (cross.length === 2) {
            segments.push([cross[0], cross[1]]);
          } else if (cross.length === 4) {
            // 鞍点：两个对角分别在一侧。哪一对对角同侧决定了怎么连，
            // 连错会让两根线交叉穿过对方。
            if ((a > level) === (c > level)) {
              segments.push([cross[0], cross[1]]);
              segments.push([cross[2], cross[3]]);
            } else {
              segments.push([cross[3], cross[0]]);
              segments.push([cross[1], cross[2]]);
            }
          }
        }
      }
      if (segments.length) groups.push({ level, segments });
    }
    return { groups, minH, maxH };
  }

  return { buildContours };
});
