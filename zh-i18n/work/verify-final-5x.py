#!/usr/bin/env python3
# 最终校验: 三层词典 vs 5.x en-US + overrides 死键
import json, re, os

ROOT = '/workspace/Claude Desktop/zh-i18n'

def load(p): return json.load(open(p, encoding='utf-8'))

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

def check(name, en_map, dict_path):
    zh = load(dict_path)
    missing = [k for k in en_map if k not in zh]
    dead = [k for k in zh if k not in en_map]
    fail = [k for k in en_map if k in zh and zh[k] != en_map[k] and not struct_ok(en_map[k], zh[k])]
    eq = [k for k in en_map if k in zh and zh[k] == en_map[k]]
    print('%s: en=%d dict=%d 未译=%d 死键=%d 结构失败=%d 与英文相同=%d'
          % (name, len(en_map), len(zh), len(missing), len(dead), len(fail), len(eq)))
    if missing[:5]: print('  未译样例:', missing[:5])
    return missing, fail

FE_EN = load(ROOT + '/work/ion-i18n-5.1231.2/i18n/en-US.json')
SH_EN = load(ROOT + '/work/app-i18n-5.1231.2/resources/i18n/en-US.json')
FS_EN = load(ROOT + '/work/frame-shell-en-5x.json')

check('前端', FE_EN, ROOT + '/language/zh-CN/linux/dictionary.json')
m_sh, f_sh = check('桌面壳', SH_EN, ROOT + '/language/zh-CN/linux/desktop-shell-dictionary.json')
check('frame-shell', FS_EN, ROOT + '/language/zh-CN/linux/frame-shell-dictionary.json')

ov = load(ROOT + '/language/zh-CN/linux/overrides.json')
ov_dead = [k for k in ov if k not in FE_EN]
print('overrides: %d 键, 死键 %d' % (len(ov), len(ov_dead)))
dyn = load(ROOT + '/work/ion-i18n-5.1231.2/i18n/dynamic/en-US.json')
dyn_zh = load(ROOT + '/language/zh-CN/dynamic/zh-CN.json')
d_missing = [k for k in dyn if k not in dyn_zh]
d_dead = [k for k in dyn_zh if k not in dyn]
d_fail = [k for k in dyn if k in dyn_zh and dyn_zh[k] != dyn[k] and not struct_ok(dyn[k], dyn_zh[k])]
print('dynamic: en=%d zh=%d 未译=%d 死键=%d 结构失败=%d' % (len(dyn), len(dyn_zh), len(d_missing), len(d_dead), len(d_fail)))

# 桌面壳缺失键明细（若有）
if m_sh:
    print('桌面壳未译 %d 键:' % len(m_sh))
    for k in m_sh[:15]: print('  ', k, '=', SH_EN[k][:60])
