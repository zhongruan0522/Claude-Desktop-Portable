#!/usr/bin/env python3
# 按英文原文值做翻译记忆复用: 从现有词典/Windows 词典/官方壳构建 value->zh 映射,
# 对批次中相同英文原文的键直接复用, 剩余写回原批次供翻译
import os
from common5x import WORK, LANG, paths_for, load, dump, struct_ok

P = paths_for()
FE_EN = load(os.path.join(P['ion_i18n'], 'en-US.json'))
SH_EN = load(os.path.join(P['app_i18n'], 'en-US.json'))
FS_EN = load(P['fs_en'])
ZH_OFF = load(os.path.join(P['app_i18n'], 'zh-Hans.json'))

def build_tm(en_map, zh_map):
    tm = {}
    for k, zh in zh_map.items():
        en = en_map.get(k)
        if en is None or zh == en or not struct_ok(en, zh):
            continue
        tm.setdefault(en, zh.replace('您', '你'))
    return tm

tm = {}
tm.update(build_tm(FE_EN, load(os.path.join(LANG, 'linux/dictionary.json'))))
tm.update(build_tm(SH_EN, load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))))
tm.update(build_tm(FS_EN, load(os.path.join(LANG, 'linux/frame-shell-dictionary.json'))))
tm.update(build_tm(SH_EN, ZH_OFF))  # 官方壳优先级最高, 后写覆盖

batches_dir = os.path.join(WORK, 'batches')
os.makedirs(batches_dir, exist_ok=True)
stats = {}
for name in sorted(os.listdir(batches_dir)):
    if not name.endswith('.json') or name.startswith('tm-'):
        continue
    bpath = os.path.join(batches_dir, name)
    batch = load(bpath)
    hit, rest = {}, {}
    for k, en in batch.items():
        zh = tm.get(en)
        if zh is not None and struct_ok(en, zh):
            hit[k] = zh
        else:
            rest[k] = en
    if hit:
        dump(os.path.join(batches_dir, 'tm-%s.json' % name[:-5]), hit)
    dump(bpath, rest)
    stats[name] = (len(batch), len(hit), len(rest))
    print('%s: %d -> TM复用 %d, 待译 %d' % (name, len(batch), len(hit), len(rest)))

total_rest = sum(v[2] for v in stats.values())
print('总待译: %d' % total_rest)
