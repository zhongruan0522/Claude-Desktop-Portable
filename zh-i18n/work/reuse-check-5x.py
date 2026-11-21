#!/usr/bin/env python3
# 统计各层新增键在 Windows 词典 / 官方壳 zh-Hans 的可复用覆盖
import os
from common5x import WORK, LANG, paths_for, load, dump, struct_ok

P = paths_for()
WIN = load(os.path.join(LANG, 'zh-CN.json'))
WIN_OV = load(os.path.join(LANG, 'zh-CN.overrides.json'))
REP = load(os.path.join(WORK, 'diff-report-5x.json'))

FE_EN = load(os.path.join(P['ion_i18n'], 'en-US.json'))
SH_EN = load(os.path.join(P['app_i18n'], 'en-US.json'))
FS_EN = load(P['fs_en'])
ZH_OFF = load(os.path.join(P['app_i18n'], 'zh-Hans.json'))

def reuse_pool(keys, en_map):
    pool = {}
    for src_name, src in (('win', WIN), ('win_ov', WIN_OV)):
        for k in keys:
            if k in src and k in en_map and src[k] != en_map[k] and struct_ok(en_map[k], src[k]):
                pool.setdefault(k, ('win' if src_name == 'win' else 'win_ov', src[k]))
    return pool

# 全量原样复用官方壳 zh-Hans.json（含保留英文专名及官方中文复数写法，保持官方人称「您」）
valid_off = {k: v for k, v in ZH_OFF.items()
             if k in SH_EN and struct_ok(SH_EN[k], v)}
print('official shell zh-Hans valid:', len(valid_off))
dump(os.path.join(WORK, 'official-shell-zh-5x.json'), valid_off)

fe_keys = REP['frontend']['missing']
sh_keys = [k for k in REP['desktop_shell']['missing'] if k not in valid_off]
fs_keys = REP['frame_shell']['missing']

for name, keys, en_map, out_name in (
    ('frontend', fe_keys, FE_EN, 'reuse-win-5x.json'),
    ('shell(rest)', sh_keys, SH_EN, 'reuse-win-shell-5x.json'),
    ('frame-shell', fs_keys, FS_EN, 'reuse-win-fs-5x.json'),
):
    pool = reuse_pool(keys, en_map)
    print('%s: %d 键, Windows 可复用 %d (%.1f%%)' % (name, len(keys), len(pool), 100 * len(pool) / max(1, len(keys))))
    dump(os.path.join(WORK, out_name), {k: v[1] for k, v in pool.items()})

print('written reuse files')
