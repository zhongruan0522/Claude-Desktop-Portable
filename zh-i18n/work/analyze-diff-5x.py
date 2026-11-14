#!/usr/bin/env python3
# 5.x 结构差异分析: en-US 从 asar 提取物读取, 词典层保持原位
# 另输出: 英文原文变更键、官方壳 zh-Hans 可复用项、frame-shell 新词典层键数
import json, os, re

BASE = '/workspace/Claude Desktop/zh-i18n'
ION_OLD = os.path.join(BASE, 'work/ion-i18n-5.1231.2/i18n')
ION_NEW = os.path.join(BASE, 'work/ion-i18n-5.11492.5/i18n')
APP_OLD = os.path.join(BASE, 'work/app-i18n-5.1231.2/resources/i18n')
APP_NEW = os.path.join(BASE, 'work/app-i18n-5.11492.5/resources/i18n')
FRAME   = os.path.join(BASE, 'work/app-frame-shell-5.11492.5/resources/frame/shell/i18n/frame-shell')
LANG = os.path.join(BASE, 'language/zh-CN')
OUT = os.path.join(BASE, 'work/diff-report-5x.json')

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

def compare(name, en_new, en_old, dict_path):
    en = load(en_new)
    old = load(en_old) if os.path.exists(en_old) else {}
    zh = load(dict_path) if os.path.exists(dict_path) else {}
    dead = sorted(k for k in zh if k not in en)
    missing = sorted(k for k in en if k not in zh)
    changed = sorted(k for k in en if k in old and en[k] != old[k])
    struct_fail = {}
    zh_eq_en = []
    for k in en:
        if k in zh:
            if zh[k] == en[k]: zh_eq_en.append(k)
            elif not struct_ok(en[k], zh[k]): struct_fail[k] = {'en': en[k], 'zh': zh[k]}
    rep = {'name': name, 'en_keys': len(en), 'old_en_keys': len(old), 'dict_keys': len(zh),
           'dead': dead, 'missing': missing, 'changed_en': changed,
           'struct_fail': struct_fail, 'zh_eq_en': zh_eq_en}
    print('== %s ==' % name)
    print('  en_old=%d en=%d dict=%d dead=%d missing=%d changed_en=%d struct_fail=%d zh==en=%d'
          % (len(old), len(en), len(zh), len(dead), len(missing), len(changed),
             len(struct_fail), len(zh_eq_en)))
    return rep

fe = compare('frontend', os.path.join(ION_NEW, 'en-US.json'), os.path.join(ION_OLD, 'en-US.json'),
             os.path.join(LANG, 'linux/dictionary.json'))
shell = compare('desktop-shell', os.path.join(APP_NEW, 'en-US.json'), os.path.join(APP_OLD, 'en-US.json'),
                os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
dyn = compare('dynamic', os.path.join(ION_NEW, 'dynamic/en-US.json'), os.path.join(ION_OLD, 'dynamic/en-US.json'),
              os.path.join(LANG, 'dynamic/zh-CN.json'))

# overrides: 以新前端 en-US 为准
ov = load(os.path.join(LANG, 'linux/overrides.json'))
ov_en = load(os.path.join(ION_NEW, 'en-US.json'))
ov_dead = sorted(k for k in ov if k not in ov_en)
print('== overrides ==\n  keys=%d dead=%d' % (len(ov), len(ov_dead)))

# 官方壳 zh-Hans: 与 en-US / 我们壳词典的交集
zh_official = load(os.path.join(APP_NEW, 'zh-Hans.json'))
sh_en = load(os.path.join(APP_NEW, 'en-US.json'))
sh_dict = load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
off_keys = set(zh_official)
print('== official zh-Hans (app.asar resources/i18n) ==')
print('  official_keys=%d' % len(off_keys))
print('  keys not in en-US.json: %d' % len([k for k in off_keys if k not in sh_en]))
in_en = {k: v for k, v in zh_official.items() if k in sh_en}
same_as_en = [k for k, v in in_en.items() if v == sh_en[k]]
diff_from_ours = {k: v for k, v in in_en.items()
                  if k in sh_dict and sh_dict[k] != v and struct_ok(sh_en[k], v)}
missing_in_ours = {k: v for k, v in in_en.items() if k not in sh_dict}
print('  valid(在 en-US 中)=%d  其中值==英文=%d  与我们译文不同且结构OK=%d  我们缺的=%d'
      % (len(in_en), len(same_as_en), len(diff_from_ours), len(missing_in_ours)))
print('  sample diff_from_ours:', json.dumps(dict(list(diff_from_ours.items())[:8]), ensure_ascii=False, indent=1)[:1200])

# frame-shell 层: JS 提取英文 vs 现有词典
FS_EN_MAP = load('frame-shell-en-5.11492.5.json')
fs_dict_path = os.path.join(LANG, 'linux/frame-shell-dictionary.json')
fs_dict = load(fs_dict_path) if os.path.exists(fs_dict_path) else {}
fs_dead = sorted(k for k in fs_dict if k not in FS_EN_MAP)
fs_missing = sorted(k for k in FS_EN_MAP if k not in fs_dict)
fs_struct_fail = {}
for k in FS_EN_MAP:
    if k in fs_dict and fs_dict[k] != FS_EN_MAP[k] and not struct_ok(FS_EN_MAP[k], fs_dict[k]):
        fs_struct_fail[k] = {'en': FS_EN_MAP[k], 'zh': fs_dict[k]}
fs_files = sorted(os.listdir(FRAME))
fs_sample = load(os.path.join(FRAME, fs_files[0]))
print('== frame-shell ==')
print('  languages=%d sample=%s keys=%d' % (len(fs_files), fs_files[0], len(fs_sample)))
print('  en_map=%d dict=%d dead=%d missing=%d struct_fail=%d'
      % (len(FS_EN_MAP), len(fs_dict), len(fs_dead), len(fs_missing), len(fs_struct_fail)))

rep = {'frontend': fe, 'desktop_shell': shell, 'dynamic': dyn, 'overrides_dead': ov_dead,
       'frame_shell': {'name': 'frame-shell', 'en_keys': len(FS_EN_MAP), 'dict_keys': len(fs_dict),
                       'dead': fs_dead, 'missing': fs_missing, 'struct_fail': fs_struct_fail},
       'official_zh_hans': {'keys': len(off_keys), 'diff_from_ours': diff_from_ours,
                            'missing_in_ours': missing_in_ours, 'same_as_en': same_as_en}}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(rep, f, ensure_ascii=False, indent=1)
print('report ->', OUT)
