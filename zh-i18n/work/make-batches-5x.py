#!/usr/bin/env python3
# 5.x 批次生成: diff-report-5x.json + Windows/官方复用剔除
import os
from common5x import WORK, paths_for, load, dump

P = paths_for()
REPORT = load(os.path.join(WORK, 'diff-report-5x.json'))
REUSE_FE = load(os.path.join(WORK, 'reuse-win-5x.json'))
REUSE_SH = load(os.path.join(WORK, 'reuse-win-shell-5x.json'))
REUSE_FS = load(os.path.join(WORK, 'reuse-win-fs-5x.json'))
OFFICIAL_SH = load(os.path.join(WORK, 'official-shell-zh-5x.json'))
FE_EN = load(os.path.join(P['ion_i18n'], 'en-US.json'))
SH_EN = load(os.path.join(P['app_i18n'], 'en-US.json'))
FS_EN = load(P['fs_en'])

frontend = {k: FE_EN[k] for k in REPORT['frontend']['missing'] if k not in REUSE_FE}
shell = {k: SH_EN[k] for k in REPORT['desktop_shell']['missing'] if k not in OFFICIAL_SH and k not in REUSE_SH}
fs = {k: FS_EN[k] for k in REPORT['frame_shell']['missing'] if k not in REUSE_FS}

batches_dir = os.path.join(WORK, 'batches')
os.makedirs(batches_dir, exist_ok=True)
for f in os.listdir(batches_dir):
    os.remove(os.path.join(batches_dir, f))

def write_batch(name, data):
    if not data:
        print(name + ': 0 条（跳过）')
        return
    dump(os.path.join(batches_dir, name + '.json'), data)
    print(name + ': %d 条' % len(data))

def split_batches(prefix, data, target_size):
    keys = sorted(data)
    if not keys:
        print(prefix + ': 0 条（跳过）')
        return
    n = max(1, (len(keys) + target_size - 1) // target_size)
    per = (len(keys) + n - 1) // n
    width = max(2, len(str(n))) if n > 1 else 1
    for i in range(n):
        part = keys[i * per:(i + 1) * per]
        if part:
            name = f'{prefix}-{i + 1:0{width}d}' if n > 1 else prefix
            write_batch(name, {k: data[k] for k in part})

fe_size = int(os.environ.get('BATCH_SIZE', '220'))
fs_size = int(os.environ.get('FS_BATCH_SIZE', '150'))
split_batches('batch-fe', frontend, fe_size)
write_batch('batch-shell', shell)
split_batches('batch-fs', fs, fs_size)
print('复用: fe %d, shell %d, fs %d; 官方壳 %d 条将经 merge 直接并入'
      % (len(REUSE_FE), len(REUSE_SH), len(REUSE_FS), len(OFFICIAL_SH)))
