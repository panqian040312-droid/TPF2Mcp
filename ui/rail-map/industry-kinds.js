// 产业类型表（公共）—— 从产业**名字**反推它属于哪一类。
//
// 为什么单独一个文件：这张表有两处要用 ——
//   `industry-icons.js`：按类型画图标和配方
//   `freight-flow.js`：选中产业时显示它的等级和配方详情
// 各写一份迟早会走样（这边加了关键词、那边没加），所以抽出来共用。
//
// ⚠️ `key` 必须与 `industry-recipes.json` 的键（= 游戏 .con 的文件名）**完全一致** ——
//    配方就是靠它查的。
// ⚠️ 数组顺序 = 匹配优先级，**长词必须排在短词前面**：
//    "食物加工厂"要先被 `food_processing_plant` 的「食物加工」吃掉，
//    否则会被最后那条兜底的「厂」抢走。
// ⚠️ 本文件必须排在 `industry-icons.js` / `freight-flow.js` **之前**加载。

window.TPF2IndustryKinds = (function () {
  "use strict";

  var LIST = [
    { key: 'food_processing_plant', label: '食品加工厂', words: ['食物加工', '食品加工', '食物厂', '食品厂'] },
    { key: 'construction_material', label: '建材厂',     words: ['建材'] },
    { key: 'iron_ore_mine',         label: '铁矿',       words: ['铁矿'] },
    { key: 'coal_mine',             label: '煤矿',       words: ['煤矿'] },
    { key: 'oil_well',              label: '油井',       words: ['油井'] },
    { key: 'oil_refinery',          label: '炼油厂',     words: ['炼油'] },
    { key: 'fuel_refinery',         label: '燃料精炼厂', words: ['燃料'] },
    { key: 'chemical_plant',        label: '化工厂',     words: ['化工'] },
    { key: 'machines_factory',      label: '机械厂',     words: ['机械'] },
    { key: 'steel_mill',            label: '钢铁厂',     words: ['钢铁', '炼钢', '钢'] },
    { key: 'tools_factory',         label: '工具厂',     words: ['工具'] },
    { key: 'quarry',                label: '采石场',     words: ['采石'] },
    { key: 'farm',                  label: '农田',       words: ['农田', '农场'] },
    { key: 'forest',                label: '森林',       words: ['森林', '林场'] },
    { key: 'saw_mill',              label: '锯木厂',     words: ['锯木', '木材'] },
    { key: 'goods_factory',         label: '工厂',       words: ['加工厂', '工厂', '厂'] }
  ];

  var FALLBACK = LIST[LIST.length - 1];   // 认不出的一律归到"工厂"（最后一条最宽）

  var BY_KEY = {};
  LIST.forEach(function (kind) { BY_KEY[kind.key] = kind; });

  function of(name) {
    var text = String(name == null ? '' : name);
    for (var i = 0; i < LIST.length; i += 1) {
      var words = LIST[i].words;
      for (var j = 0; j < words.length; j += 1) {
        if (text.indexOf(words[j]) >= 0) return LIST[i];
      }
    }
    return FALLBACK;
  }

  return {
    LIST: LIST,
    of: of,
    byKey: function (key) { return BY_KEY[key] || null; }
  };
})();
