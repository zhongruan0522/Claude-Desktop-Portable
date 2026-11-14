#!/usr/bin/env python3
# 5.x 合并: 死键清理 + 批次/复用/官方合并
import json, os

ROOT = '/workspace/Claude Desktop/zh-i18n'
REPORT = json.load(open(ROOT + '/work/diff-report-5x.json', encoding='utf-8'))

def load(p): return json.load(open(p, encoding='utf-8'))
def dump(p, obj):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print('%s: %d 键' % (os.path.relpath(p, ROOT), len(obj)))

def batch_sources(names):
    out = {}
    for n in names:
        out.update(load(ROOT + '/work/results/' + n + '.out.json'))
    return out

# 前端: 死键 + TM复用 + 批次
fe = load(ROOT + '/language/zh-CN/linux/dictionary.json')
fe_dead = REPORT['frontend']['dead']
for k in fe_dead: fe.pop(k, None)
fe_before = len(fe)
fe.update(load(ROOT + '/work/reuse-win-5x.json'))
fe.update(batch_sources(['batch-fe-1', 'batch-fe-2', 'batch-fe-3', 'batch-fe-4', 'batch-fe-5']))
dump(ROOT + '/language/zh-CN/linux/dictionary.json', fe)
print('  前端: 移除死键 %d，新增 %d' % (len(fe_dead), len(fe) - fe_before))

# 桌面壳: 死键 + 批次 + 复用 + 官方 zh-Hans(最后并入 = 优先级最高)
sh = load(ROOT + '/language/zh-CN/linux/desktop-shell-dictionary.json')
sh_dead = REPORT['desktop_shell']['dead']
for k in sh_dead: sh.pop(k, None)
sh_before = len(sh)
sh.update(batch_sources(['batch-shell']))
sh.update(load(ROOT + '/work/reuse-win-shell-5x.json'))
official = load(ROOT + '/work/official-shell-zh-5x.json')
sh.update(official)
dump(ROOT + '/language/zh-CN/linux/desktop-shell-dictionary.json', sh)
print('  桌面壳: 移除死键 %d，新增 %d（官方 zh-Hans 并入 %d 条）' % (len(sh_dead), len(sh) - sh_before, len(official)))

# frame-shell: 死键 + 复用 + 批次
fs = load(ROOT + '/language/zh-CN/linux/frame-shell-dictionary.json')
for k in REPORT['frame_shell']['dead']: fs.pop(k, None)
fs_before = len(fs)
fs.update(load(ROOT + '/work/reuse-win-fs-5x.json'))
fs.update(batch_sources(['batch-fs-1', 'batch-fs-2']))
dump(ROOT + '/language/zh-CN/linux/frame-shell-dictionary.json', fs)
print('  frame-shell: 移除死键 %d，新增 %d' % (len(REPORT['frame_shell']['dead']), len(fs) - fs_before))

# overrides: 死键
ov = load(ROOT + '/language/zh-CN/linux/overrides.json')
ov_dead = REPORT['overrides_dead']
for k in ov_dead: ov.pop(k, None)
dump(ROOT + '/language/zh-CN/linux/overrides.json', ov)
print('  overrides: 移除死键 %d' % len(ov_dead))

# dynamic 不变
dyn = load(ROOT + '/language/zh-CN/dynamic/zh-CN.json')
print('  dynamic: 不变（%d 键）' % len(dyn))
