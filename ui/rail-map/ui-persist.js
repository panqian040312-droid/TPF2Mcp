// 界面勾选状态的本地记忆（2026-10-02）
//
// 用户诉求：「做一个机制记住我勾选了啥，除非我手动重置（加一个重置按钮）否则保留我的选择」。
//
// 干什么：把图层面板里每个勾选项的状态存在浏览器 localStorage 里，下次打开还是上次那样。
// 键名规则：`tpf2map.ui.<分组名>/<条目名>` —— 分组名取自面板上显示的那行标题，
// 条目名就是勾选框右边那串字。所以**改了面板文案 = 换了键**（旧值会被忽略、退回默认），
// 这是故意的：文案都改了，还拿旧状态去套才是真的怪。
//
// 重置：`TPF2UIState.reset()` 清掉所有 `tpf2map.ui.*` 然后刷新页面。
// 选"刷新"而不是"就地改回来"，是因为有些项要等数据到齐才能应用，
// 就地恢复会漏几条 —— 刷新一次得到的一定是干净的默认态。
//
// ⚠️ 只记**勾选状态**（还有少数下拉框），不碰任何游戏数据。
(function () {
  var PREFIX = 'tpf2map.ui.';
  // 待恢复的动作先攒着，等整块面板（含各扩展自建的分组）都建完再统一跑。
  // 立刻跑会踩到"别的地方还没初始化"的坑；等一个 tick 就不必关心谁先谁后了。
  var pending = [];
  var flushTimer = null;

  function flush() {
    flushTimer = null;
    var list = pending;
    pending = [];
    list.forEach(function (task) {
      try {
        task();
      } catch (error) {
        console.warn('[地图] 恢复勾选状态失败（该项退回默认）：', error);
      }
    });
  }

  function parse(raw) {
    try {
      return JSON.parse(raw);
    } catch (error) {
      return undefined;
    }
  }

  window.TPF2UIState = {
    prefix: PREFIX,

    // 分组名 + 条目名 → 存储键
    key: function (group, label) {
      return (group ? group + '/' : '') + label;
    },

    // 读：没存过返回 fallback（**不写入**，所以"没动过"和"存了默认值"是分得开的）
    get: function (key, fallback) {
      try {
        var raw = window.localStorage.getItem(PREFIX + key);
        if (raw === null) return fallback;
        var value = parse(raw);
        return value === undefined ? fallback : value;
      } catch (error) {
        return fallback;   // 隐私模式 / 存储被禁 → 静默退化成"不记忆"
      }
    },

    set: function (key, value) {
      try {
        window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
      } catch (error) {
        /* 存不下就算了，不影响用 */
      }
    },

    has: function (key) {
      try {
        return window.localStorage.getItem(PREFIX + key) !== null;
      } catch (error) {
        return false;
      }
    },

    // 攒一个"数据到齐后再应用"的动作
    defer: function (task) {
      pending.push(task);
      if (flushTimer === null) flushTimer = window.setTimeout(flush, 0);
    },

    // 清掉所有记忆并刷新 —— 面板上的「重置勾选」按钮走这条
    reset: function () {
      var removed = 0;
      try {
        var keys = [];
        for (var i = 0; i < window.localStorage.length; i += 1) {
          var name = window.localStorage.key(i);
          if (name && name.indexOf(PREFIX) === 0) keys.push(name);
        }
        keys.forEach(function (name) {
          window.localStorage.removeItem(name);
          removed += 1;
        });
      } catch (error) {
        /* 读不到 localStorage 就没什么可清的 */
      }
      console.log('[地图] 已清除 ' + removed + ' 项勾选记忆，正在刷新…');
      window.location.reload();
    },

    // 诊断用：控制台敲 __uiState.dump() 看现在存了什么
    dump: function () {
      var out = {};
      try {
        for (var i = 0; i < window.localStorage.length; i += 1) {
          var name = window.localStorage.key(i);
          if (name && name.indexOf(PREFIX) === 0) out[name.slice(PREFIX.length)] = parse(window.localStorage.getItem(name));
        }
      } catch (error) {
        return {};
      }
      return out;
    }
  };

  window.__uiState = window.TPF2UIState;
})();
