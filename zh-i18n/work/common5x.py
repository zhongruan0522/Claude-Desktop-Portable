#!/usr/bin/env python3
# 5.x 同步脚本公共助手：路径解析、最新解包版本自动探测、ICU 结构校验
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
    a, b = str(en), str(zh)
    if a.count('{') != b.count('{') or a.count('}') != b.count('}'): return False
    if sorted(re.findall(r'<[^>]*>', a)) != sorted(re.findall(r'<[^>]*>', b)): return False
    if tokens(a) != tokens(b): return False
    return True
