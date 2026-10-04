// Lua 语法检查（不执行代码，只解析）
// 用法: node lua-syntax-check.js <file.lua> [...]
const fs = require('fs');
const path = require('path');
const luaparse = require('./luaparse.js');

let failed = 0, checked = 0;
for (const file of process.argv.slice(2)) {
  try {
    const code = fs.readFileSync(file, 'utf8');
    luaparse.parse(code, { luaVersion: '5.2', comments: false, scope: false });
    console.log(`OK    ${file}`);
    checked++;
  } catch (e) {
    failed++;
    const line = e.line !== undefined ? e.line : (e.index !== undefined ? e.index : '?');
    console.log(`FAIL  ${file}  line=${line}  ${e.message}`);
  }
}
console.log(`\n解析 ${checked + failed} 个文件，失败 ${failed} 个`);
process.exit(failed ? 1 : 0);
