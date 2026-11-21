#!/usr/bin/env python3
# 5.x 结构差异分析: en-US 从 asar 提取物读取, 词典层保持原位
# 另输出: 英文原文变更键、官方壳 zh-Hans 可复用项、frame-shell 新词典层键数
import json, os
from common5x import WORK, LANG, current_ver, prev_ver, paths_for, load, dump, struct_ok

VER = current_ver()
OLD_VER = prev_ver(VER)
P_NEW = paths_for(VER)
P_OLD = paths_for(OLD_VER) if OLD_VER else None
OUT = os.path.join(WORK, 'diff-report-5x.json')

print(f'分析版本: {VER}' + (f'（对比旧版 {OLD_VER}）' if OLD_VER else '（无旧版基线目录，跳过 changed_en 对比）'))

def compare(name, en_new, en_old, dict_path):
    en = load(en_new)
    old = load(en_old) if en_old and os.path.exists(en_old) else {}
    zh = load(dict_path) if os.path.exists(dict_path) else {}
    dead = sorted(k for k in zh if k not in en)
    missing = sorted(k for k in en if k not in zh)
    changed = sorted(k for k in en if k in old and en[k] != old[k])
    struct_fail = {}
    zh_eq_en = []
    for k in en:
        if k in zh:
            if zh[k] == en[k]:
                zh_eq_en.append(k)
            elif not struct_ok(en[k], zh[k]):
                struct_fail[k] = {'en': en[k], 'zh': zh[k]}
    rep = {'name': name, 'en_keys': len(en), 'old_en_keys': len(old), 'dict_keys': len(zh),
           'dead': dead, 'missing': missing, 'changed_en': changed,
           'struct_fail': struct_fail, 'zh_eq_en': zh_eq_en}
    print('== %s ==' % name)
    print('  en_old=%d en=%d dict=%d dead=%d missing=%d changed_en=%d struct_fail=%d zh==en=%d'
          % (len(old), len(en), len(zh), len(dead), len(missing), len(changed),
             len(struct_fail), len(zh_eq_en)))
    return rep

fe = compare('frontend',
             os.path.join(P_NEW['ion_i18n'], 'en-US.json'),
             os.path.join(P_OLD['ion_i18n'], 'en-US.json') if P_OLD else '',
             os.path.join(LANG, 'linux/dictionary.json'))
shell = compare('desktop-shell',
                os.path.join(P_NEW['app_i18n'], 'en-US.json'),
                os.path.join(P_OLD['app_i18n'], 'en-US.json') if P_OLD else '',
                os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
dyn = compare('dynamic',
              os.path.join(P_NEW['ion_i18n'], 'dynamic/en-US.json'),
              os.path.join(P_OLD['ion_i18n'], 'dynamic/en-US.json') if P_OLD else '',
              os.path.join(LANG, 'dynamic/zh-CN.json'))

ov = load(os.path.join(LANG, 'linux/overrides.json'))
ov_en = load(os.path.join(P_NEW['ion_i18n'], 'en-US.json'))
ov_dead = sorted(k for k in ov if k not in ov_en)
ov_fail = sorted(k for k in ov if k in ov_en and ov[k] != ov_en[k] and not struct_ok(ov_en[k], ov[k]))
print('== overrides ==\n  keys=%d dead=%d struct_fail=%d' % (len(ov), len(ov_dead), len(ov_fail)))

zh_official = load(os.path.join(P_NEW['app_i18n'], 'zh-Hans.json'))
sh_en = load(os.path.join(P_NEW['app_i18n'], 'en-US.json'))
sh_dict = load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
off_keys = set(zh_official)
print('== official zh-Hans (app.asar resources/i18n) ==')
print('  official_keys=%d' % len(off_keys))
print('  keys not in en-US.json: %d' % len([k for k in off_keys if k not in sh_en]))
in_en = {k: v for k, v in zh_official.items() if k in sh_en}
same_as_en = [k for k, v in in_en.items() if v == sh_en[k]]
diff_from_ours = {k: v for k, v in in_en.items()
                  if k in sh_dict and sh_dict[k] != v and struct_ok(sh_en[k], v)}
missing_in_ours = {k: v for k, v in in_en.items() if k not in sh_dict and struct_ok(sh_en[k], v)}
print('  valid(在 en-US 中)=%d  其中值==英文=%d  与我们译文不同且结构OK=%d  我们缺的=%d'
      % (len(in_en), len(same_as_en), len(diff_from_ours), len(missing_in_ours)))
if diff_from_ours:
    print('  sample diff_from_ours:', json.dumps(dict(list(diff_from_ours.items())[:8]), ensure_ascii=False, indent=1)[:1200])

FS_EN_MAP = load(P_NEW['fs_en'])
FS_OLD_MAP = load(P_OLD['fs_en']) if P_OLD and os.path.exists(P_OLD['fs_en']) else {}
fs_dict_path = os.path.join(LANG, 'linux/frame-shell-dictionary.json')
fs_dict = load(fs_dict_path) if os.path.exists(fs_dict_path) else {}
fs_dead = sorted(k for k in fs_dict if k not in FS_EN_MAP)
fs_missing = sorted(k for k in FS_EN_MAP if k not in fs_dict)
fs_changed = sorted(k for k in FS_EN_MAP if k in FS_OLD_MAP and FS_EN_MAP[k] != FS_OLD_MAP[k])
fs_struct_fail = {}
fs_eq = []
for k in FS_EN_MAP:
    if k in fs_dict:
        if fs_dict[k] == FS_EN_MAP[k]:
            fs_eq.append(k)
        elif not struct_ok(FS_EN_MAP[k], fs_dict[k]):
            fs_struct_fail[k] = {'en': FS_EN_MAP[k], 'zh': fs_dict[k]}
frame_i18n = os.path.join(P_NEW['app_fs'], 'i18n/frame-shell')
if os.path.isdir(frame_i18n):
    fs_files = sorted(os.listdir(frame_i18n))
    fs_sample = load(os.path.join(frame_i18n, fs_files[0]))
    print('== frame-shell ==')
    print('  languages=%d sample=%s keys=%d' % (len(fs_files), fs_files[0], len(fs_sample)))
print('  en_old=%d en_map=%d dict=%d dead=%d missing=%d changed_en=%d struct_fail=%d zh==en=%d'
      % (len(FS_OLD_MAP), len(FS_EN_MAP), len(fs_dict), len(fs_dead), len(fs_missing), len(fs_changed), len(fs_struct_fail), len(fs_eq)))

rep = {'version': VER, 'frontend': fe, 'desktop_shell': shell, 'dynamic': dyn,
       'overrides_dead': ov_dead, 'overrides_struct_fail': ov_fail,
       'frame_shell': {'name': 'frame-shell', 'en_keys': len(FS_EN_MAP), 'old_en_keys': len(FS_OLD_MAP),
                       'dict_keys': len(fs_dict), 'dead': fs_dead, 'missing': fs_missing,
                       'changed_en': fs_changed, 'struct_fail': fs_struct_fail, 'zh_eq_en': fs_eq},
       'official_zh_hans': {'keys': len(off_keys), 'diff_from_ours': diff_from_ours,
                            'missing_in_ours': missing_in_ours, 'same_as_en': same_as_en}}
dump(OUT, rep)
print('report ->', OUT)
