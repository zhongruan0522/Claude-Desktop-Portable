#!/usr/bin/env python3
# 单独补并 work/batches/tm-*.json 翻译记忆复用条目（merge-results-5x.py 已自动包含此步骤）
import glob, os
from common5x import WORK, LANG, paths_for, load, dump

P = paths_for()
tm = {}
for p in sorted(glob.glob(os.path.join(WORK, 'batches/tm-*.json'))):
    tm.update(load(p))
print('TM 条目: %d' % len(tm))

fe_path = os.path.join(LANG, 'linux/dictionary.json')
sh_path = os.path.join(LANG, 'linux/desktop-shell-dictionary.json')
fs_path = os.path.join(LANG, 'linux/frame-shell-dictionary.json')
fe, sh, fs = load(fe_path), load(sh_path), load(fs_path)

FE_EN = load(os.path.join(P['ion_i18n'], 'en-US.json'))
SH_EN = load(os.path.join(P['app_i18n'], 'en-US.json'))
FS_EN = load(P['fs_en'])

n1 = n2 = n3 = 0
for k, v in tm.items():
    if k in FE_EN and fe.get(k) != v: fe[k] = v; n1 += 1
    if k in SH_EN and sh.get(k) != v: sh[k] = v; n2 += 1
    if k in FS_EN and fs.get(k) != v: fs[k] = v; n3 += 1

dump(fe_path, fe)
dump(sh_path, sh)
dump(fs_path, fs)
print('并入: 前端 %d, 壳 %d, frame-shell %d' % (n1, n2, n3))
