#!/usr/bin/env python3
# 补并 TM 复用条目 + frame-shell 尾部 2 键
import json, os, glob

ROOT = '/workspace/Claude Desktop/zh-i18n'
def load(p): return json.load(open(p, encoding='utf-8'))
def dump(p, obj):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

tm = {}
for p in sorted(glob.glob(ROOT + '/work/batches/tm-*.json')):
    tm.update(load(p))
print('TM 条目: %d' % len(tm))

fe = load(ROOT + '/language/zh-CN/linux/dictionary.json')
sh = load(ROOT + '/language/zh-CN/linux/desktop-shell-dictionary.json')
fs = load(ROOT + '/language/zh-CN/linux/frame-shell-dictionary.json')

FE_EN = load(ROOT + '/work/ion-i18n-5.1231.2/i18n/en-US.json')
SH_EN = load(ROOT + '/work/app-i18n-5.1231.2/resources/i18n/en-US.json')
FS_EN = load(ROOT + '/work/frame-shell-en-5x.json')

n1 = n2 = n3 = 0
for k, v in tm.items():
    if k in FE_EN and fe.get(k) != v: fe[k] = v; n1 += 1
    if k in SH_EN and sh.get(k) != v: sh[k] = v; n2 += 1
    if k in FS_EN and fs.get(k) != v: fs[k] = v; n3 += 1

fs['RDs10nUT0d'] = '知道了'
fs['BLD0IuLr03'] = '关闭'

dump(ROOT + '/language/zh-CN/linux/dictionary.json', fe)
dump(ROOT + '/language/zh-CN/linux/desktop-shell-dictionary.json', sh)
dump(ROOT + '/language/zh-CN/linux/frame-shell-dictionary.json', fs)
print('并入: 前端 %d, 壳 %d, frame-shell %d' % (n1, n2, n3))
