#!/usr/bin/env python3
"""JS 词法扫描器审计：以 acorn 的解析结果为标准答案，核对安装器给文字规则定位字符串字面量的全过程。

用法:
  python3 zh-i18n/work/js-audit.py [版本]              对解包出的官方包里的全部 JS 做审计（与安装器一致：先套精确规则，再核对文字规则）
  python3 zh-i18n/work/js-audit.py cases <用例.json>    对一组 JS 用例做同样的审计（对抗测试用）
  选项: --installer <路径>   被审计的安装器，缺省为 zh-i18n/install-linux.py
        --keep              保留临时目录
  用例.json 是 [{"name": "用例名", "src": "JS 源码"}, …]；用例模式下每个字符串字面量都临时当作一条规则，译文由本脚本给。
  需要 node 与 acorn：环境变量 ACORN 为 acorn 包目录（如 …/node_modules/acorn），缺省按模块名 acorn 解析。

检查项，任一项不符即退出码 1：
  1. 词法比对：扫描器给出的字符串、模板（含每一段的解码值）、正则字面量的区间与解码值与 acorn 逐项一致，
     且不在合法 JS 上报错（acorn 解析不了的用例/文件本身也算问题，会被列出）；
     有三类文件不在审计范围内，跳过并计数说明：只在脚本模式下才合法的文件（安装器只处理 ES 模块）、含旧式 HTML 注释的文件
     （模块代码里的语法错误），以及 acorn 与 V8 切分不同的写法（异步函数表达式的体之后紧跟斜杠：acorn 读成正则，V8 读除号，
     安装器按 V8 处理）；
  2. 替换比对：期望输出由 acorn 的区间独立拼出，与 patch_js_text 的输出逐字节一致；
  3. 预筛：凡是 acorn 找得到规则字符串的文件，预筛必须放行——这是预筛成立的前提，每次同步新版本都要核对；
  4. 替换后的输出必须仍能被 acorn 解析。
依赖安装器的内部名字：build_js_rules、patch_js_text、_JsLex、_js_cooked、_js_may_hit、GUARD_RE、asar_open、asar_walk。"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time

_DIV_RE = re.compile(r"(?:(?:await|yield|of|async)(?![\w$]))(?:\s|/\*.*?\*/)*function\s*(?:/\*.*?\*/\s*)*[\w$\\\s]*\([^()]*\)\s*(?:/\*.*?\*/\s*)*\{[^{}]*\}\s*(?://[^\n]*\n|/\*.*?\*/|\s)*$", re.S)
HTML_COMMENT_RE = re.compile(r'<!--|(?:^|[\r\n\u2028\u2029])[ \t]*-->')      # 旧式 HTML 注释：模块代码里是语法错误

def is_divergence(text, off):
    """off 处的斜杠前面是不是“异步函数表达式的体”：acorn 在这里把斜杠读成正则，V8 读除号。"""
    return _DIV_RE.search(text[max(0, off - 400):off]) is not None

def diverged_error(text, rec, pos):
    """词法器在 pos 处抛了异常，而 pos 之前 acorn 就把分歧写法的斜杠读成了正则：从那里开始两边读的已经不是同一段代码。"""
    return any(off <= pos and is_divergence(text, off) for off, _ in rec['re'])
WORK = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(WORK); LANG = os.path.join(ROOT, 'language/zh-CN')
RULE_BAD = re.compile(r'["\\=;{}\r\n`]')            # 与 build_js_rules 对文字规则键的约束一致
KINDS = ('字符串', '正则', '模板', '模板段')

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f: f.write(text)

def read(path):
    with open(path, encoding='utf-8', newline='') as f: return f.read()       # 原样保留 CR，与安装器拿到的解码结果一致

def load_installer(path):
    os.environ['ZH_RESOURCES'] = os.path.join(WORK, 'audit-不存在的目录')      # 审计只读：确保安装器拿不到任何可写路径
    os.environ['ZH_BACKUP'] = os.path.join(WORK, 'audit-不存在的备份')
    os.environ['ZH_LANG'] = LANG
    sys.argv = ['install-linux.py']
    spec = importlib.util.spec_from_file_location('inst', path); mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod

def dump(tmp, root, tag):
    """用 js-ast-dump.js 解析 root 下的文件（清单取 tmp/index.json），返回 (记录列表, 解析失败列表)。"""
    out = os.path.join(tmp, tag + '.jsonl'); fails = os.path.join(tmp, tag + '.fails.json')
    r = subprocess.run(['node', os.path.join(WORK, 'js-ast-dump.js'), root, os.path.join(tmp, 'index.json'), 'all', out, fails],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if r.returncode not in (0, 3): raise SystemExit('js-ast-dump.js 运行失败（需要 node 与 acorn；环境变量 ACORN 可指定 acorn 包目录）：\n' + r.stderr[-2000:])
    return [json.loads(line) for line in read(out).split('\n') if line], json.loads(read(fails))     # 只按 \n 切行：解码值里可能有 U+2028

def mine_tokens(inst, text):
    toks = inst._JsLex(text).tokens()
    return (sorted((t[1], t[2], t[4]) for t in toks if t[0] == 'str'), sorted((t[1], t[2]) for t in toks if t[0] == 're'),
            sorted((t[1], t[2], t[4]) for t in toks if t[0] == 'tpl'),
            sorted((qs, qe, inst._js_cooked(raw)) for t in toks if t[0] == 'tpl' for qs, qe, raw in t[5]))

def acorn_tokens(rec):
    return (sorted(tuple(x) for x in rec['str']), sorted(tuple(x) for x in rec['re']),
            sorted(tuple(x) for x in rec['tpl']), sorted((x[0], x[1], x[2]) for x in rec['te']))

def template_values(rec):
    """不含插值的模板及其解码值：[(起, 止, 解码值), …]。"""
    out = []
    for s, e, n in rec['tpl']:
        if n == 0:
            cooked = [t[2] for t in rec['te'] if s <= t[0] and t[1] <= e]
            if len(cooked) == 1: out.append((s, e, cooked[0]))
    return out

def quote(zh, q):                       # 独立于安装器的写法：译文不含双引号、反斜杠、花括号、换行
    if q == "'": return q + zh.replace("'", "\\'") + q
    if q == '`': return q + zh.replace('`', '\\`') + q
    return q + zh + q

def expected_output(guard, text, literals, plain):
    """以 acorn 的区间为标准答案，独立拼出文字规则应得的输出；返回 (期望输出, 命中的区间列表)。"""
    spans = [(s, e, v) for s, e, v in literals if v in plain and not guard.search(text[max(0, s - 96):s])]
    spans.sort()
    out = []; last = 0
    for s, e, v in spans:
        out.append(text[last:s]); out.append(quote(plain[v], text[s])); last = e
    out.append(text[last:])
    return ''.join(out), spans

def main():
    installer = os.path.join(ROOT, 'install-linux.py'); keep = False; cases_path = None; ver = None
    args = sys.argv[1:]; i = 0
    while i < len(args):
        if args[i] == '--installer': installer = args[i + 1]; i += 2
        elif args[i] == '--keep': keep = True; i += 1
        elif args[i] == 'cases': cases_path = args[i + 1]; i += 2
        else: ver = args[i]; i += 1
    inst = load_installer(installer)
    exact, plain = inst.build_js_rules()
    src = None; tmp = tempfile.mkdtemp(prefix='js-audit-'); bad = 0       # 建在系统临时目录下：被中断时不会在仓库里留下残余
    try:
        src = os.path.join(tmp, 'src'); out_dir = os.path.join(tmp, 'out'); index = []
        if cases_path:
            cases = json.loads(read(cases_path))
            if not isinstance(cases, list): raise SystemExit('用例文件应是一个 JSON 数组')
            for n, c in enumerate(cases):
                if not isinstance(c, dict) or not isinstance(c.get('src'), str): raise SystemExit('用例 %d 不是 {"name": …, "src": …} 形式' % n)
                path = '/%04d.js' % n
                write(os.path.join(src, 'cases' + path), c['src'])
                index.append({'origin': 'cases', 'path': path, 'name': c.get('name', ''), 'utf8_ok': True})
        else:
            sys.path.insert(0, WORK); from common5x import paths_for
            res = paths_for(ver)['deb_res']
            for origin, asar, want in (('ion', 'ion-dist.asar', lambda e: e.endswith('.js') and e.startswith('/assets/')),
                                       ('app', 'app.asar', lambda e: e.endswith('.js'))):
                data, header, data_start = inst.asar_open(os.path.join(res, asar))
                for epath, node in inst.asar_walk(header):
                    if not want(epath) or node.get('unpacked'): continue
                    off = int(node['offset'])
                    try: text = data[data_start + off:data_start + off + int(node['size'])].decode('utf-8')
                    except UnicodeDecodeError:
                        index.append({'origin': origin, 'path': epath, 'utf8_ok': False}); continue
                    write(os.path.join(src, origin + epath), inst.patch_js_text(text, exact, {})[0])   # 与安装器一致：先套精确规则
                    index.append({'origin': origin, 'path': epath, 'utf8_ok': True})
        write(os.path.join(tmp, 'index.json'), json.dumps(index, ensure_ascii=False))
        records, fails = dump(tmp, src, 'ast')
        print('acorn 解析 %d 个文件，失败 %d 个' % (sum(1 for e in index if e['utf8_ok']), len(fails)))
        for f in fails[:10]: print('  ✗ 无法解析：%s %s' % (f['file'], f['error']))
        bad += len(fails)
        if cases_path:                              # 用例模式：每个字面量都当一条规则，译文轮流带弯引号、撇号、美元符号、制表符
            plain = {}
            for rec in records:
                for v in [v for _, _, v in rec['str']] + [v for _, _, v in template_values(rec)]:
                    if v and v not in plain and not RULE_BAD.search(v):
                        plain[v] = ('译%d', '‘%d’', '它\'s %d$', '第%d项')[len(plain) % 4] % len(plain)
            print('用例模式：把 %d 个不同的字符串字面量各当作一条规则' % len(plain))
        ent_by = {e['origin'] + e['path']: e for e in index}
        outputs = []; n_truth = n_may = n_done = n_files_truth = 0; n_skip = {'脚本': 0, 'HTML': 0, '分歧': 0}; t0 = time.time()
        for rec in records:
            ent = ent_by[rec['origin'] + rec['file']]; where = '%s %s' % (rec['file'], ent.get('name', ''))
            text = read(os.path.join(src, ent['origin'] + rec['file']))
            if rec.get('mode') == 'script':
                n_skip['脚本'] += 1; continue            # 只在脚本模式下才合法：安装器只处理 ES 模块
            if HTML_COMMENT_RE.search(text):
                n_skip['HTML'] += 1; continue             # 旧式 HTML 注释在模块代码里是语法错误（V8 不接受）
            n_done += 1
            try:
                mine = mine_tokens(inst, text)
            except ValueError as e:
                pos = int(str(e).split('偏移 ')[1].split(' ')[0]) if '偏移 ' in str(e) else 10 ** 9
                if diverged_error(text, rec, pos):
                    n_skip['分歧'] += 1; n_done -= 1; continue     # acorn 与 V8 的分歧写法：按 V8 处理，不计
                bad += 1; print('✗ 词法扫描报错（合法 JS 不应报错）%s：%s' % (where, str(e)[:220])); continue
            acorn = acorn_tokens(rec)
            if mine[1] != acorn[1] and not [i for i in mine[1] if i not in set(acorn[1])] and all(is_divergence(text, i[0]) for i in acorn[1] if i not in set(mine[1])):
                n_skip['分歧'] += 1; n_done -= 1; continue         # acorn 与 V8 的分歧写法：按 V8 处理，不计
            for kind, x, y in zip(KINDS, mine, acorn):
                if x == y: continue
                bad += 1; xs = set(x); ys = set(y)
                only_mine = [i for i in x if i not in ys][:2]; only_acorn = [i for i in y if i not in xs][:2]
                print('✗ 词法比对不一致 [%s] %s\n    仅扫描器: %s\n    仅 acorn: %s' % (kind, where, [str(j)[:90] for j in only_mine], [str(j)[:90] for j in only_acorn]))
                for j in (only_acorn or only_mine)[:1]: print('    偏移 %d 前的源码: %r' % (j[0], text[max(0, j[0] - 150):j[0] + 90]))
            expected, spans = expected_output(inst.GUARD_RE, text, list(rec['str']) + template_values(rec), plain)
            actual = inst.patch_js_text(text, [], plain)[0]
            n_truth += len(spans); n_files_truth += 1 if spans else 0
            if spans and not inst._js_may_hit(text, plain):
                bad += 1; n_may += 1; print('✗ 预筛漏放行 %s（acorn 找得到 %d 处规则字符串）' % (where, len(spans)))
            if actual != expected:
                bad += 1; k = next((i for i, (x, y) in enumerate(zip(actual, expected)) if x != y), min(len(actual), len(expected)))
                print('✗ 替换结果不一致 %s，首个差异在偏移 %d\n    期望: %r\n    实际: %r' % (where, k, expected[max(0, k - 80):k + 80], actual[max(0, k - 80):k + 80]))
            write(os.path.join(out_dir, ent['origin'] + rec['file']), actual)
            outputs.append({'origin': ent['origin'], 'path': rec['file'], 'utf8_ok': True})
        write(os.path.join(tmp, 'index.json'), json.dumps(outputs, ensure_ascii=False))
        _, fails2 = dump(tmp, out_dir, 'out')
        for f in fails2[:10]: print('  ✗ 替换后的输出无法解析：%s %s' % (f['file'], f['error']))
        bad += len(fails2)
        if any(n_skip.values()):
            print('跳过 %d 个只在脚本模式下才合法的文件、%d 个含旧式 HTML 注释的文件、%d 个属于 acorn 与 V8 分歧写法的文件（不在审计范围内）'
                  % (n_skip['脚本'], n_skip['HTML'], n_skip['分歧']))
        print('审计 %d 个文件：应有替换 %d 处（%d 个文件），预筛漏放行 %d 个文件，替换后无法解析 %d 个文件；扫描与替换耗时 %.1fs'
              % (n_done, n_truth, n_files_truth, n_may, len(fails2), time.time() - t0))
    finally:
        if keep and src: print('临时目录保留在', tmp)
        else: shutil.rmtree(tmp, ignore_errors=True)
    print('✔ JS 词法扫描器审计通过' if not bad else '✗ JS 词法扫描器审计发现 %d 处问题' % bad)
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
