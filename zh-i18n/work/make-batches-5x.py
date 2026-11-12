#!/usr/bin/env python3
# 5.x 批次生成: diff-report-5x.json + Windows/官方复用剔除
import json, os

ROOT = '/workspace/Claude Desktop/zh-i18n'
REPORT = json.load(open(ROOT + '/work/diff-report-5x.json', encoding='utf-8'))
REUSE_FE = json.load(open(ROOT + '/work/reuse-win-5x.json', encoding='utf-8'))
REUSE_SH = json.load(open(ROOT + '/work/reuse-win-shell-5x.json', encoding='utf-8'))
REUSE_FS = json.load(open(ROOT + '/work/reuse-win-fs-5x.json', encoding='utf-8'))
OFFICIAL_SH = json.load(open(ROOT + '/work/official-shell-zh-5x.json', encoding='utf-8'))
FE_EN = json.load(open(ROOT + '/work/ion-i18n-5.1231.2/i18n/en-US.json', encoding='utf-8'))
SH_EN = json.load(open(ROOT + '/work/app-i18n-5.1231.2/resources/i18n/en-US.json', encoding='utf-8'))
FS_EN = json.load(open(ROOT + '/work/frame-shell-en-5x.json', encoding='utf-8'))

frontend = {k: FE_EN[k] for k in REPORT['frontend']['missing'] if k not in REUSE_FE}
shell = {k: SH_EN[k] for k in REPORT['desktop_shell']['missing'] if k not in OFFICIAL_SH and k not in REUSE_SH}
fs = {k: FS_EN[k] for k in FS_EN if k not in REUSE_FS}

os.makedirs(ROOT + '/work/batches', exist_ok=True)
for f in os.listdir(ROOT + '/work/batches'):
    os.remove(os.path.join(ROOT + '/work/batches', f))

def dump(name, data):
    json.dump(data, open(ROOT + '/work/batches/' + name + '.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(name + ': %d 条' % len(data))

keys = sorted(frontend)
N = 5
per = (len(keys) + N - 1) // N
for i in range(N):
    part = keys[i*per:(i+1)*per]
    if part:
        dump('batch-fe-%d' % (i+1), {k: frontend[k] for k in part})
dump('batch-shell', shell)
fkeys = sorted(fs)
F = 2
fper = (len(fkeys) + F - 1) // F
for i in range(F):
    part = fkeys[i*fper:(i+1)*fper]
    if part:
        dump('batch-fs-%d' % (i+1), {k: fs[k] for k in part})
print('复用: fe %d, shell %d, fs %d; 官方壳 %d 条将经 merge 直接并入'
      % (len(REUSE_FE), len(REUSE_SH), len(REUSE_FS), len(OFFICIAL_SH)))
