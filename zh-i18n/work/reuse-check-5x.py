#!/usr/bin/env python3
# 统计各层新增键在 Windows 词典 / 官方壳 zh-Hans 的可复用覆盖
import json, re, os

ROOT = '/workspace/Claude Desktop/zh-i18n'
WIN = json.load(open(ROOT + '/language/zh-CN/zh-CN.json', encoding='utf-8'))
WIN_OV = json.load(open(ROOT + '/language/zh-CN/zh-CN.overrides.json', encoding='utf-8'))
REP = json.load(open(ROOT + '/work/diff-report-5x.json', encoding='utf-8'))

FE_EN = json.load(open(ROOT + '/work/ion-i18n-5.1231.2/i18n/en-US.json', encoding='utf-8'))
SH_EN = json.load(open(ROOT + '/work/app-i18n-5.1231.2/resources/i18n/en-US.json', encoding='utf-8'))
FS_EN = json.load(open(ROOT + '/work/frame-shell-en-5x.json', encoding='utf-8'))
ZH_OFF = json.load(open(ROOT + '/work/app-i18n-5.1231.2/resources/i18n/zh-Hans.json', encoding='utf-8'))

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

def reuse_pool(keys, en_map):
    pool = {}
    for src_name, src in (('win', WIN), ('win_ov', WIN_OV)):
        for k in keys:
            if k in src and k in en_map and src[k] != en_map[k] and struct_ok(en_map[k], src[k]):
                pool.setdefault(k, ('win' if src_name == 'win' else 'win_ov', src[k]))
    return pool

fe_keys = REP['frontend']['missing']
sh_keys = [k for k in REP['desktop_shell']['missing'] if k not in ZH_OFF or ZH_OFF[k] == SH_EN[k]]
fs_keys = list(FS_EN)

for name, keys, en_map in (('frontend', fe_keys, FE_EN), ('shell(rest)', sh_keys, SH_EN), ('frame-shell', fs_keys, FS_EN)):
    pool = reuse_pool(keys, en_map)
    print('%s: %d 键, Windows 可复用 %d (%.1f%%)' % (name, len(keys), len(pool), 100 * len(pool) / max(1, len(keys))))

# shell: 官方 zh-Hans 有效条目
valid_off = {k: v for k, v in ZH_OFF.items() if k in SH_EN and v != SH_EN[k] and struct_ok(SH_EN[k], v)}
print('official shell zh-Hans valid:', len(valid_off))
json.dump(valid_off, open(ROOT + '/work/official-shell-zh-5x.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

# 生成复用文件
fe_pool = reuse_pool(fe_keys, FE_EN)
json.dump({k: v[1] for k, v in fe_pool.items()}, open(ROOT + '/work/reuse-win-5x.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
sh_pool = reuse_pool(sh_keys, SH_EN)
json.dump({k: v[1] for k, v in sh_pool.items()}, open(ROOT + '/work/reuse-win-shell-5x.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
fs_pool = reuse_pool(fs_keys, FS_EN)
json.dump({k: v[1] for k, v in fs_pool.items()}, open(ROOT + '/work/reuse-win-fs-5x.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('written reuse files')
