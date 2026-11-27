#!/usr/bin/env node
'use strict';
// 用 acorn 解析一组 JS，逐文件导出字符串字面量 / 模板 / 正则 / 注释的区间与解码值（JSON lines），
// 供 js-audit.py 与安装器的 JS 词法扫描器逐项比对。区间与下标换算成 Unicode 码点下标（与 Python str 的下标一致）。
// 用法: node js-ast-dump.js <根目录> <index.json> <origin 或 all> <out.jsonl> <fails.json>
//   index.json 每一项: {origin, path, size, utf8_ok}；文件位于 <根目录>/<origin><path>
//   acorn 包: 环境变量 ACORN 为包目录（如 …/node_modules/acorn）或模块名，缺省为 acorn
const fs = require('fs');
const acorn = require(process.env.ACORN || 'acorn');
const [,, root, indexPath, origin, outPath, failPath] = process.argv;
if (!failPath) { console.error('usage: node js-ast-dump.js <root> <index.json> <origin|all> <out.jsonl> <fails.json>'); process.exit(2); }
const index = JSON.parse(fs.readFileSync(indexPath, 'utf8')).filter(e => e.utf8_ok && (origin === 'all' || e.origin === origin));
const out = fs.createWriteStream(outPath, { encoding: 'utf8' });
const fails = [];
let nFiles = 0, nStr = 0, nTpl = 0, nRe = 0;
const t0 = Date.now();
for (const ent of index) {
  const u16 = fs.readFileSync(root + '/' + ent.origin + ent.path, 'utf8');
  const cpLen = [...u16].length;
  let cp = null;
  if (cpLen !== u16.length) { // 含增补平面字符：建立 UTF-16 下标 → 码点下标 的映射
    cp = new Int32Array(u16.length + 1);
    let j = 0;
    for (let i = 0; i < u16.length; j++) { cp[i] = j; const c = u16.codePointAt(i); i += c > 0xffff ? 2 : 1; }
    cp[u16.length] = j;
  }
  const toCp = (i) => (cp ? cp[i] : i);
  let ast = null, mode = null, err = null;
  for (const st of ['module', 'script']) {
    try {
      ast = acorn.parse(u16, { ecmaVersion: 'latest', sourceType: st, allowHashBang: true, allowAwaitOutsideFunction: true, allowReturnOutsideFunction: true });
      mode = st; break;
    } catch (e) { err = st + ': ' + String(e.message) + ' @' + e.pos; }
  }
  if (!ast) { fails.push({ file: ent.path, size: ent.size, error: err }); continue; }
  const str = [], tpl = [], te = [], re = [];
  (function walk(n) {
    if (!n || typeof n !== 'object') return;
    if (Array.isArray(n)) { for (const c of n) walk(c); return; }
    if (typeof n.type !== 'string') return;
    if (n.type === 'Literal') {
      if (typeof n.value === 'string') { str.push([toCp(n.start), toCp(n.end), n.value]); nStr++; }
      else if (n.regex) { re.push([toCp(n.start), toCp(n.end)]); nRe++; }
    } else if (n.type === 'TemplateLiteral') { tpl.push([toCp(n.start), toCp(n.end), n.expressions.length]); nTpl++; }
    else if (n.type === 'TemplateElement') { te.push([toCp(n.start), toCp(n.end), n.value.cooked, n.tail]); }
    for (const k in n) { if (k === 'type' || k === 'start' || k === 'end') continue; walk(n[k]); }
  })(ast);
  out.write(JSON.stringify({ file: ent.path, origin: ent.origin, mode, len: cpLen, str, tpl, te, re }) + '\n');
  nFiles++;
}
out.end(() => {
  fs.writeFileSync(failPath, JSON.stringify(fails, null, 1));
  console.error(JSON.stringify({ origin, files: nFiles, stringLiterals: nStr, templates: nTpl, regexes: nRe, failures: fails.length, ms: Date.now() - t0 }));
  process.exit(fails.length ? 3 : 0);
});
