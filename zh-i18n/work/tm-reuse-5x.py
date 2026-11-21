#!/usr/bin/env python3
# 按英文原文值做翻译记忆复用: 从现有词典/旧版 frame-shell/已译批次/官方壳构建 value->zh 映射,
# 对批次中相同英文原文的键直接复用, 剩余写回原批次供翻译（支持多轮运行，例如先译 fe 再复用给 fs）
import glob, os
from common5x import WORK, LANG, current_ver, prev_ver, paths_for, load, dump, struct_ok

VER = current_ver()
OLD_VER = prev_ver(VER)
P = paths_for(VER)
P_OLD = paths_for(OLD_VER) if OLD_VER else None
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
        tm.setdefault(en, zh)
    return tm

tm = {}
fs_dict = load(os.path.join(LANG, 'linux/frame-shell-dictionary.json'))
if P_OLD and os.path.exists(P_OLD['fs_en']):
    tm.update(build_tm(load(P_OLD['fs_en']), fs_dict))
tm.update(build_tm(FE_EN, load(os.path.join(LANG, 'linux/dictionary.json'))))
tm.update(build_tm(SH_EN, load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))))
tm.update(build_tm(FS_EN, fs_dict))
# 若已存在已翻译的前端/壳/frame-shell 批次结果，一并纳入 TM 供跨层（如 fs 复用 fe）共享
for res_path in sorted(glob.glob(os.path.join(WORK, 'results', '*.out.json'))):
    res_map = load(res_path)
    base = os.path.basename(res_path)
    if base.startswith('batch-fe'):
        tm.update(build_tm(FE_EN, res_map))
    elif base.startswith('batch-shell'):
        tm.update(build_tm(SH_EN, res_map))
    elif base.startswith('batch-fs'):
        tm.update(build_tm(FS_EN, res_map))
tm.update(build_tm(SH_EN, ZH_OFF))  # 官方壳优先级最高, 后写覆盖

batches_dir = os.path.join(WORK, 'batches')
os.makedirs(batches_dir, exist_ok=True)
stats = {}
for name in sorted(os.listdir(batches_dir)):
    if not name.endswith('.json') or name.startswith('tm-'):
        continue
    out_path = os.path.join(WORK, 'results', name[:-5] + '.out.json')
    if os.path.exists(out_path):
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
        tm_path = os.path.join(batches_dir, 'tm-%s.json' % name[:-5])
        prev_hit = load(tm_path) if os.path.exists(tm_path) else {}
        prev_hit.update(hit)
        dump(tm_path, prev_hit)
    dump(bpath, rest)
    stats[name] = (len(batch), len(hit), len(rest))
    print('%s: %d -> TM复用 %d, 待译 %d' % (name, len(batch), len(hit), len(rest)))

total_rest = sum(v[2] for v in stats.values())
print('总待译: %d' % total_rest)
