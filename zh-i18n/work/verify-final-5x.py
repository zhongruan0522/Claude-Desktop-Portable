#!/usr/bin/env python3
# 最终校验: 五层词典 vs 当前解包 5.x en-US（零死键、零缺失、零 ICU/标签结构错误）
import os, sys
from common5x import LANG, paths_for, load, struct_ok

P = paths_for()
print('校验目标版本:', P['ver'])

errors = 0

def check(name, en_map, dict_path):
    global errors
    zh = load(dict_path)
    missing = [k for k in en_map if k not in zh]
    dead = [k for k in zh if k not in en_map]
    fail = [k for k in en_map if k in zh and zh[k] != en_map[k] and not struct_ok(en_map[k], zh[k])]
    eq = [k for k in en_map if k in zh and zh[k] == en_map[k]]
    print('%s: en=%d dict=%d 未译=%d 死键=%d 结构失败=%d 与英文相同=%d'
          % (name, len(en_map), len(zh), len(missing), len(dead), len(fail), len(eq)))
    if missing[:5]:
        print('  未译样例:', missing[:5])
    if fail[:5]:
        print('  结构失败样例:', fail[:5])
    if missing or dead or fail:
        errors += len(missing) + len(dead) + len(fail)
    return missing, fail

FE_EN = load(os.path.join(P['ion_i18n'], 'en-US.json'))
SH_EN = load(os.path.join(P['app_i18n'], 'en-US.json'))
FS_EN = load(P['fs_en'])
DYN_EN = load(os.path.join(P['ion_i18n'], 'dynamic/en-US.json'))

check('前端', FE_EN, os.path.join(LANG, 'linux/dictionary.json'))
check('桌面壳', SH_EN, os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
check('frame-shell', FS_EN, os.path.join(LANG, 'linux/frame-shell-dictionary.json'))
check('dynamic', DYN_EN, os.path.join(LANG, 'dynamic/zh-CN.json'))

ov = load(os.path.join(LANG, 'linux/overrides.json'))
ov_dead = [k for k in ov if k not in FE_EN]
ov_fail = [k for k in ov if k in FE_EN and ov[k] != FE_EN[k] and not struct_ok(FE_EN[k], ov[k])]
print('overrides: %d 键, 死键 %d, 结构失败 %d' % (len(ov), len(ov_dead), len(ov_fail)))
if ov_dead or ov_fail:
    errors += len(ov_dead) + len(ov_fail)

if errors:
    sys.exit(1)
print('✔ 五层词典全量校验通过')
