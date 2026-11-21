#!/usr/bin/env python3
# 5.x/6.x 同步脚本公共助手：路径解析、最新解包版本自动探测、ICU MessageFormat 结构校验
import glob, json, os, re

WORK = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WORK)
LANG = os.path.join(ROOT, 'language/zh-CN')

def ver_key(v):
    return [int(p) if p.isdigit() else p for p in re.split(r'[._-]', v)]

def detect_versions():
    vers = set()
    for prefix in ('ion-i18n-', 'deb-', 'app-i18n-', 'app-frame-shell-'):
        for p in glob.glob(os.path.join(WORK, prefix + '*')):
            v = os.path.basename(p)[len(prefix):]
            if re.match(r'^\d+\.', v):
                vers.add(v)
    for p in glob.glob(os.path.join(WORK, 'frame-shell-en-*.json')):
        v = os.path.basename(p)[len('frame-shell-en-'):-len('.json')]
        if re.match(r'^\d+\.', v):
            vers.add(v)
    return sorted(vers, key=ver_key)

def current_ver():
    env = os.environ.get('CLAUDE_VER', '').strip()
    if env:
        return env
    vers = detect_versions()
    if not vers:
        raise SystemExit('未在 zh-i18n/work/ 下检测到解包版本，请先运行 python3 zh-i18n/work/unpack-deb.py')
    return vers[-1]

def prev_ver(cur=None):
    env = os.environ.get('CLAUDE_OLD_VER', '').strip()
    if env:
        return env
    cur = cur or current_ver()
    vers = [v for v in detect_versions() if v != cur]
    return vers[-1] if vers else ''

def paths_for(ver=None):
    v = ver or current_ver()
    return {
        'ver': v,
        'deb_dir': os.path.join(WORK, f'deb-{v}'),
        'deb_res': os.path.join(WORK, f'deb-{v}/usr/lib/claude-desktop/resources'),
        'ion_i18n': os.path.join(WORK, f'ion-i18n-{v}/i18n'),
        'app_i18n': os.path.join(WORK, f'app-i18n-{v}/resources/i18n'),
        'app_fs': os.path.join(WORK, f'app-frame-shell-{v}/resources/frame/shell'),
        'fs_en': os.path.join(WORK, f'frame-shell-en-{v}.json'),
    }

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def dump(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

# ---------- ICU MessageFormat 结构校验（兼容中文官方 zh-Hans 复数简化写法） ----------
_TAG_RE = re.compile(r'</?[A-Za-z][A-Za-z0-9_.-]*(?:\s*/)?\s*>')

def _parse_icu_block(s, start):
    n = len(s)
    i = start + 1
    while i < n and s[i].isspace():
        i += 1
    m_var = re.match(r'[A-Za-z_][A-Za-z0-9_.-]*', s[i:])
    if not m_var:
        return None
    var = m_var.group(0)
    i += len(var)
    while i < n and s[i].isspace():
        i += 1
    if i >= n:
        return None
    if s[i] == '}':
        return i + 1, {'var': var, 'kind': 'plain', 'branches': {}}
    if s[i] != ',':
        return None
    i += 1
    while i < n and s[i].isspace():
        i += 1
    m_type = re.match(r'[A-Za-z_][A-Za-z0-9_.-]*', s[i:])
    if not m_type:
        return None
    ftype = m_type.group(0)
    i += len(ftype)
    while i < n and s[i].isspace():
        i += 1
    if ftype not in ('plural', 'selectordinal', 'select'):
        depth = 1
        in_q = False
        while i < n and depth > 0:
            ch = s[i]
            if ch == "'":
                if i + 1 < n and s[i + 1] == "'":
                    i += 2; continue
                elif not in_q and i + 1 < n and s[i + 1] in '{}#':
                    in_q = True
                elif in_q:
                    in_q = False
            elif not in_q:
                if ch == '{': depth += 1
                elif ch == '}': depth -= 1
            i += 1
        if depth != 0:
            return None
        return i, {'var': var, 'kind': ftype, 'branches': {}}

    if i >= n or s[i] != ',':
        return None
    i += 1
    branches = {}
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            return None
        if s[i] == '}':
            return i + 1, {'var': var, 'kind': ftype, 'branches': branches}
        if ftype in ('plural', 'selectordinal') and s[i:].startswith('offset:'):
            m_off = re.match(r'offset:\s*-?\d+', s[i:])
            if not m_off:
                return None
            i += len(m_off.group(0))
            continue
        m_key = re.match(r'[^\s{}]+', s[i:])
        if not m_key:
            return None
        bkey = m_key.group(0)
        i += len(bkey)
        while i < n and s[i].isspace():
            i += 1
        if i >= n or s[i] != '{':
            return None
        bstart = i + 1
        depth = 1
        j = bstart
        in_q = False
        while j < n and depth > 0:
            ch = s[j]
            if ch == "'":
                if j + 1 < n and s[j + 1] == "'":
                    j += 2; continue
                elif not in_q and j + 1 < n and s[j + 1] in '{}#<>':
                    in_q = True
                elif in_q:
                    in_q = False
            elif not in_q:
                if ch == '{': depth += 1
                elif ch == '}': depth -= 1
            j += 1
        if depth != 0:
            return None
        branches[bkey] = s[bstart:j - 1]
        i = j
    return None

def _tags_balanced(tag_list):
    stack = []
    for t in tag_list:
        if t.endswith('/>'):
            continue
        if t.startswith('</'):
            name = t[2:-1].strip()
            if not stack or stack[-1] != name:
                return False
            stack.pop()
        else:
            name = t[1:-1].strip()
            stack.append(name)
    return not stack

def _parse_icu_meta(text):
    s = str(text)
    all_vars = set()
    non_plural_vars = set()
    plural_vars = {}
    select_vars = {}
    all_tags = []

    def walk(sub):
        n = len(sub)
        i = 0
        in_q = False
        plain_buf = []
        branch_tags = []
        while i < n:
            ch = sub[i]
            if ch == "'":
                if i + 1 < n and sub[i + 1] == "'":
                    plain_buf.append("'")
                    i += 2; continue
                elif not in_q and i + 1 < n and sub[i + 1] in '{}#<>':
                    in_q = True; i += 1; continue
                elif in_q:
                    in_q = False; i += 1; continue
            if not in_q and ch == '{':
                res = _parse_icu_block(sub, i)
                if res is None:
                    return False
                end_i, info = res
                v, k = info['var'], info['kind']
                all_vars.add(v)
                if k in ('plural', 'selectordinal'):
                    if 'other' not in info['branches']:
                        return False
                    plural_vars.setdefault(v, set()).update(info['branches'].keys())
                    for btext in info['branches'].values():
                        if not walk(btext):
                            return False
                elif k == 'select':
                    if 'other' not in info['branches']:
                        return False
                    non_plural_vars.add(v)
                    select_vars.setdefault(v, set()).update(info['branches'].keys())
                    for btext in info['branches'].values():
                        if not walk(btext):
                            return False
                else:
                    non_plural_vars.add(v)
                i = end_i
                continue
            if not in_q and ch == '}':
                return False
            plain_buf.append(ch)
            i += 1
        joined = ''.join(plain_buf)
        for t in _TAG_RE.findall(joined):
            all_tags.append(t)
            branch_tags.append(t)
        return True

    ok = walk(s)
    return all_vars, non_plural_vars, plural_vars, select_vars, all_tags, ok

def strip_icu(value):
    s = str(value); res = ''; i = 0
    while i < len(s):
        if s[i] == '{':
            depth = 0; j = i
            while j < len(s):
                if s[j] == '{': depth += 1
                elif s[j] == '}':
                    depth -= 1
                    if depth == 0: break
                j += 1
            if j < len(s) and re.match(r'^[A-Za-z_][A-Za-z0-9_.-]*,\s*(plural|selectordinal|select)\s*,', s[i+1:j]):
                res += '{__ICU__}'; i = j + 1; continue
        res += s[i]; i += 1
    return res

def tokens(value):
    c = {}; st = strip_icu(value)
    for t in re.findall(r'<[^>]*>|\{[A-Za-z_][A-Za-z0-9_.-]*\}', st):
        c[t] = c.get(t, 0) + 1
    return c

def struct_ok(en, zh):
    """ICU MessageFormat 结构校验：支持中文复数省略 one 分支或直写 {var}，同时严格校验变量名、select 分支和富文本标签。"""
    en_vars, en_np, en_pl, en_sel, en_tags, en_ok = _parse_icu_meta(en)
    zh_vars, zh_np, zh_pl, zh_sel, zh_tags, zh_ok = _parse_icu_meta(zh)
    if not en_ok:
        a, b = str(en), str(zh)
        return (a.count('{') == b.count('{') and a.count('}') == b.count('}')
                and sorted(re.findall(r'<[^>]*>', a)) == sorted(re.findall(r'<[^>]*>', b)))
    if not zh_ok:
        return False
    if not zh_vars.issubset(en_vars):
        return False
    if not en_np.issubset(zh_vars):
        return False
    if set(zh_sel.keys()) != set(en_sel.keys()):
        return False
    for v, keys in en_sel.items():
        if zh_sel[v] != keys:
            return False
    for v, keys in en_pl.items():
        if v in zh_pl:
            if '=0' in keys and '=0' not in zh_pl[v]:
                return False
            if not zh_pl[v].issubset(keys | {'other', 'one', 'zero', '=0', '=1'}):
                return False
        elif v in zh_vars:
            if '=0' in keys:
                return False
        else:
            if '#' in str(en) or '=0' in keys:
                return False
    if set(zh_tags) != set(en_tags):
        return False
    if _tags_balanced(en_tags) and not _tags_balanced(zh_tags):
        return False
    if not en_pl and not en_sel:
        if sorted(en_tags) != sorted(zh_tags):
            return False
    return True
