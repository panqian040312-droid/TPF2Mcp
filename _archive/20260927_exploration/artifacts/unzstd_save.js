// 解压 TPF2 存档（zstd）到 E 盘，供离线分析。
// 用法: node unzstd_save.js
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const SRC = 'C:\\Program Files (x86)\\Steam\\userdata\\1070536217\\1066780\\local\\save\\2.sav';
const OUTDIR = 'E:\\workbody\\TPF2Mcp\\_save';
const DST = path.join(OUTDIR, '2.sav.raw');

fs.mkdirSync(OUTDIR, { recursive: true });

function streamDecompress() {
  return new Promise((resolve, reject) => {
    const rs = fs.createReadStream(SRC);
    const ws = fs.createWriteStream(DST);
    const dec = zlib.createZstdDecompress();
    let out = 0;
    dec.on('data', (c) => { out += c.length; });
    rs.on('error', reject);
    dec.on('error', reject);
    ws.on('error', reject);
    ws.on('finish', () => resolve(out));
    rs.pipe(dec).pipe(ws);
  });
}

function syncDecompress() {
  const buf = fs.readFileSync(SRC);
  const out = zlib.zstdDecompressSync(buf, { maxOutputLength: 4 * 1024 * 1024 * 1024 });
  fs.writeFileSync(DST, out);
  return out.length;
}

(async () => {
  try {
    const n = await streamDecompress();
    console.log('stream OK, bytes =', n);
  } catch (e) {
    console.log('stream FAILED:', e.message, '-> try sync');
    try {
      const n = syncDecompress();
      console.log('sync OK, bytes =', n);
    } catch (e2) {
      console.log('sync FAILED:', e2.message);
      process.exit(1);
    }
  }
  console.log('written to', DST, fs.statSync(DST).size);
})();
