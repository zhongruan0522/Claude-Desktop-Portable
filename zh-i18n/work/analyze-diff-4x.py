#!/usr/bin/env python3
# 4.x 结构差异分析: en-US 从 asar 提取物读取, 词典层保持原位
import json, os, re

BASE = '/workspace/Claude Desktop/zh-i18n'
ION = os.path.join(BASE, 'work/ion-i18n-4.23118/i18n')      # ion-dist.asar 提取
APP = os.path.join(BASE, 'work/app-i18n-4.23118/resources/i18n')  # app.asar 提取
LANG = os.path.join(BASE, 'language/zh-CN')
OUT = os.path.join(BASE, 'work/diff-report-4x.json')

def load(p):
    with open(p, encoding='utf-8') as f: return json.load(f)

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

def _tokens(value):
    c = {}; st = strip_icu(value)
    for t in re.findall(r'<[^>]*>|\{[A-Za-z_][A-Za-z0-9_.-]*\}', st): c[t] = c.get(t, 0) + 1
    return c

def struct_ok(en, zh):
    a, b = str(en), str(zh)
    if a.count('{') != b.count('{') or a.count('}') != b.count('}'): return False
    if sorted(re.findall(r'<[^>]*>', a)) != sorted(re.findall(r'<[^>]*>', b)): return False
    if _tokens(a) != _tokens(b): return False
    return True

def compare(name, en_path, dict_path):
    en = load(en_path)
    zh = load(dict_path) if os.path.exists(dict_path) else {}
    dead = sorted(k for k in zh if k not in en)
    missing = sorted(k for k in en if k not in zh)
    struct_fail = {}
    zh_eq_en = []
    for k in en:
        if k in zh:
            if zh[k] == en[k]: zh_eq_en.append(k)
            elif not struct_ok(en[k], zh[k]): struct_fail[k] = {'en': en[k], 'zh': zh[k]}
    rep = {'name': name, 'en_keys': len(en), 'dict_keys': len(zh),
           'dead': dead, 'missing': missing, 'struct_fail': struct_fail, 'zh_eq_en': zh_eq_en}
    print('== %s ==' % name)
    print('  en=%d dict=%d dead=%d missing=%d struct_fail=%d zh==en=%d'
          % (len(en), len(zh), len(dead), len(missing), len(struct_fail), len(zh_eq_en)))
    return rep

fe = compare('frontend', os.path.join(ION, 'en-US.json'), os.path.join(LANG, 'linux/dictionary.json'))
shell = compare('desktop-shell', os.path.join(APP, 'en-US.json'), os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
dyn = compare('dynamic', os.path.join(ION, 'dynamic/en-US.json'), os.path.join(LANG, 'dynamic/zh-CN.json'))
ov = load(os.path.join(LANG, 'linux/overrides.json'))
ov_en = load(os.path.join(ION, 'en-US.json'))
ov_dead = sorted(k for k in ov if k not in ov_en)
print('== overrides ==\n  keys=%d dead=%d' % (len(ov), len(ov_dead)))

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump({'frontend': fe, 'desktop_shell': shell, 'dynamic': dyn, 'overrides_dead': ov_dead},
              f, ensure_ascii=False, indent=1)
print('report ->', OUT)
