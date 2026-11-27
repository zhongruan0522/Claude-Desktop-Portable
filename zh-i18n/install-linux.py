#!/usr/bin/env python3
# Claude Desktop 汉化助手（由 install-linux.sh 调用；也可单独运行调试）
# 支持 4.x（前端打包在 ion-dist.asar、桌面壳词典在 app.asar 内）与 3.x（明文目录）两种布局。
# 用法: ZH_RESOURCES=... ZH_BACKUP=... ZH_LANG=... python3 install-linux.py install|reset|check
#      python3 install-linux.py set-locale <config.json 路径>   # 以目标用户身份运行
import json, os, re, sys, hashlib, struct, shutil, subprocess, posixpath

RESOURCES = os.environ.get('ZH_RESOURCES', '')
BACKUP = os.environ.get('ZH_BACKUP', '')
LANG = os.environ.get('ZH_LANG', '')
MODE = sys.argv[1] if len(sys.argv) > 1 else ''

def p(msg): print(msg, flush=True)

def load(path):
    with open(path, encoding='utf-8') as f: return json.load(f)

def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1).encode('utf-8')

# ---------- 布局检测 ----------
def detect_layout():
    if os.path.isfile(os.path.join(RESOURCES, 'ion-dist.asar')): return 'asar4'
    if os.path.isfile(os.path.join(RESOURCES, 'ion-dist/i18n/en-US.json')): return 'dir3'
    raise SystemExit('未识别的资源布局：既没有 ion-dist.asar（4.x）也没有 ion-dist/i18n/en-US.json（3.x）。'
                     '请确认 Claude Desktop 安装完好，或用 --resources 指定正确的资源目录。')

def detect_version(layout):
    try:
        r = subprocess.run(['dpkg-query', '-W', '-f=${Version}', 'claude-desktop'],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return 'deb:' + r.stdout.strip()
    except Exception:
        pass
    if layout == 'asar4':
        blob = asar_entry(os.path.join(RESOURCES, 'ion-dist.asar'), '/i18n/en-US.json')[0]
    else:
        blob = open(os.path.join(RESOURCES, 'ion-dist/i18n/en-US.json'), 'rb').read()
    return 'hash:' + hashlib.sha256(blob).hexdigest()[:16]

# ---------- asar 读写 ----------
def asar_open(path):
    with open(path, 'rb') as f:
        head = f.read(16)
    json_len = int.from_bytes(head[12:16], 'little')
    with open(path, 'rb') as f:
        f.seek(16)
        header = json.loads(f.read(json_len).decode('utf-8'))
    data = open(path, 'rb').read()
    data_start = 8 + int.from_bytes(head[4:8], 'little')
    return data, header, data_start

def asar_find(header, path):
    node = header
    for seg in path.strip('/').split('/'):
        if not isinstance(node, dict) or 'files' not in node or seg not in node['files']:
            return None
        node = node['files'][seg]
    return node

def asar_entry(path, entry_path):
    data, header, data_start = asar_open(path)
    node = asar_find(header, entry_path)
    if node is None or 'size' not in node:
        raise RuntimeError('asar %s 中不存在条目 %s' % (os.path.basename(path), entry_path))
    if node.get('unpacked'):
        src = os.path.join(path + '.unpacked', entry_path.strip('/'))
        return open(src, 'rb').read(), header, -1, node
    off = int(node['offset'])
    return data[data_start + off:data_start + off + int(node['size'])], header, data_start, node

def asar_walk(header, prefix='', out=None):
    if out is None: out = []
    if isinstance(node := header, dict) and 'files' in node:
        for name, child in node['files'].items():
            asar_walk(child, prefix + '/' + name, out)
        return out
    if isinstance(header, dict) and 'size' in header:
        out.append((prefix, header))
    return out

def _integrity_node(blob, template=None):
    bs = int(template.get('blockSize', 4194304)) if isinstance(template, dict) else 4194304
    algo = template.get('algorithm', 'SHA256') if isinstance(template, dict) else 'SHA256'
    return {'algorithm': algo, 'hash': hashlib.sha256(blob).hexdigest(), 'blockSize': bs,
            'blocks': [hashlib.sha256(blob[i:i + bs]).hexdigest() for i in range(0, len(blob), bs)]}

def asar_rewrite(path, replacements=None, additions=None, removals=None):
    """重建 asar：replacements={条目路径:新bytes}；additions={新条目路径:bytes}；removals=[条目路径]。
    返回 (替换条目数, 新增条目数, 删除条目数)。写临时文件后原子替换。"""
    replacements = replacements or {}; additions = additions or {}; removals = set(removals or [])
    data, header, data_start = asar_open(path)
    tmpl = None
    for _pp, n in asar_walk(header):
        if isinstance(n.get('integrity'), dict) and n['integrity'].get('hash'):
            tmpl = n['integrity']; break
    for ep in list(replacements) + list(additions):
        if not ep.startswith('/') or '\\' in ep or '..' in ep.split('/'):
            raise RuntimeError('条目路径须为 / 开头且不含 .. 的绝对路径: ' + ep)
    entries = asar_walk(header)
    for ep in replacements:
        if asar_find(header, ep) is None:
            raise RuntimeError('asar 中不存在待替换条目: ' + ep)
    # 已存在的"新增"条目转为替换语义，保证条目计数一致
    for ep in list(additions):
        if asar_find(header, ep) is not None:
            replacements[ep] = additions.pop(ep)

    out = bytearray(); seen = {}; patched = 0
    for epath, node in entries:
        if epath in removals: continue
        if node.get('unpacked'):
            if epath in replacements:
                blob = replacements[epath]; patched += 1
                upath = os.path.join(path + '.unpacked', epath.strip('/'))
                os.makedirs(os.path.dirname(upath), exist_ok=True)
                with open(upath, 'wb') as f: f.write(blob)
                node['size'] = len(blob)
            continue
        if epath in replacements:
            blob = replacements[epath]; patched += 1
            node['offset'] = str(len(out)); node['size'] = len(blob)
            if isinstance(node.get('integrity'), dict):
                node['integrity'] = _integrity_node(blob, node['integrity'])
            out += blob
        else:
            key = (int(node.get('offset', 0)), int(node['size']))
            if key in seen:
                node['offset'] = str(seen[key]); continue
            blob = data[data_start + key[0]:data_start + key[0] + key[1]]
            seen[key] = len(out); node['offset'] = str(len(out))
            out += blob

    def parent_node(epath):
        node = header
        for seg in posixpath.dirname(epath).strip('/').split('/'):
            if not seg: continue
            node = node.setdefault('files', {}).setdefault(seg, {'files': {}})
            if 'files' not in node: node['files'] = {}
        return node

    for epath, blob in sorted(additions.items()):
        parent = parent_node(epath)
        name = posixpath.basename(epath)
        node = {'size': len(blob), 'offset': str(len(out)), 'integrity': _integrity_node(blob, tmpl)}
        parent['files'][name] = node
        out += blob

    removed = 0
    for epath in removals:
        parent = header
        segs = epath.strip('/').split('/')
        for seg in segs[:-1]:
            if not isinstance(parent, dict) or 'files' not in parent or seg not in parent['files']:
                parent = None; break
            parent = parent['files'][seg]
        if isinstance(parent, dict) and 'files' in parent and segs[-1] in parent['files']:
            del parent['files'][segs[-1]]; removed += 1

    hb = json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    # 复刻官方格式：[4][@4][@8][hb] json NUL 填充(4 字节对齐) 数据
    pad = (-(len(hb) + 5)) % 4
    size8 = len(hb) + 5 + pad
    new = struct.pack('<4I', 4, size8 + 4, size8, len(hb)) + hb + b'\x00' + b'\x00' * pad + out
    new_data_start = 8 + size8 + 4

    # 自检：重新解析，逐条目校验 SHA-256 完整性与替换/新增内容
    jlen = int.from_bytes(new[12:16], 'little')
    hdr2 = json.loads(new[16:16 + jlen].decode('utf-8'))
    total = [0]; hash_bad = [0]
    for epath, node in asar_walk(hdr2):
        if node.get('unpacked'): continue
        total[0] += 1
        blob = new[new_data_start + int(node['offset']):new_data_start + int(node['offset']) + int(node['size'])]
        if isinstance(node.get('integrity'), dict) and node['integrity'].get('hash'):
            if hashlib.sha256(blob).hexdigest() != node['integrity']['hash']:
                hash_bad[0] += 1
        if epath in replacements and blob != replacements[epath]:
            raise RuntimeError('自检失败：替换条目内容不符 %s' % epath)
        if epath in additions and blob != additions[epath]:
            raise RuntimeError('自检失败：新增条目内容不符 %s' % epath)
    old_total = sum(1 for _ep, n in entries if not n.get('unpacked'))
    if total[0] != old_total + len(additions) - removed:
        raise RuntimeError('自检失败：条目数 %d（预期 %d）' % (total[0], old_total + len(additions) - removed))
    if hash_bad[0]:
        raise RuntimeError('自检失败：%d 个条目 hash 不符' % hash_bad[0])

    tmp = path + '.zh-tmp'
    with open(tmp, 'wb') as f: f.write(new)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return patched, len(additions), removed

# ---------- 状态 ----------
MANIFEST_PATH = os.path.join(BACKUP, 'manifest.json')
VERSION_PATH = os.path.join(BACKUP, '.version')

def read_state():
    if os.path.exists(MANIFEST_PATH):
        try: return load(MANIFEST_PATH)
        except Exception: pass
    return {'backups': [], 'deployed': []}

def backup_file(state, rel):
    src = os.path.join(RESOURCES, rel)
    dst = os.path.join(BACKUP, rel)
    if not os.path.isfile(src): return
    if rel in state['backups'] or rel in state['deployed']: return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    state['backups'].append(rel)

def mark_deployed(state, rel):
    if rel not in state['deployed']:
        state['deployed'].append(rel)

def save_state(state):
    os.makedirs(BACKUP, exist_ok=True)
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump({'backups': state['backups'], 'deployed': state['deployed']},
                  f, ensure_ascii=False, indent=1)

# ---------- 词典校验（ICU MessageFormat 结构安全检查，兼容官方中文复数简化） ----------
_TAG_RE = re.compile(r'</?[A-Za-z][A-Za-z0-9_.-]*(?:\s*/)?\s*>')

def _parse_icu_block(s, start):
    n = len(s); i = start + 1
    while i < n and s[i].isspace(): i += 1
    m_var = re.match(r'[A-Za-z_][A-Za-z0-9_.-]*', s[i:])
    if not m_var: return None
    var = m_var.group(0); i += len(var)
    while i < n and s[i].isspace(): i += 1
    if i >= n: return None
    if s[i] == '}': return i + 1, {'var': var, 'kind': 'plain', 'branches': {}}
    if s[i] != ',': return None
    i += 1
    while i < n and s[i].isspace(): i += 1
    m_type = re.match(r'[A-Za-z_][A-Za-z0-9_.-]*', s[i:])
    if not m_type: return None
    ftype = m_type.group(0); i += len(ftype)
    while i < n and s[i].isspace(): i += 1
    if ftype not in ('plural', 'selectordinal', 'select'):
        depth = 1; in_q = False
        while i < n and depth > 0:
            ch = s[i]
            if ch == "'":
                if i + 1 < n and s[i + 1] == "'": i += 2; continue
                elif not in_q and i + 1 < n and s[i + 1] in '{}#': in_q = True
                elif in_q: in_q = False
            elif not in_q:
                if ch == '{': depth += 1
                elif ch == '}': depth -= 1
            i += 1
        return (i, {'var': var, 'kind': ftype, 'branches': {}}) if depth == 0 else None
    if i >= n or s[i] != ',': return None
    i += 1; branches = {}
    while i < n:
        while i < n and s[i].isspace(): i += 1
        if i >= n: return None
        if s[i] == '}': return i + 1, {'var': var, 'kind': ftype, 'branches': branches}
        if ftype in ('plural', 'selectordinal') and s[i:].startswith('offset:'):
            m_off = re.match(r'offset:\s*-?\d+', s[i:])
            if not m_off: return None
            i += len(m_off.group(0)); continue
        m_key = re.match(r'[^\s{}]+', s[i:])
        if not m_key: return None
        bkey = m_key.group(0); i += len(bkey)
        while i < n and s[i].isspace(): i += 1
        if i >= n or s[i] != '{': return None
        bstart = i + 1; depth = 1; j = bstart; in_q = False
        while j < n and depth > 0:
            ch = s[j]
            if ch == "'":
                if j + 1 < n and s[j + 1] == "'": j += 2; continue
                elif not in_q and j + 1 < n and s[j + 1] in '{}#<>': in_q = True
                elif in_q: in_q = False
            elif not in_q:
                if ch == '{': depth += 1
                elif ch == '}': depth -= 1
            j += 1
        if depth != 0: return None
        branches[bkey] = s[bstart:j - 1]; i = j
    return None

def _tags_balanced(tag_list):
    stack = []
    for t in tag_list:
        if t.endswith('/>'): continue
        if t.startswith('</'):
            name = t[2:-1].strip()
            if not stack or stack[-1] != name: return False
            stack.pop()
        else:
            stack.append(t[1:-1].strip())
    return not stack

def _parse_icu_meta(text):
    s = str(text); all_vars = set(); non_plural_vars = set()
    plural_vars = {}; select_vars = {}; all_tags = []
    def walk(sub):
        n = len(sub); i = 0; in_q = False; plain_buf = []
        while i < n:
            ch = sub[i]
            if ch == "'":
                if i + 1 < n and sub[i + 1] == "'": plain_buf.append("'"); i += 2; continue
                elif not in_q and i + 1 < n and sub[i + 1] in '{}#<>': in_q = True; i += 1; continue
                elif in_q: in_q = False; i += 1; continue
            if not in_q and ch == '{':
                res = _parse_icu_block(sub, i)
                if res is None: return False
                end_i, info = res; v, k = info['var'], info['kind']
                all_vars.add(v)
                if k in ('plural', 'selectordinal'):
                    if 'other' not in info['branches']: return False
                    plural_vars.setdefault(v, set()).update(info['branches'].keys())
                    for btext in info['branches'].values():
                        if not walk(btext): return False
                elif k == 'select':
                    if 'other' not in info['branches']: return False
                    non_plural_vars.add(v)
                    select_vars.setdefault(v, set()).update(info['branches'].keys())
                    for btext in info['branches'].values():
                        if not walk(btext): return False
                else:
                    non_plural_vars.add(v)
                i = end_i; continue
            if not in_q and ch == '}': return False
            plain_buf.append(ch); i += 1
        for t in _TAG_RE.findall(''.join(plain_buf)): all_tags.append(t)
        return True
    ok = walk(s)
    return all_vars, non_plural_vars, plural_vars, select_vars, all_tags, ok

def struct_ok(en, zh):
    en_vars, en_np, en_pl, en_sel, en_tags, en_ok = _parse_icu_meta(en)
    zh_vars, zh_np, zh_pl, zh_sel, zh_tags, zh_ok = _parse_icu_meta(zh)
    if not en_ok:
        a, b = str(en), str(zh)
        return (a.count('{') == b.count('{') and a.count('}') == b.count('}')
                and sorted(re.findall(r'<[^>]*>', a)) == sorted(re.findall(r'<[^>]*>', b)))
    if not zh_ok: return False
    if not zh_vars.issubset(en_vars): return False
    if not en_np.issubset(zh_vars): return False
    if set(zh_sel.keys()) != set(en_sel.keys()): return False
    for v, keys in en_sel.items():
        if zh_sel[v] != keys: return False
    for v, keys in en_pl.items():
        if v in zh_pl:
            if '=0' in keys and '=0' not in zh_pl[v]: return False
            if not zh_pl[v].issubset(keys | {'other', 'one', 'zero', '=0', '=1'}): return False
        elif v in zh_vars:
            if '=0' in keys: return False
        else:
            if '#' in str(en) or '=0' in keys: return False
    if set(zh_tags) != set(en_tags): return False
    if _tags_balanced(en_tags) and not _tags_balanced(zh_tags): return False
    if not en_pl and not en_sel and sorted(en_tags) != sorted(zh_tags): return False
    return True

def merge_dict(en_map, zh_map):
    out = {}; translated = 0; fell_back = 0
    for k, en in en_map.items():
        zh = zh_map.get(k)
        if zh is not None and zh != en and struct_ok(en, zh):
            out[k] = zh; translated += 1
        else:
            if zh is not None and zh != en: fell_back += 1
            out[k] = en
    return out, translated, fell_back

def write_json_atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.zh-tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)

# ---------- 版本无关 locale 规则（按内容匹配；与 Windows 安装器同源） ----------
LOCALE_RULES = [
    ('["en-US","de-DE","fr-FR","ko-KR', '["en-US","zh-CN","de-DE","fr-FR","ko-KR'),
    ('"en-US":{name:"English (United States)",localName:"English (United States)"}',
     '"zh-CN":{name:"Chinese (Simplified)",localName:"简体中文"},"en-US":{name:"English (United States)",localName:"English (United States)"}'),
    ('case"en-US":return["language","en"];', 'case"zh-CN":return["language","zh-CN"];case"en-US":return["language","en"];'),
    # Linux 版适配（压缩后的变量名随构建变化，按固定片段匹配）
    ('?"Plugins":"Customize"', '?"Plugins":"自定义"'),
    ('??"Local task"', '??"本地任务"'),
]

GUARD_RE = re.compile(
    r'(?<![A-Za-z0-9_$-])(?:as|code|command|component|displayName|glyph|icon|iconName|id|key|kind|leadingIcon|locale|name|path|role|source|state|status|trailingIcon|type|value|variant)\s*[:=]\s*$')

def build_js_rules():
    exact_rules = list(LOCALE_RULES)
    for rel in ('assets-manifest.json', 'hardcoded.json'):
        try:
            rules = load(os.path.join(LANG, rel))
            if rel == 'assets-manifest.json':
                rules = rules.get('patches', [])
            for r in rules:
                b, a = r.get('before', ''), r.get('after', '')
                if b and a and b != a: exact_rules.append((b, a))
        except FileNotFoundError:
            pass
    plain_map = {}
    try:
        for s, t in load(os.path.join(LANG, 'frontend-hardcoded.json')):
            if not s or s == t: continue
            if re.search(r'["\\=;{}\r\n`]', s) or re.search(r'["\\{}\r\n`]', t): continue
            plain_map[s] = t
    except FileNotFoundError:
        pass
    return exact_rules, plain_map

# ---------- JS 词法扫描：给文字规则定位字符串字面量 ----------
# 文字规则（frontend-hardcoded.json 等）按“字符串解码后的值”查表替换，所以要先知道源码里哪些引号、反引号是字符串字面量的起止。
# 这里不按出现顺序配对引号，而是照搬 acorn 分词器的上下文规则逐个记号地推进：只有“此处可以开始表达式”的位置，
# 引号才会开启字符串、斜杠才会开启正则字面量；注释、正则里的引号、另一种引号的字符串、模板字符串里的引号都不再干扰定位。
# 另外带上了解析器层面会改变切分的几条规则（acorn 的 parseExprAtom 在需要一个表达式却读到除号时，把斜杠重读成正则；
# V8 也是这样切分的）：
#   · if / for / while / with 的条件之后，函数或类的声明体之后，import / from 引入的模块路径换行之后，靠换行省略分号的
#     break / continue / debugger 之后，以及语句块的右花括号之后（包括靠换行省略分号开始的语句块、do 的主体、
#     类的静态初始化块——这几种在分词器里按对象字面量入栈，是解析器把它们当语句块用的）；
#   · await、yield、for…of 的 of 后面跟的函数或类是表达式；点号后面的 of / yield / await 以及其它关键字只是属性名。
# 适用范围与已知取舍（详见 zh-i18n/linux-readme.md 的「已知限制」）：
#   · 只处理 ES 模块代码（前端 /assets 下的 JS 都是模块）。旧式 HTML 注释（<!-- 与行首的 -->）在模块里是语法错误，不识别；
#   · acorn 与 V8 切分不同的一类写法按 V8 处理：异步函数表达式的体之后紧跟斜杠（x = async function(){} ⇢ /re/），
#     acorn 读成正则，V8 读除号；对照工具遇到这类文件会单独计数，不算不一致；
#   · 遇到残缺输入（未闭合的字符串、注释、模板，非法转义等）直接抛 ValueError，由安装器中止，不做任何兜底。
# 配套工具在 zh-i18n/work/：js-lex-test.py（单元测试，已并入 verify-chain.sh 的第 00 步）、js-audit.py 与 js-ast-dump.js
# （以 acorn 的解析结果为标准答案审计官方安装包里的全部 JS，每次同步新版本后运行）。修改这里以后三样都要重跑。
_JS_B_STAT, _JS_B_EXPR, _JS_B_TMPL = 0, 1, 2      # { }：语句块 / 对象字面量 / ${ … }
_JS_P_STAT, _JS_P_EXPR, _JS_Q_TMPL = 3, 4, 5      # ( )：if/for/while/with 的条件 / 其它括号；模板字符串
_JS_F_STAT, _JS_F_EXPR, _JS_F_GEN, _JS_F_EXPR_GEN = 6, 7, 8, 9     # function/class 主体：声明 / 表达式 / 生成器 / 生成器表达式
_JS_IS_EXPR = frozenset((_JS_B_EXPR, _JS_P_EXPR, _JS_Q_TMPL, _JS_F_EXPR, _JS_F_EXPR_GEN))
_JS_IS_FUNC = frozenset((_JS_F_STAT, _JS_F_EXPR, _JS_F_GEN, _JS_F_EXPR_GEN))
_JS_IS_GEN = frozenset((_JS_F_GEN, _JS_F_EXPR_GEN))
_JS_KEYWORDS = frozenset((
    'break', 'case', 'catch', 'continue', 'debugger', 'default', 'do', 'else', 'finally', 'for', 'function', 'if',
    'return', 'switch', 'throw', 'try', 'var', 'const', 'while', 'with', 'new', 'this', 'super', 'class', 'extends',
    'export', 'import', 'null', 'true', 'false', 'in', 'instanceof', 'typeof', 'void', 'delete'))
_JS_KEYWORDS_BEFORE_EXPR = frozenset((
    'case', 'default', 'do', 'else', 'return', 'throw', 'extends', 'in', 'instanceof', 'typeof', 'void', 'delete', 'new'))
_JS_LINE_BREAK_RE = re.compile(r'\r\n?|[\n\u2028\u2029]')
_JS_SPACE = frozenset(' \t\v\f\u00a0\r\n\u2028\u2029\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000\ufeff')
# 会改变上下文的记号：括号、冒号、问号、星号、function、class。每个分支都以单个字面量开头，正则引擎才能按首字符快速跳过其它位置；
# function/class 会连标识符里的同名字样一起匹配到，是否为关键字在读到时再判断。
_JS_SPECIAL_RE = re.compile(r'\(|\)|\{|\}|\*|:|\?|function|class')
_JS_PAREN_CHECK = frozenset('frhe') | _JS_SPACE     # ( 之前是这个字符时，才可能紧跟在 if/for/while/with 后面
_JS_WORD_RE = re.compile(r'[\w$]')
_JS_CODE_RE = re.compile(r'["\'`/]')                   # 代码状态下需要停下来看的字符
_JS_STR_DQ_RE = re.compile(r'["\\\n\r]')
_JS_STR_SQ_RE = re.compile(r"['\\\n\r]")
_JS_TPL_RE = re.compile(r'[`$\\\r\n\u2028\u2029]')
_JS_REGEX_RE = re.compile(r'[\\/\[\]\n\r\u2028\u2029]')
_JS_FLAGS_RE = re.compile(r'[\w$]*')
_JS_OP_CHARS = frozenset('+-*/%<>=!&|^~?:.,;()[]{}')
_JS_OP_TOKEN_RE = re.compile(
    r'>>>=|\.\.\.|===|!==|\*\*=|<<=|>>=|>>>|&&=|\|\|=|\?\?=|=>|==|!=|<=|>=|&&|\|\||\?\?|\?\.|\+\+|--|\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|\*\*'
    r'|[-+*/%<>=!&|^~?:.,;()\[\]{}]')
_JS_WORD_END_RE = re.compile(r'[^\W\d][\w$]*$')
_JS_NUM_END_RE = re.compile(r'\d[\w.]*$')
_JS_IDENT_START_RE = re.compile(r'(?:[^\W\d]|\\)|$')     # 名字的开头：字母、_、$，或 \uXXXX 转义开头的反斜杠；到了文件末尾也算
_JS_SIMPLE_ESCAPE = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'v': '\v', 'f': '\f'}
_JS_ESCAPE_RE = re.compile(r'\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[0-7]{1,3}|\r\n|[\s\S])')
_JS_SURROGATE_RE = re.compile('[\ud800-\udfff]')
_JS_NEEDS_QUOTE_RE = re.compile(r'["\'`\\\x00-\x1f\u2028\u2029]|\$(?=\{)')
_JS_QUOTE_ESCAPES = {'"': '\\"', "'": "\\'", '`': '\\`', '\\': '\\\\', '$': '\\$', '\n': '\\n', '\r': '\\r', '\t': '\\t',
                     '\b': '\\b', '\f': '\\f', '\v': '\\v', '\u2028': '\\u2028', '\u2029': '\\u2029'}
_JS_FILTER_LEN = 8                                # 预筛用的键前缀长度
_JS_FILTER_STOP = frozenset('"\'\\/')             # 压缩器会转义的 ASCII 字符，预筛前缀遇之截断

def _js_before_expr(prev):
    """上一个词法单元之后能否开始表达式（acorn TokenType.beforeExpr）；prev 是上一个单元的类别。"""
    if prev in _JS_KEYWORDS: return prev in _JS_KEYWORDS_BEFORE_EXPR
    return prev not in ('str', 'regexp', 'backquote', 'name', 'num', 'eof', ')', ']', '}', '.', '?.', '++', '--')

def _js_unescape(raw, template):
    """解码字符串/模板里的转义序列。template=True 时遇到无效转义返回 None（对应 acorn 的 cooked = null）；
    普通字符串里的无效转义在合法 JS 中不可能出现，抛 ValueError。"""
    out = []; i = 0
    for m in _JS_ESCAPE_RE.finditer(raw):
        out.append(raw[i:m.start()]); e = m.group(1); c = e[0]; i = m.end(); bad = False
        if c in _JS_SIMPLE_ESCAPE:
            out.append(_JS_SIMPLE_ESCAPE[c])
        elif c == 'x' or c == 'u':
            if len(e) == 1 or int(e[2:-1] if e[1] == '{' else e[1:], 16) > 0x10FFFF: bad = True
            else: out.append(chr(int(e[2:-1] if e[1] == '{' else e[1:], 16)))
        elif '0' <= c <= '7':
            n = int(e, 8); extra = ''
            if n > 255: extra = e[-1]; e = e[:-1]; n = int(e, 8)
            bad = template and (e != '0' or raw[i:i + 1] in ('8', '9'))
            if not bad: out.append(chr(n) + extra)
        elif c in '\r\n\u2028\u2029':
            pass                                   # 行续接，不产生字符
        elif template and c in '89':
            bad = True
        else:
            out.append(c)                          # 身份转义：\' \" \\ \$ \` 以及非严格模式下的 \8 \9
        if bad:
            if template: return None
            raise ValueError('字符串里的转义序列无效：%r' % m.group(0))
    out.append(raw[i:])
    val = ''.join(out)
    if _JS_SURROGATE_RE.search(val):               # \uD83D\uDD25 这类代理对要合成一个码点，才是 JS 语义下的字符串值
        val = val.encode('utf-16-le', 'surrogatepass').decode('utf-16-le', 'surrogatepass')
    return val

def _js_next_char(s, pos):
    """pos 之后第一个有效字符（跳过空白和注释）；到文件尾返回 ''。"""
    n = len(s)
    while pos < n:
        c = s[pos]
        if c in _JS_SPACE: pos += 1
        elif c == '/' and s[pos + 1:pos + 2] == '*':
            e = s.find('*/', pos + 2)
            if e < 0: raise ValueError('JS 词法扫描失败：块注释未闭合')
            pos = e + 2
        elif c == '/' and s[pos + 1:pos + 2] == '/':
            m = _JS_LINE_BREAK_RE.search(s, pos + 2)
            if m is None: return ''
            pos = m.start()
        else:
            return c
    return ''

def _js_quote(text, quote):
    """把译文写成以 quote（" ' ` 之一）包裹的 JS 字符串字面量。文字规则的译文按构造不含引号、反斜杠和换行，这里仍做转义以防规则文件日后放开。"""
    out = []; i = 0
    for m in _JS_NEEDS_QUOTE_RE.finditer(text):
        ch = m.group()
        if ch == quote or ch == '\\' or ord(ch) < 0x20 or ch in '\u2028\u2029' or (quote == '`' and ch == '$'):
            out.append(text[i:m.start()]); out.append(_JS_QUOTE_ESCAPES.get(ch) or '\\x%02x' % ord(ch)); i = m.end()      # 表里没有的控制字符按 \xHH 转义
    out.append(text[i:])
    return quote + ''.join(out) + quote

def _js_rule_filter(plain_map):
    """给文字规则建预筛，返回 (候选正则, 定长前缀集合, 短前缀元组, 开头就需转义的键的首字符集合)。"""
    fixed = set(); short = []; esc = set()
    for key in plain_map:
        n = 0
        while n < len(key) and n < _JS_FILTER_LEN:
            c = key[n]
            if c in _JS_FILTER_STOP or not c.isascii() or not c.isprintable(): break
            n += 1
        if n >= _JS_FILTER_LEN: fixed.add(key[:n])
        elif n: short.append(key[:n])
        else: esc.add(key[0])
    first = ''.join(re.escape(c) for c in sorted({p[0] for p in fixed} | {p[0] for p in short} | esc))
    return re.compile('["\'`](?:[' + first + ']|\\\\)'), frozenset(fixed), tuple(short), frozenset(esc)

_JS_RULE_FILTER = None                             # (规则表, 候选正则, 定长前缀集合, 短前缀元组, 转义开头的首字符集合)

def _js_may_hit(text, plain_map):
    """快速预筛：文件里有没有以某条文字规则的前缀开头的字符串。成立条件是压缩器只把非 ASCII 字符、引号、反斜杠和斜杠写成转义，
    规则开头连续的普通 ASCII 字符在源码里原样出现；不满足的文件不做词法扫描。zh-i18n/work/js-audit.py 在同步时核对这一前提。"""
    global _JS_RULE_FILTER
    if _JS_RULE_FILTER is None or _JS_RULE_FILTER[0] is not plain_map:
        _JS_RULE_FILTER = (plain_map,) + _js_rule_filter(plain_map)
    _, cre, fixed, short, esc = _JS_RULE_FILTER
    for m in cre.finditer(text):
        pos = m.start() + 1
        if text[pos] == '\\' or text[pos] in esc or text[pos:pos + _JS_FILTER_LEN] in fixed or text.startswith(short, pos):
            return True
    return False

class _JsLex:
    """JS 词法扫描器。tokens() 扫描整个文件并返回词法单元列表：
         ('str', 起, 止, 引号, 解码值)、('tpl', 起, 止, 解码值或 None, 插值个数, [(段起, 段止, 段原文), …])、('re', 起, 止)
       含 ${} 插值或无效转义的模板解码值为 None。按 ES 模块代码处理（旧式 HTML 注释在模块里不是注释）。遇到未闭合的字符串、模板、正则或注释时抛 ValueError。
       prev 是上一个记号的类别，prev_text 只在 prev == 'name' 时有意义。"""

    def __init__(self, s):
        self.s = s; self.n = len(s)
        self.ctx = [_JS_B_STAT]
        self.ea = True                 # 当前位置能否开始表达式（acorn 的 exprAllowed）
        self.prev = 'eof'; self.prev_text = ''; self.prev_end = 0     # 上一个词法单元：类别 / 原文 / 结束位置
        self.pos = 0
        self.out = []
        self.tern = {}                              # 每一层括号里尚未配对的三目问号数，按 ctx 下标记
        self.fasync = {}                            # function 关键字建起的帧是否 async，按 ctx 下标记；class 帧记 None
        self.colon_tern = False                     # 刚读过的冒号是不是三目运算符的冒号
        self.fdecl = set()                          # 语句层面的函数 / 类声明所在的帧（ctx 下标）
        self.close_paren_stat = False               # 最近弹出的圆括号是不是 if/for/while/with 的条件
        self.close_decl = False                     # 最近弹出的花括号是不是函数 / 类声明的主体
        self.str_import = False                     # 最近读到的字符串是不是 import / from 引入的模块路径
        self.async_stmt = False                     # 最近读到的 async 是不是处在语句开头
        self.label_break = False                    # 最近读到的标识符是不是紧跟在 break / continue 后面的标签
        self.await_for = False                     # 最近读到的 await 是不是 for await 的 await
        self.cmt_end = -1                          # 最近跳过的块注释的结束位置
        self.sblock = set()                        # 靠换行省略分号开始的语句块所在的帧（ctx 下标），词法上按对象字面量入栈
        self.fn_real = False                      # 刚读到的 function / class 关键字是不是真的开始了函数或类
        self.star_method = False                  # 刚读到的星号后面是不是“一个方法名加左圆括号”（生成器方法）
        self.method_paren = set()                 # 生成器方法参数列表所在的帧（ctx 下标）
        self.after_method_paren = False           # 刚弹出的圆括号是不是生成器方法的参数列表
        self.genblock = set()                     # 生成器方法主体所在的帧（ctx 下标）
        self.pstat_for = set()                   # for 头所在的帧（ctx 下标）
        self.sctx = set()                        # 解析器当作语句块、词法上却按对象字面量入栈的帧（do 的主体），ctx 下标
        self.yield_op = False                   # 刚读到的 yield 是不是作关键字用（点号后面的 yield 是属性名，不算）
        self.operand_kw = False                  # 刚读到的 of / await 是不是作关键字用（for…of 的 of、await 的操作数；点号后面的只是属性名）

    def _fail(self, pos, msg):
        raise ValueError('JS 词法扫描在偏移 %d 处失败：%s；附近源码：%r' % (pos, msg, self.s[max(0, pos - 60):pos + 60]))

    def _line_end(self, p):
        m = _JS_LINE_BREAK_RE.search(self.s, p)
        return self.n if m is None else m.start()

    def tokens(self):
        s = self.s
        if s.startswith('#!'):                      # shebang 行
            self.pos = self._line_end(2)
        limit = sys.getrecursionlimit()
        if limit < 20000: sys.setrecursionlimit(20000)      # 模板字符串里的 ${…} 是递归读取的，嵌套很深时需要更多的调用层数
        try:
            self._run(False, _JS_CODE_RE)
        finally:
            sys.setrecursionlimit(limit)
        return self.out

    def _run(self, in_template, code_re):
        """从 self.pos 扫到文件尾；in_template=True 时扫到闭合 ${ 的 } 为止。"""
        s = self.s; n = self.n; out = self.out
        seg = self.pos
        while True:
            m = code_re.search(s, seg) if seg < n else None
            t = m.group() if m is not None else ''
            if self._scan(seg, n if m is None else m.start(), in_template, t == '/'):
                return
            if m is None:
                return
            p = m.start()
            if t == '"' or t == "'":
                self.str_import = self._import_spec(seg, p)       # import "x"、from "x" 的模块路径之后只能是一条新语句
                m2 = (_JS_STR_DQ_RE if t == '"' else _JS_STR_SQ_RE).search(s, p + 1)
                if m2 is None or m2.group() != t:
                    out.append(self._read_string(p, t))
                else:
                    end = m2.end(); raw = s[p + 1:end - 1]
                    self._end_str(end)
                    out.append(('str', p, end, t, raw if '\\' not in raw else _js_unescape(raw, False)))
                seg = self.pos
            elif t == '`':
                out.append(self._read_template(p, code_re))
                seg = self.pos
            elif t == '/':
                c2 = s[p + 1:p + 2]
                if c2 == '*':
                    e = s.find('*/', p + 2)
                    if e < 0: self._fail(p, '块注释未闭合')
                    seg = self.cmt_end = e + 2
                elif c2 == '/':
                    seg = self._line_end(p + 2)
                elif self.ea or self._slash_regex(p):
                    out.append(self._read_regex(p))
                    seg = self.pos
                else:                              # 除号 / 除法赋值：普通运算符
                    t = '/=' if c2 == '=' else '/'
                    self.prev = self.prev_text = t; self.ea = True; seg = self.prev_end = self.pos = p + len(t)
            else:
                raise AssertionError('词法扫描停在了意外的字符上：%r' % t)

    def _scan(self, a, b, in_template, tail):
        """处理纯代码段 s[a:b] 里的括号、冒号、星号和 function/class，返回 True 表示停在闭合 ${ 的 } 上（此时 self.pos 已越过它）。
        tail=True 时把段末的普通词法单元也当作刚读完的单元：下一个记号是斜杠、--、< 或注释的话，它的判定依赖这个状态；
        下一个记号是字符串或模板时不需要。段内其它词法单元只在需要时回看最后一个。"""
        s = self.s; ctx = self.ctx
        last = a
        for m in _JS_SPECIAL_RE.finditer(s, a, b):
            p, q = m.span(); t = s[p]
            if t != '(': self.star_method = False            # 星号之后不是紧跟左圆括号：不是方法名前的星号
            if t != '{': self.after_method_paren = False     # 参数列表之后不是紧跟左花括号：不是方法主体
            if t == ')':
                self.close_paren_stat = False
                if len(ctx) == 1: self.ea = True
                else:
                    out = ctx.pop()
                    if out == _JS_B_STAT and ctx[-1] in _JS_IS_FUNC: out = ctx.pop()
                    self.ea = out not in _JS_IS_EXPR
                    self.close_paren_stat = out == _JS_P_STAT
                    self.after_method_paren = len(ctx) in self.method_paren; self.method_paren.discard(len(ctx)); self.pstat_for.discard(len(ctx))
                self.prev = t; self.prev_end = q; last = q
            elif t == '(':
                if p == self.cmt_end:                             # 紧跟在块注释后面：括号前的记号在注释前已经读过
                    head = self._paren_head()
                elif p == 0 or (s[p - 1] not in _JS_PAREN_CHECK and s[p - 5:p] != 'await'):      # 前面不可能是 if/for/while/with/await
                    head = False
                else:
                    if p > last:
                        info = self._prev_regular(last, p)
                        if info is not None: self._take(info, last)
                    head = self._paren_head()
                self._push(_JS_P_STAT if head else _JS_P_EXPR)
                if head == 'for': self.pstat_for.add(len(ctx) - 1)
                if self.star_method: self.method_paren.add(len(ctx) - 1); self.star_method = False
                self.ea = True; self.prev = t; self.prev_end = q; last = q
            elif t == '{':
                if p > last:
                    info = self._prev_regular(last, p)
                    if info is not None: self._take(info, last)
                block = self._brace_is_block(p)
                self._push(_JS_B_STAT if block else _JS_B_EXPR)
                if not block and self._asi_block(p): self.sblock.add(len(ctx) - 1)
                if self.prev == 'do': self.sctx.add(len(ctx) - 1)          # do 的主体：解析器按语句块处理
                elif (not block and self.prev == 'name' and self.prev_text == 'static' and len(ctx) >= 3
                      and ctx[-2] == _JS_B_STAT and ctx[-3] in _JS_IS_FUNC and self.fasync.get(len(ctx) - 3, '') is None):
                    self.sctx.add(len(ctx) - 1)         # 类主体里的 static { … }：静态初始化块，解析器同样按语句块处理
                if self.after_method_paren: self.genblock.add(len(ctx) - 1)
                self.ea = True; self.prev = t; self.prev_end = q; last = q
            elif t == '}':
                self.close_decl = False
                if len(ctx) == 1: self.ea = True
                else:
                    out = ctx.pop()
                    if out == _JS_B_STAT and ctx[-1] in _JS_IS_FUNC: out = ctx.pop()
                    self.ea = out not in _JS_IS_EXPR
                    self.close_decl = ((out in _JS_IS_FUNC and len(ctx) in self.fdecl)
                                      or (out == _JS_B_EXPR and len(ctx) in self.sblock))
                    self.fdecl.discard(len(ctx)); self.sblock.discard(len(ctx)); self.sctx.discard(len(ctx)); self.genblock.discard(len(ctx))
                    if in_template and ctx[-1] == _JS_Q_TMPL:
                        self.prev = t; self.pos = self.prev_end = q
                        return True
                self.prev = t; self.prev_end = q; last = q
            elif t == ':':
                i = len(ctx) - 1; n = self.tern.get(i, 0)
                self.colon_tern = n > 0                # 配上了三目问号：是三目运算符的冒号，不是标签、case 或对象字面量的冒号
                if n: self.tern[i] = n - 1
                if ctx[-1] in _JS_IS_FUNC: ctx.pop()
                self.ea = True; self.prev = t; self.prev_end = q; last = q
            elif t == '?':
                c2 = s[p + 1:p + 2]
                if c2 == '?' or (c2 == '.' and not '0' <= s[p + 2:p + 3] <= '9'): continue    # ?? 与 ?. 是普通运算符，用到时再回看
                self.tern[len(ctx) - 1] = self.tern.get(len(ctx) - 1, 0) + 1
                self.ea = True; self.prev = t; self.prev_end = q; last = q
            elif t == '*':
                if self.prev == 'function' and self.fn_real:
                    k = p
                    while k > last and s[k - 1] in _JS_SPACE: k -= 1
                    if k == last and ctx[-1] in _JS_IS_FUNC: ctx[-1] = _JS_F_EXPR_GEN if ctx[-1] == _JS_F_EXPR else _JS_F_GEN
                else:
                    self.star_method = self._method_star(q)      # 其它星号：后面若是“一个方法名加左圆括号”，就是生成器方法
                self.ea = True; self.prev = t; self.prev_end = q; last = q
            elif not ((p > 0 and _JS_WORD_RE.match(s, p - 1)) or _JS_WORD_RE.match(s, q)):     # 确是 function / class 关键字
                if p > last:
                    info = self._prev_regular(last, p)
                    if info is not None: self._take(info, last)
                w = s[p:q]
                self.fn_real = self._function_or_class(w, p, q)
                self.prev = w; self.prev_end = q; last = q
        if tail and b > last:
            info = self._prev_regular(last, b)
            if info is not None: self._take(info, last)
        self.pos = b
        return False

    def _prev_regular(self, a, p):
        """回看 s[a:p] 的最后一个普通词法单元，返回 (类别, 原文, 起, 止)；类别为 kw / name / num / op。前面只有空白时返回 None。"""
        s = self.s
        i = p
        while i > a and s[i - 1] in _JS_SPACE: i -= 1
        if i == a: return None
        c = s[i - 1]
        if c in _JS_OP_CHARS:
            j = i
            while j > a and s[j - 1] in _JS_OP_CHARS: j -= 1
            tok = _JS_OP_TOKEN_RE.findall(s, j, i)[-1]
            return ('op', tok, i - len(tok), i)
        m = _JS_WORD_END_RE.search(s, a, i)
        if m is not None:
            w = m.group(); k = m.start()
            while k > a and s[k - 1] in _JS_SPACE: k -= 1
            if k > a and s[k - 1] == '#': return ('private', w, k - 1, i)     # 私有字段 #x：整体是一个标识符
            if w in _JS_KEYWORDS and not (k > 0 and s[k - 1] == '.' and not (k > 1 and s[k - 2] == '.')) and not (k == a and self.prev in ('.', '?.')): return ('kw', w, m.start(), i)     # ... 是展开运算符，不是属性访问
            return ('name', w, m.start(), i)
        m = _JS_NUM_END_RE.search(s, a, i)
        if m is not None: return ('num', m.group(), m.start(), i)
        return ('name', c, i - 1, i)              # 标识符里的 \uXXXX 转义结尾等：按“值”处理

    def _take(self, info, a):
        """把回看到的普通词法单元当作刚读完的单元，更新 exprAllowed 与 prev。"""
        kind, text, start, end = info
        if kind == 'op':
            ea = self._ea_before(start, a) if text in ('++', '--') else _js_before_expr(text)
            self.prev = text
        elif kind == 'kw':
            ea = text in _JS_KEYWORDS_BEFORE_EXPR; self.prev = text
        elif kind == 'name':
            dot = text in ('of', 'yield', 'await') and self._after_dot(a, start)      # x.of / 2、x.yield / 2、x.await / 2：点号后面是普通属性名
            self.yield_op = text == 'yield' and not dot
            if dot: ea = False
            elif text == 'of': ea = not self._ea_before(start, a)
            elif text == 'yield': ea = self._in_generator()
            elif text == 'await': ea = self._can_await()
            else: ea = False
            self.operand_kw = text in ('of', 'await') and ea
            if text == 'async': self.async_stmt = self._stmt_before(start, a)
            if text == 'await':
                info = self._before(a, start)
                self.await_for = info[0] == 'kw' and info[1] == 'for' and _JS_LINE_BREAK_RE.search(self.s, max(0, info[3]), start) is None
            self.label_break = self._after_break(a, start)
            self.prev = 'name'
        else:
            ea = False; self.prev = 'name' if kind == 'private' else kind; self.yield_op = False; self.operand_kw = False
        self.prev_text = text; self.prev_end = end; self.ea = ea

    def _ea_before(self, start, a):
        """位置 start 上的词法单元之前的 exprAllowed。"""
        info = self._prev_regular(a, start)
        if info is None: return self.ea
        self._take(info, a)
        return self.ea

    def _push(self, kind):
        self.ctx.append(kind); self.tern[len(self.ctx) - 1] = 0

    def _can_await(self):
        """await 之后能否跟操作数：acorn 里取决于当前作用域是否允许 await。这里只认 function 关键字建起的同步函数体——
        在它里面 await 只能是标识符；异步函数、箭头函数、方法和顶层都按“await 是关键字”处理。"""
        for i in range(len(self.ctx) - 1, 0, -1):
            if self.ctx[i] in _JS_IS_FUNC:
                if self.fasync.get(i) is not None: return self.fasync[i]     # class 的帧不是函数作用域，跳过
        return True

    def _end_str(self, end):
        self.prev = 'str'; self.prev_end = self.pos = end; self.ea = False

    def _import_spec(self, a, p):
        """位置 p 的字符串是不是模块路径：它与前一记号之间只有空白，而前一记号是 import 或 from。from 也可能是普通标识符，是不是真模块路径要到后面的斜杠才见分晓（见 _slash_regex）。"""
        s = self.s; i = p
        while i > a and s[i - 1] in _JS_SPACE: i -= 1
        if i >= a + 6 and s[i - 6:i] == 'import': k = i - 6
        elif i >= a + 4 and s[i - 4:i] == 'from': k = i - 4
        else: return False
        return k == a or (not _JS_WORD_RE.match(s, k - 1) and s[k - 1] != '.')

    def _stmt_before(self, p, a):
        """位置 p 上的记号是不是处在语句开头：前面是分号、右花括号、if/for/while/with 的右括号、文件开头，
        或者一个完整的表达式加换行（自动补分号，表达式的结尾可以是 )、]、++、-- 等运算符）。"""
        info = self._prev_regular(a, p)
        if info is not None:
            if info[0] == 'op':
                if info[1] in (';', '}'): return True
                if info[1] in (')', ']', '++', '--'): return _JS_LINE_BREAK_RE.search(self.s, info[3], p) is not None      # 以 ) ] ++ -- 结尾的表达式语句靠换行补分号
                return False
            if info[0] == 'kw': return info[1] in ('default', 'export')
            return _JS_LINE_BREAK_RE.search(self.s, info[3], p) is not None
        if self.prev in ('eof', ';', '}', '{', 'default', 'export'): return True
        if self.prev == ':' and self._in_stmt() and not self.colon_tern: return True      # 标签或 case 的冒号
        if self.prev == ')': return self.close_paren_stat or _JS_LINE_BREAK_RE.search(self.s, self.prev_end, p) is not None      # if/for/while/with 的条件之后，或以 ) 结尾的表达式语句换了行
        if self.prev in ('name', 'num', 'str', 'regexp', 'backquote', ']', '++', '--'):
            return _JS_LINE_BREAK_RE.search(self.s, self.prev_end, p) is not None
        return False

    def _before(self, a, pos):
        """pos 之前的记号 (类别, 原文, 起, 止)：段内离它最近的普通记号；pos 就在段首（注释、字符串等之后）时，
        是已经读过的上一个记号，此时起止位置记为 -1。只往前看 64 个字符，再远只可能是空白。"""
        info = self._prev_regular(max(a, pos - 64), pos)
        if info is None and pos - 64 > a: info = self._prev_regular(a, pos)
        if info is not None: return info
        p = self.prev
        if p in _JS_KEYWORDS: return ('kw', p, -1, self.prev_end)
        if p in ('name', 'str', 'num', 'regexp', 'backquote'): return (p, self.prev_text, -1, self.prev_end)
        return ('op', p, -1, self.prev_end)

    def _after_dot(self, a, start):
        info = self._before(a, start)
        return info[0] == 'op' and info[1] in ('.', '?.')

    def _after_break(self, a, start):
        """位置 start 的标识符是不是紧跟在 break / continue 后面的标签（中间只能有空白，不能换行）。"""
        s = self.s; i = start
        while i > a and s[i - 1] in _JS_SPACE: i -= 1
        if i - 5 >= a and s[i - 5:i] == 'break': k = i - 5
        elif i - 8 >= a and s[i - 8:i] == 'continue': k = i - 8
        else:
            info = self._before(a, start)
            return info[0] == 'kw' and info[1] in ('break', 'continue') and _JS_LINE_BREAK_RE.search(s, max(0, info[3]), start) is None
        return (k == a or not _JS_WORD_RE.match(s, k - 1)) and _JS_LINE_BREAK_RE.search(s, k, start) is None

    def _method_star(self, q):
        """q 处的星号是不是生成器方法名前的星号（*m(){ … }、async *m(){ … }、*[key](){ … }、*"名字"(){ … }）：
        星号与左圆括号之间恰好是一个方法名。"""
        s = self.s; n = self.n
        if self.prev == 'name' and self.prev_text == 'yield': return False       # yield * expr
        i = q
        while i < n and s[i] in _JS_SPACE: i += 1
        if i >= n: return False
        c = s[i]
        if c == '[':
            j = s.find(']', i + 1)
            if j < 0: return False
            i = j + 1
        elif c == '"' or c == "'":
            j = s.find(c, i + 1)
            if j < 0: return False
            i = j + 1
        else:
            j = i
            while j < n and (_JS_WORD_RE.match(s, j) or s[j] == '\\'): j += 1
            if j == i: return False
            i = j
        while i < n and s[i] in _JS_SPACE: i += 1
        return i < n and s[i] == '('

    def _yield_regex_ok(self):
        """刚读到的 yield 是不是在生成器方法里（星号是方法名前的星号，而不是 function*）。
        acorn 的分词器不把方法体当作生成器上下文，是解析器在需要表达式时把斜杠重读成正则。"""
        for i in range(len(self.ctx) - 1, 0, -1):
            if self.ctx[i] in _JS_IS_FUNC: return False      # 中间隔着别的函数：yield 在那个函数里另有身份
            if i in self.genblock: return True
        return False

    def _paren_head(self):
        """刚读到的圆括号是不是 if/for/while/with（含 for await）的条件括号，是则返回那个关键字：self.prev 必须已是括号前的记号。"""
        if self.prev in ('if', 'for', 'with', 'while'): return self.prev
        if self.prev == 'name' and self.prev_text == 'await' and self.await_for: return 'for'
        return None

    def _in_stmt(self):
        """当前帧是不是语句块上下文：词法上按语句块入栈，或者解析器把它当语句块用
        （do 的主体、靠换行省略分号开始的语句块；这两种在词法上按对象字面量入栈）。"""
        i = len(self.ctx) - 1
        return self.ctx[i] == _JS_B_STAT or i in self.sctx or i in self.sblock

    def _asi_block(self, p):
        """这个按对象字面量入栈的花括号，其实是不是靠换行省略分号开始的一个语句块（x = 1 ⇢ {} ⇢ /re/…）。
        只在语句上下文里成立：方括号、圆括号、对象字面量内部不会自动补分号；await 的操作数也不算（await 换行后接 {} 仍是对象字面量）。"""
        i = len(self.ctx) - 2
        if not (self.ctx[i] == _JS_B_STAT or i in self.sblock or i in self.sctx): return False
        if self.prev == 'name' and self.prev_text in ('of', 'await') and self.operand_kw: return False     # for…of 与 await 的操作数是对象字面量，即使 await 后面换了行
        if self.prev == '}': return True                 # 语句块、函数或类的声明体的右花括号之后，花括号只能开始新语句
        if self.prev not in ('name', 'num', 'str', 'regexp', 'backquote', ']', '++', '--'): return False
        return _JS_LINE_BREAK_RE.search(self.s, self.prev_end, p) is not None

    def _slash_regex(self, p):
        """解析器需要一个表达式、却读到除号时，acorn 会退回去把它重读成正则（parseExprAtom 开头），V8 也是这样切分的。
        合法代码里这只发生在上一条语句已经结束、接下来是一条新语句的时候：if/for/while/with 的条件之后、
        函数或类的声明体之后、import / from 引入的模块路径之后（必须隔着换行：同一行里紧跟在 from 后面的字符串，只能是把 from 当名字用的另一条语句），以及靠换行省略分号的 break / continue / debugger 之后。await 的操作数另由 exprAllowed 处理。"""
        prev = self.prev
        if prev == 'name' and self.prev_text == 'yield' and self.yield_op and self._yield_regex_ok(): return True
        if self.label_break or prev in ('break', 'continue', 'debugger'):
            return _JS_LINE_BREAK_RE.search(self.s, self.prev_end, p) is not None
        if prev == 'str' and self.str_import:
            return _JS_LINE_BREAK_RE.search(self.s, self.prev_end, p) is not None      # 模块路径之后换了行才是新语句；同一行里紧跟字符串的斜杠是除号（from 也可能是普通标识符：from ⇢ "x"/2）
        return (prev == ')' and self.close_paren_stat) or (prev == '}' and self.close_decl)

    def _in_generator(self):
        for c in reversed(self.ctx):
            if c in _JS_IS_FUNC: return c in _JS_IS_GEN
        return False

    def _brace_is_block(self, p):
        s = self.s; parent = self.ctx[-1]; prev = self.prev
        if parent in _JS_IS_FUNC: return True
        if prev == ':' and parent in (_JS_B_STAT, _JS_B_EXPR):
            return self._in_stmt() and not self.colon_tern    # 语句位置的三目分支 {a: 1}：解析器把它当作对象字面量
        if prev == 'name' and self.prev_text in ('of', 'await') and self.operand_kw: return False     # for…of 与 await 的操作数同样按对象字面量
        if prev == 'return' or (prev == 'name' and self.ea):
            return _JS_LINE_BREAK_RE.search(s, self.prev_end, p) is not None
        if prev == ';' and parent == _JS_P_STAT and len(self.ctx) - 1 in self.pstat_for: return False     # for 头里分号之后是表达式位置，{ 是对象字面量
        if prev in ('else', ';', '=>', ')') or prev == 'eof': return True
        if prev == '{': return self._in_stmt()
        if prev in ('var', 'const', 'name'): return False
        return not self.ea

    def _function_or_class(self, t, p, q):
        s = self.s; prev = self.prev
        if prev in ('.', '?.'):
            self.ea = False; return False        # 属性名里的关键字不压上下文
        lb = _JS_LINE_BREAK_RE.search(s, self.prev_end, p) is not None
        if prev == 'name' and self.prev_text == 'async' and not lb:
            is_expr = True                         # async function：解析器把上下文改为函数表达式
        elif prev == 'name' and self.ea and self.prev_text in ('await', 'yield', 'of'):
            is_expr = True                         # await / yield / for…of 的操作数是表达式：acorn 的分词器在这里压的是声明帧，V8 把后面的斜杠读作除号
        else:
            is_expr = (_js_before_expr(prev) and prev != 'else'
                       and not (prev == ';' and self.ctx[-1] != _JS_P_STAT)
                       and not (prev == 'return' and lb)
                       and not (prev in (':', '{') and self._in_stmt()))
        c = _js_next_char(s, q)
        if t == 'function':
            real = c in ('*', '(') or _JS_IDENT_START_RE.match(c) is not None
        else:
            real = c == '{' or _JS_IDENT_START_RE.match(c) is not None
        if real:
            self._push(_JS_F_EXPR if is_expr else _JS_F_STAT)          # 被当作属性名时解析器会立刻弹出，这里直接不压
            is_async = prev == 'name' and self.prev_text == 'async' and not lb
            self.fasync[len(self.ctx) - 1] = None if t == 'class' else is_async
            # 语句层面的函数 / 类声明后面只能是一条新语句；表达式里的（x = function(){} / 2）则可以接除号
            if not is_expr or prev == 'default' or (prev == ')' and self.close_paren_stat) or (is_async and self.async_stmt):
                self.fdecl.add(len(self.ctx) - 1)
        self.ea = False
        return real

    def _read_string(self, start, q):
        s = self.s; pat = _JS_STR_DQ_RE if q == '"' else _JS_STR_SQ_RE
        p = start + 1
        while True:
            m = pat.search(s, p)
            if m is None: self._fail(start, '字符串未闭合')
            if m.group() == q: break
            if m.group() != '\\': self._fail(m.start(), '字符串未闭合就换行')
            p = m.start() + (3 if s[m.start() + 1:m.start() + 3] == '\r\n' else 2)
        end = m.end(); raw = s[start + 1:end - 1]
        value = raw if '\\' not in raw else _js_unescape(raw, False)
        self._end_str(end)
        return ('str', start, end, q, value)

    def _read_regex(self, start):
        s = self.s; p = start + 1; in_class = False
        while True:
            m = _JS_REGEX_RE.search(s, p)
            if m is None: self._fail(start, '正则字面量未闭合')
            c = m.group()
            if c == '\\': p = m.start() + 2
            elif c == '[': in_class = True; p = m.end()
            elif c == ']': in_class = False; p = m.end()
            elif c == '/':
                p = m.end()
                if not in_class: break
            else: self._fail(m.start(), '正则字面量未闭合就换行')
        p = _JS_FLAGS_RE.match(s, p).end()
        self.prev = 'regexp'; self.prev_text = ''; self.prev_end = self.pos = p; self.ea = False
        return ('re', start, p)

    def _read_template(self, start, code_re):
        s = self.s
        self._push(_JS_Q_TMPL)
        p = start + 1; qs = p; quasis = []; nexpr = 0
        while True:
            m = _JS_TPL_RE.search(s, p)
            if m is None: self._fail(start, '模板字符串未闭合')
            c = m.group()
            if c == '`':
                quasis.append((qs, m.start(), s[qs:m.start()]))
                self.ctx.pop(); self.prev = 'backquote'; self.prev_text = ''
                self.prev_end = self.pos = m.end(); self.ea = False
                return ('tpl', start, m.end(), _js_cooked(quasis[0][2]) if nexpr == 0 else None, nexpr, quasis)
            if c == '$':
                if s[m.start() + 1:m.start() + 2] != '{':
                    p = m.start() + 1; continue
                quasis.append((qs, m.start(), s[qs:m.start()])); nexpr += 1
                self._push(_JS_B_TMPL); self.ea = True
                self.prev = '${'; self.prev_text = ''; self.prev_end = self.pos = m.start() + 2
                self._run(True, code_re)
                p = qs = self.pos
            elif c == '\\':
                p = m.start() + 2
            else:
                p = m.start() + (2 if c == '\r' and s[m.start() + 1:m.start() + 2] == '\n' else 1)

def _js_cooked(raw):
    """模板一段原文的解码值：源码里的换行归一为 \n，转义序列解码；无效转义返回 None。"""
    if '\\' not in raw and '\r' not in raw: return raw
    return _js_unescape(raw.replace('\r\n', '\n').replace('\r', '\n') if '\r' in raw else raw, True)

def _js_string_literals(text):
    """返回 [(类别, 起, 止, 解码值), …]：类别 'str' 为字符串字面量（解码值必为 str），
    'tpl' 为不含 ${} 插值的模板字面量（解码值为 str；含插值或无效转义时为 None）。"""
    return [(t[0], t[1], t[2], t[4] if t[0] == 'str' else t[3]) for t in _JsLex(text).tokens() if t[0] != 're']

def patch_js_text(text, exact_rules, plain_map):
    updated = text
    exact_hits = 0
    for before, after in exact_rules:
        if before in updated and after not in updated:
            exact_hits += updated.count(before)
            updated = updated.replace(before, after)
    plain_hits = 0
    if plain_map and _js_may_hit(updated, plain_map):
        out = []; last = 0
        for kind, start, end, value in _js_string_literals(updated):
            zh = plain_map.get(value) if value is not None else None
            if zh is None: continue
            if GUARD_RE.search(updated[max(0, start - 96):start]): continue
            out.append(updated[last:start]); out.append(_js_quote(zh, updated[start]))
            last = end; plain_hits += 1
        if out:
            out.append(updated[last:]); updated = ''.join(out)
    return updated, exact_hits, plain_hits

# ---------- 4.x：ion-dist.asar 补丁 ----------
def patch_ion_dist(state):
    ion = os.path.join(RESOURCES, 'ion-dist.asar')
    data, header, data_start = asar_open(ion)

    fe_en = json.loads(asar_entry(ion, '/i18n/en-US.json')[0].decode('utf-8'))
    fe_dict = load(os.path.join(LANG, 'linux/dictionary.json'))
    fe_out, translated, fe_fallback = merge_dict(fe_en, fe_dict)
    repl = {}
    add = {'/i18n/zh-CN.json': json_bytes(fe_out)}
    remove = []

    ov = {k: v for k, v in load(os.path.join(LANG, 'linux/overrides.json')).items()
          if k in fe_en and struct_ok(fe_en[k], v)}
    if ov: add['/i18n/zh-CN.overrides.json'] = json_bytes(ov)
    elif asar_find(header, '/i18n/zh-CN.overrides.json') is not None:
        remove.append('/i18n/zh-CN.overrides.json')

    dyn = load(os.path.join(LANG, 'dynamic/zh-CN.json'))
    dyn_node = asar_find(header, '/i18n/dynamic/en-US.json')
    if dyn_node is not None:
        dyn_en = json.loads(asar_entry(ion, '/i18n/dynamic/en-US.json')[0].decode('utf-8'))
        dyn = {k: v for k, v in dyn.items() if k in dyn_en}
    add['/i18n/dynamic/zh-CN.json'] = json_bytes(dyn)

    exact_rules, plain_map = build_js_rules()
    patched_files = 0; exact_hits = 0; plain_hits = 0
    for epath, node in asar_walk(header):
        if not epath.endswith('.js') or node.get('unpacked'): continue
        if not (epath.startswith('/assets/v1/') or epath.startswith('/assets/')): continue
        off = int(node['offset'])
        blob = data[data_start + off:data_start + off + int(node['size'])]
        try:
            text = blob.decode('utf-8')
        except UnicodeDecodeError:
            continue
        updated, eh, ph = patch_js_text(text, exact_rules, plain_map)
        if updated == text: continue
        repl[epath] = updated.encode('utf-8')
        patched_files += 1; exact_hits += eh; plain_hits += ph

    backup_file(state, 'ion-dist.asar')
    p('· 前端词典：%d/%d 键已翻译（%d 键因英文原文变化暂回退英文）' % (translated, len(fe_en), fe_fallback))
    p('· JS 规则：修改 %d 个文件（精确规则 %d 处，文字规则 %d 处）' % (patched_files, exact_hits, plain_hits))
    patched, added, removed = asar_rewrite(ion, repl, add, remove)
    mark_deployed(state, 'ion-dist.asar#zh-CN')  # 仅记录，重置时整档恢复
    return len(fe_en), translated

# ---------- 5.x：frame-shell 词典层（app.asar 内 frame/shell 捆绑包） ----------
FS_MSG_RE = re.compile(
    r'\{\s*(?:(?:id|defaultMessage|description)\s*:\s*"(?:[^"\\]|\\.)*"\s*,\s*){1,2}'
    r'(?:id|defaultMessage|description)\s*:\s*"(?:[^"\\]|\\.)*"\s*\}')
FS_PROP_RE = re.compile(r'\b(id|defaultMessage)\s*:\s*("(?:[^"\\]|\\.)*")')

def frame_shell_en_map(asar, header, data, data_start):
    """从 frame-shell JS 条目提取 {id: defaultMessage} 英文映射。"""
    en = {}
    for epath, node in asar_walk(header):
        if node.get('unpacked'): continue
        if '/resources/frame/shell/' not in epath or not epath.endswith('.js'): continue
        off = int(node['offset'])
        blob = data[data_start + off:data_start + off + int(node['size'])]
        try:
            text = blob.decode('utf-8')
        except UnicodeDecodeError:
            continue
        for m in FS_MSG_RE.finditer(text):
            try:
                props = {pm.group(1): json.loads(pm.group(2)) for pm in FS_PROP_RE.finditer(m.group(0))}
            except Exception:
                continue
            if 'id' in props and 'defaultMessage' in props:
                en[props['id']] = props['defaultMessage']
    return en

def patch_frame_shell(asar, header, data, data_start, repl, add):
    """在 app.asar 内新增 frame-shell zh-CN.json，并同步 shell-manifest.json 与 frame-shell.html 的语言清单。"""
    fs_dir = asar_find(header, '/resources/frame/shell/i18n/frame-shell')
    fs_html = asar_find(header, '/resources/frame/shell/frame-shell.html')
    fs_manifest = asar_find(header, '/resources/frame/shell/shell-manifest.json')
    if fs_dir is None or fs_html is None or fs_manifest is None:
        p('· frame-shell：未找到捆绑包结构，跳过该层')  # 旧版本无此层
        return
    en = frame_shell_en_map(asar, header, data, data_start)
    if not en:
        p('· frame-shell：未能从 JS 提取英文原文，跳过该层')
        return
    dict_path = os.path.join(LANG, 'linux/frame-shell-dictionary.json')
    if not os.path.isfile(dict_path):
        p('· frame-shell：缺少词典文件，跳过该层')
        return
    fs_dict = load(dict_path)
    fs_out, fs_translated, fs_fallback = merge_dict(en, fs_dict)
    fs_blob = json_bytes(fs_out)
    add['/resources/frame/shell/i18n/frame-shell/zh-CN.json'] = fs_blob
    p('· frame-shell 词典：%d/%d 键已翻译（%d 键回退英文）' % (fs_translated, len(en), fs_fallback))

    digest = hashlib.sha256(fs_blob).hexdigest()
    # frame-shell.html：语言清单加入 zh-CN（data-shipped + data-catalogs，带 12 位缓存指纹）
    # 注意：html 被修改后必须同步其在 shell-manifest.json 中的条目，
    # 否则启动时的清单校验（manifest→磁盘逐字节比对）会拒绝整个捆绑包。
    off = int(fs_html['offset'])
    htext = data[data_start + off:data_start + off + int(fs_html['size'])].decode('utf-8')
    htext2 = htext
    html_changed = False
    m1 = re.search(r'data-shipped="([^"]*)"', htext2)
    m2 = re.search(r'data-catalogs="([^"]*)"', htext2)
    zh_cat = 'zh-CN:' + digest[:12]
    if m1 and m2 and (zh_cat not in m2.group(1).split(',') or 'zh-CN' not in m1.group(1).split(',')):
        shipped = [s for s in m1.group(1).split(',') if s] if m1.group(1) else []
        if 'zh-CN' not in shipped:
            shipped.append('zh-CN')
        htext2 = htext2.replace(m1.group(0), 'data-shipped="%s"' % ','.join(shipped), 1)
        m2b = re.search(r'data-catalogs="([^"]*)"', htext2)
        cats = [c for c in m2b.group(1).split(',') if c and not c.startswith('zh-CN:')] if m2b.group(1) else []
        cats.append(zh_cat)
        htext2 = htext2.replace(m2b.group(0), 'data-catalogs="%s"' % ','.join(cats), 1)
        html_changed = True
        p('· frame-shell 语言清单：frame-shell.html 已同步 zh-CN')
    else:
        p('· frame-shell 语言清单：已是最新')
    html_blob = htext2.encode('utf-8')

    # shell-manifest.json：登记新文件并同步被修改文件的条目（服务端按清单逐字节校验并提供文件）
    off = int(fs_manifest['offset'])
    mtext = data[data_start + off:data_start + off + int(fs_manifest['size'])].decode('utf-8')
    manifest = json.loads(mtext)
    manifest_changed = False
    files = manifest.setdefault('files', {})
    key = 'i18n/frame-shell/zh-CN.json'
    if files.get(key, {}).get('sha256') != digest:
        files[key] = {'bytes': len(fs_blob),
                      'contentType': 'application/json; charset=utf-8', 'sha256': digest}
        manifest_changed = True
    if html_changed and files.get('frame-shell.html', {}).get('sha256') != hashlib.sha256(html_blob).hexdigest():
        files['frame-shell.html'] = {'bytes': len(html_blob),
                                     'contentType': files.get('frame-shell.html', {}).get(
                                         'contentType', 'text/html; charset=utf-8'),
                                     'sha256': hashlib.sha256(html_blob).hexdigest()}
        manifest_changed = True
    if manifest_changed:
        repl['/resources/frame/shell/shell-manifest.json'] = \
            json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        p('· frame-shell 清单：shell-manifest.json 已更新（登记 zh-CN.json，同步 frame-shell.html）')
    else:
        p('· frame-shell 清单：已是最新')
    if html_changed:
        repl['/resources/frame/shell/frame-shell.html'] = html_blob

def patch_app_asar(state):
    asar = os.path.join(RESOURCES, 'app.asar')
    data, header, data_start = asar_open(asar)
    repl = {}; add = {}

    # 桌面壳词典：app.asar 内 resources/i18n/<locale>.json
    sh_en_node = asar_find(header, '/resources/i18n/en-US.json')
    if sh_en_node is not None:
        sh_en = json.loads(asar_entry(asar, '/resources/i18n/en-US.json')[0].decode('utf-8'))
        sh_dict = load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
        sh_out, sh_translated, sh_fallback = merge_dict(sh_en, sh_dict)
        add['/resources/i18n/zh-CN.json'] = json_bytes(sh_out)
        p('· 桌面壳词典：%d/%d 键已翻译（%d 键回退英文）' % (sh_translated, len(sh_en), sh_fallback))
    else:
        p('· app.asar 内未找到桌面壳词典 resources/i18n/en-US.json，跳过桌面壳汉化')

    # 桌面语言映射：zh → zh-CN
    if b'id:"id-ID",zh:"zh-CN"}' in data:
        p('· app.asar 桌面语言映射：已打过补丁')
    else:
        target = None; occurrences = 0
        for epath, node in asar_walk(header):
            if node.get('unpacked'): continue
            off = int(node['offset'])
            blob = data[data_start + off:data_start + off + int(node['size'])]
            occurrences += blob.count(b'id:"id-ID"}')
            if b'id:"id-ID"}' in blob and target is None:
                target = (epath, blob)
        if target is None:
            p('· app.asar 中未找到 locale 映射（版本结构可能已变），已跳过；语言仍可从菜单选择')
        elif occurrences != 1:
            p('· app.asar 中 locale 映射出现 %d 次（预期 1 次），为保证安全已跳过' % occurrences)
        else:
            epath, blob = target
            repl[epath] = blob.replace(b'id:"id-ID"}', b'id:"id-ID",zh:"zh-CN"}')
            p('· app.asar 桌面语言映射：将打补丁（zh → zh-CN）')

    patch_frame_shell(asar, header, data, data_start, repl, add)

    if not repl and not add:
        return
    backup_file(state, 'app.asar')
    asar_rewrite(asar, repl, add)

# ---------- 3.x：明文目录补丁（旧版兼容） ----------
def patch_dir3_assets(state):
    assets = os.path.join(RESOURCES, 'ion-dist/assets/v1')
    if not os.path.isdir(assets):
        p('· 未找到前端资源目录，跳过 JS 规则'); return
    exact_rules, plain_map = build_js_rules()
    quote_patterns = []
    for q in ('"', "'", '`'):
        qq = re.escape(q)
        quote_patterns.append((q, re.compile(qq + r'((?:\\.|[^' + qq + r'\\])*)' + qq)))
    names = os.listdir(assets)
    files = sorted(f for f in names if f.endswith('.js'))
    zst = [f for f in names if f.endswith('.js.zst')]
    if zst:
        p('· 注意：发现 %d 个 .js.zst 文件，其中内容未打补丁' % len(zst))
    patched_files = 0; exact_hits = 0; plain_hits = 0
    for name in files:
        path = os.path.join(assets, name)
        with open(path, encoding='utf-8') as f: text = f.read()
        updated, eh, ph = patch_js_text(text, exact_rules, plain_map)
        if updated == text: continue
        rel = 'ion-dist/assets/v1/' + name
        backup_file(state, rel)
        with open(path, 'w', encoding='utf-8') as f: f.write(updated)
        patched_files += 1; exact_hits += eh; plain_hits += ph
    p('· JS 规则：修改 %d 个文件（精确规则 %d 处，文字规则 %d 处）' % (patched_files, exact_hits, plain_hits))

def patch_asar_locale_only(state):
    """3.x 布局的 app.asar 语言映射补丁（原样保留旧逻辑）。"""
    asar = os.path.join(RESOURCES, 'app.asar')
    data = open(asar, 'rb').read()
    json_len = int.from_bytes(data[12:16], 'little')
    header = json.loads(data[16:16 + json_len].decode('utf-8'))
    data_start = 8 + int.from_bytes(data[4:8], 'little')
    if b'id:"id-ID",zh:"zh-CN"}' in data:
        p('· app.asar 桌面语言映射：已打过补丁'); return
    entries = []
    def walk(node):
        if isinstance(node, dict) and 'files' in node:
            for c in node['files'].values(): walk(c)
            return
        if isinstance(node, dict) and 'size' in node and 'offset' in node:
            entries.append((node, int(node['offset']), int(node['size'])))
    walk(header)
    target = None; occurrences = 0
    for node, off, size in entries:
        blob = data[data_start + off: data_start + off + size]
        occurrences += blob.count(b'id:"id-ID"}')
        if b'id:"id-ID"}' in blob and target is None:
            target = (node, blob)
    if target is None:
        p('· app.asar 中未找到 locale 映射（版本结构可能已变），已跳过；语言仍可从菜单选择'); return
    if occurrences != 1:
        p('· app.asar 中 locale 映射出现 %d 次（预期 1 次），为保证安全已跳过' % occurrences); return
    node, blob = target
    patched = blob.replace(b'id:"id-ID"}', b'id:"id-ID",zh:"zh-CN"}')

    out = bytearray()
    seen = {}
    for n, off, size in entries:
        if n is node:
            n['size'] = len(patched)
            n['offset'] = str(len(out))
            if isinstance(n.get('integrity'), dict):
                integ = n['integrity']
                bs = int(integ.get('blockSize', 4194304))
                integ['hash'] = hashlib.sha256(patched).hexdigest()
                integ['blocks'] = [hashlib.sha256(patched[i:i + bs]).hexdigest()
                                   for i in range(0, len(patched), bs)]
            out += patched
            continue
        key = (off, size)
        if key in seen:
            n['offset'] = str(seen[key]); continue
        n['offset'] = str(len(out))
        seen[key] = len(out)
        out += data[data_start + off: data_start + off + size]
    hb = json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    pad = (-(len(hb) + 5)) % 4
    size8 = len(hb) + 5 + pad
    new = struct.pack('<4I', 4, size8 + 4, size8, len(hb)) + hb + b'\x00' + b'\x00' * pad + out
    new_data_start = 8 + size8 + 4

    jlen = int.from_bytes(new[12:16], 'little')
    hdr2 = json.loads(new[16:16 + jlen].decode('utf-8'))
    hits = [0]; total = [0]; hash_bad = [0]
    def walk2(n):
        if isinstance(n, dict) and 'files' in n:
            for c in n['files'].values(): walk2(c)
        elif isinstance(n, dict) and 'offset' in n:
            total[0] += 1
            start = new_data_start + int(n['offset'])
            blob = new[start:start + int(n['size'])]
            if b'id:"id-ID",zh:"zh-CN"}' in blob: hits[0] += 1
            if isinstance(n.get('integrity'), dict) and n['integrity'].get('hash'):
                if hashlib.sha256(blob).hexdigest() != n['integrity']['hash']:
                    hash_bad[0] += 1
    walk2(hdr2)
    if total[0] != len(entries) or hits[0] != 1 or hash_bad[0]:
        raise RuntimeError('asar 重建自检失败（条目 %d/%d，命中 %d，hash 错误 %d）'
                           % (total[0], len(entries), hits[0], hash_bad[0]))
    backup_file(state, 'app.asar')
    tmp = asar + '.zh-tmp'
    with open(tmp, 'wb') as f: f.write(new)
    os.replace(tmp, asar)
    p('· app.asar 桌面语言映射：已打补丁（zh → zh-CN）')

def do_install_dir3(state):
    # 四层中文资源（明文目录版）
    fe_en = load(os.path.join(RESOURCES, 'ion-dist/i18n/en-US.json'))
    fe_dict = load(os.path.join(LANG, 'linux/dictionary.json'))
    fe_out, translated, fe_fallback = merge_dict(fe_en, fe_dict)
    backup_file(state, 'ion-dist/i18n/zh-CN.json')
    write_json_atomic(os.path.join(RESOURCES, 'ion-dist/i18n/zh-CN.json'), fe_out)
    mark_deployed(state, 'ion-dist/i18n/zh-CN.json')
    save_state(state)

    ov = {k: v for k, v in load(os.path.join(LANG, 'linux/overrides.json')).items()
          if k in fe_en and struct_ok(fe_en[k], v)}
    ov_path = os.path.join(RESOURCES, 'ion-dist/i18n/zh-CN.overrides.json')
    if ov:
        write_json_atomic(ov_path, ov)
        mark_deployed(state, 'ion-dist/i18n/zh-CN.overrides.json')
    elif os.path.exists(ov_path):
        os.remove(ov_path)

    dyn = load(os.path.join(LANG, 'dynamic/zh-CN.json'))
    dyn_en_path = os.path.join(RESOURCES, 'ion-dist/i18n/dynamic/en-US.json')
    if os.path.exists(dyn_en_path):
        dyn_en = load(dyn_en_path)
        dyn = {k: v for k, v in dyn.items() if k in dyn_en}
    write_json_atomic(os.path.join(RESOURCES, 'ion-dist/i18n/dynamic/zh-CN.json'), dyn)
    mark_deployed(state, 'ion-dist/i18n/dynamic/zh-CN.json')

    sh_en_path = os.path.join(RESOURCES, 'en-US.json')
    if os.path.exists(sh_en_path):
        sh_en = load(sh_en_path)
        sh_dict = load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
        sh_out, sh_translated, sh_fallback = merge_dict(sh_en, sh_dict)
        backup_file(state, 'zh-CN.json')
        write_json_atomic(os.path.join(RESOURCES, 'zh-CN.json'), sh_out)
        mark_deployed(state, 'zh-CN.json')
        p('· 桌面壳词典：%d/%d 键已翻译（%d 键回退英文）' % (sh_translated, len(sh_en), sh_fallback))
    save_state(state)

    p('· 前端词典：%d/%d 键已翻译（%d 键因英文原文变化暂回退英文）' % (translated, len(fe_en), fe_fallback))
    patch_dir3_assets(state)
    save_state(state)
    try:
        patch_asar_locale_only(state)
    except Exception as e:
        p('· app.asar 补丁出错（%s），已跳过，不影响其余汉化' % e)
    save_state(state)

# ---------- install / reset / check ----------
def do_install():
    layout = detect_layout()
    version = detect_version(layout)
    os.makedirs(BACKUP, exist_ok=True)
    state = read_state()
    old_version = ''
    if os.path.exists(VERSION_PATH):
        with open(VERSION_PATH, encoding='utf-8') as f: old_version = f.read().strip()
    if old_version and old_version != version:
        p('· 检测到 Claude 已更新（%s → %s）：清除旧备份，按当前版本重新打补丁' % (old_version, version))
        shutil.rmtree(BACKUP, ignore_errors=True)
        os.makedirs(BACKUP, exist_ok=True)
        state = {'backups': [], 'deployed': []}
    if old_version != version:
        with open(VERSION_PATH, 'w', encoding='utf-8') as f: f.write(version)

    if layout == 'asar4':
        patch_ion_dist(state)
        save_state(state)
        patch_app_asar(state)
    else:
        do_install_dir3(state)

    save_state(state)
    p('')
    p('✔ 汉化完成。启动 Claude，从头像/用户菜单进入“语言”，选择“简体中文”。')

def do_reset():
    state = read_state()
    if not state['backups'] and not state['deployed']:
        p('· 没有可恢复的内容（尚未安装过汉化）'); return
    for rel in state['backups']:
        src = os.path.join(BACKUP, rel)
        dst = os.path.join(RESOURCES, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            p('· 已恢复 %s' % rel)
    for rel in state['deployed']:
        if rel in state['backups'] or '#' in rel: continue  # asar 内部部署项随整档恢复
        dst = os.path.join(RESOURCES, rel)
        if os.path.isfile(dst):
            os.remove(dst)
            p('· 已移除 %s' % rel)
    for f in (MANIFEST_PATH, VERSION_PATH):
        if os.path.exists(f): os.remove(f)
    shutil.rmtree(BACKUP, ignore_errors=True)
    p('✔ 已恢复英文原版。')

def do_check():
    layout = detect_layout()
    version = detect_version(layout)
    p('· 资源目录: %s' % RESOURCES)
    p('· 布局: %s' % ('4.x（ion-dist.asar）' if layout == 'asar4' else '3.x（明文目录）'))
    p('· 当前版本: %s' % version)
    if layout == 'asar4':
        ion = os.path.join(RESOURCES, 'ion-dist.asar')
        node = asar_find(asar_open(ion)[1], '/i18n/zh-CN.json')
        if node is not None:
            blob = asar_entry(ion, '/i18n/zh-CN.json')[0]
            p('· 前端 zh-CN.json: 已部署（%d 键）' % len(json.loads(blob.decode('utf-8'))))
        else:
            p('· 前端 zh-CN.json: 未部署')
        data, header, data_start = asar_open(ion)
        whitelist = False; namemap = False
        for epath, n in asar_walk(header):
            if whitelist and namemap: break
            if not epath.endswith('.js') or n.get('unpacked'): continue
            off = int(n['offset'])
            blob = data[data_start + off:data_start + off + int(n['size'])]
            if b'["en-US","zh-CN","de-DE"' in blob: whitelist = True
            if b'"zh-CN":{name:"Chinese (Simplified)"' in blob: namemap = True
        p('· 前端语言白名单: %s' % ('已加入 zh-CN' if whitelist else '未打补丁'))
        p('· 前端语言名称映射: %s' % ('已加入 zh-CN' if namemap else '未打补丁'))
        asar = os.path.join(RESOURCES, 'app.asar')
        adata = open(asar, 'rb').read()
        p('· app.asar 语言映射: %s' % ('已打补丁' if b'id:"id-ID",zh:"zh-CN"}' in adata else '未打补丁'))
        sh = asar_find(asar_open(asar)[1], '/resources/i18n/zh-CN.json')
        if sh is not None:
            blob = asar_entry(asar, '/resources/i18n/zh-CN.json')[0]
            p('· 桌面壳 zh-CN.json: 已部署（%d 键）' % len(json.loads(blob.decode('utf-8'))))
        else:
            p('· 桌面壳 zh-CN.json: 未部署')
        fs = asar_find(asar_open(asar)[1], '/resources/frame/shell/i18n/frame-shell/zh-CN.json')
        if fs is not None:
            blob = asar_entry(asar, '/resources/frame/shell/i18n/frame-shell/zh-CN.json')[0]
            p('· frame-shell zh-CN.json: 已部署（%d 键）' % len(json.loads(blob.decode('utf-8'))))
        else:
            p('· frame-shell zh-CN.json: 未部署')
    else:
        fe = os.path.join(RESOURCES, 'ion-dist/i18n/zh-CN.json')
        if os.path.exists(fe):
            p('· 前端 zh-CN.json: 已部署（%d 键）' % len(load(fe)))
        else:
            p('· 前端 zh-CN.json: 未部署')
        sh = os.path.join(RESOURCES, 'zh-CN.json')
        if os.path.exists(sh):
            p('· 桌面壳 zh-CN.json: 已部署（%d 键）' % len(load(sh)))
        else:
            p('· 桌面壳 zh-CN.json: 未部署')
        whitelist = False
        assets = os.path.join(RESOURCES, 'ion-dist/assets/v1')
        if os.path.isdir(assets):
            for name in os.listdir(assets):
                if not name.endswith('.js'): continue
                try:
                    with open(os.path.join(assets, name), encoding='utf-8') as f: t = f.read()
                except Exception: continue
                if '["en-US","zh-CN","de-DE"' in t:
                    whitelist = True; break
        p('· 前端语言白名单: %s' % ('已加入 zh-CN' if whitelist else '未打补丁'))
        with open(os.path.join(RESOURCES, 'app.asar'), 'rb') as f: blob = f.read()
        p('· app.asar 语言映射: %s' % ('已打补丁' if b'id:"id-ID",zh:"zh-CN"}' in blob else '未打补丁'))
    if os.path.exists(VERSION_PATH):
        with open(VERSION_PATH, encoding='utf-8') as f: v = f.read().strip()
        p('· 补丁记录版本: %s%s' % (v, '（与当前一致）' if v == version else '（与当前不同，建议重跑 install）'))

def set_locale(path):
    """把用户 config.json 的 locale 写为 zh-CN（保留其余配置项）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg = {}
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f: cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg['locale'] = 'zh-CN'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

if MODE in ('install', 'reset', 'check') and not (RESOURCES and BACKUP and LANG):
    raise SystemExit('缺少环境变量 ZH_RESOURCES / ZH_BACKUP / ZH_LANG（正常使用请运行 install-linux.sh）')
if MODE == 'install': do_install()
elif MODE == 'reset': do_reset()
elif MODE == 'check': do_check()
elif MODE == 'set-locale':
    if len(sys.argv) < 3: raise SystemExit('set-locale 需要 config.json 路径参数')
    set_locale(sys.argv[2])
else: raise SystemExit('未知模式: ' + MODE)
