#!/usr/bin/env python3
# 5.x 合并: 死键清理 + 批次/TM复用/Windows复用/官方壳合并
import glob, os
from common5x import ROOT, WORK, LANG, load, dump

REPORT = load(os.path.join(WORK, 'diff-report-5x.json'))

def batch_sources(prefix):
    out = {}
    for p in sorted(glob.glob(os.path.join(WORK, 'batches', f'tm-{prefix}*.json'))):
        out.update(load(p))
    for p in sorted(glob.glob(os.path.join(WORK, 'results', f'{prefix}*.out.json'))):
        out.update(load(p))
    return out

def write_and_report(path, obj):
    dump(path, obj)
    print('%s: %d 键' % (os.path.relpath(path, ROOT), len(obj)))

# 前端: 死键 + Windows复用 + TM/翻译批次
fe_path = os.path.join(LANG, 'linux/dictionary.json')
fe = load(fe_path)
fe_dead = REPORT['frontend']['dead']
for k in fe_dead:
    fe.pop(k, None)
fe_before = len(fe)
fe.update(load(os.path.join(WORK, 'reuse-win-5x.json')))
fe.update(batch_sources('batch-fe'))
write_and_report(fe_path, fe)
print('  前端: 移除死键 %d，新增 %d' % (len(fe_dead), len(fe) - fe_before))

# 桌面壳: 死键 + TM/翻译批次 + Windows复用 + 官方 zh-Hans(最后并入 = 优先级最高)
sh_path = os.path.join(LANG, 'linux/desktop-shell-dictionary.json')
sh = load(sh_path)
sh_dead = REPORT['desktop_shell']['dead']
for k in sh_dead:
    sh.pop(k, None)
sh_before = len(sh)
sh.update(batch_sources('batch-shell'))
sh.update(load(os.path.join(WORK, 'reuse-win-shell-5x.json')))
official = load(os.path.join(WORK, 'official-shell-zh-5x.json'))
sh.update(official)
write_and_report(sh_path, sh)
print('  桌面壳: 移除死键 %d，新增 %d（官方 zh-Hans 并入 %d 条）' % (len(sh_dead), len(sh) - sh_before, len(official)))

# frame-shell: 死键 + Windows复用 + TM/翻译批次
fs_path = os.path.join(LANG, 'linux/frame-shell-dictionary.json')
fs = load(fs_path)
fs_dead = REPORT['frame_shell']['dead']
for k in fs_dead:
    fs.pop(k, None)
fs_before = len(fs)
fs.update(load(os.path.join(WORK, 'reuse-win-fs-5x.json')))
fs.update(batch_sources('batch-fs'))
write_and_report(fs_path, fs)
print('  frame-shell: 移除死键 %d，新增 %d' % (len(fs_dead), len(fs) - fs_before))

# overrides: 死键 + 结构失效键清理
ov_path = os.path.join(LANG, 'linux/overrides.json')
ov = load(ov_path)
ov_drop = sorted(set(REPORT['overrides_dead']) | set(REPORT.get('overrides_struct_fail', [])))
for k in ov_drop:
    ov.pop(k, None)
write_and_report(ov_path, ov)
print('  overrides: 移除死键/失效键 %d' % len(ov_drop))

dyn = load(os.path.join(LANG, 'dynamic/zh-CN.json'))
print('  dynamic: %d 键' % len(dyn))
