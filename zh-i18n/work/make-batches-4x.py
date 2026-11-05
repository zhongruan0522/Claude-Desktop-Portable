#!/usr/bin/env python3
# 4.x 批次生成: diff-report-4x.json + Windows 复用剔除
import json, os

ROOT = '/workspace/Claude Desktop/zh-i18n'
REPORT = json.load(open(ROOT + '/work/diff-report-4x.json', encoding='utf-8'))
REUSE = json.load(open(ROOT + '/work/reuse-4x.json', encoding='utf-8'))
FE_EN = json.load(open(ROOT + '/work/ion-i18n-4.16336/i18n/en-US.json', encoding='utf-8'))
SH_EN = json.load(open(ROOT + '/work/app-i18n-4.16336/resources/i18n/en-US.json', encoding='utf-8'))

frontend = {k: FE_EN[k] for k in REPORT['frontend']['missing'] if k not in REUSE}
SH_REUSE = json.load(open(ROOT + '/work/reuse-shell-official-4x.json', encoding='utf-8'))
shell = {k: SH_EN[k] for k in REPORT['desktop_shell']['missing'] if k not in SH_REUSE}

os.makedirs(ROOT + '/work/batches', exist_ok=True)
for f in os.listdir(ROOT + '/work/batches'):
    os.remove(os.path.join(ROOT + '/work/batches', f))

keys = sorted(frontend)
N = 6
per = (len(keys) + N - 1) // N
for i in range(N):
    part = keys[i*per:(i+1)*per]
    if not part: continue
    json.dump({k: frontend[k] for k in part},
              open(ROOT + '/work/batches/batch-%d.json' % (i+1), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('batch-%d: %d 条' % (i+1, len(part)))
json.dump(shell, open(ROOT + '/work/batches/batch-shell.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('batch-shell: %d 条' % len(shell))
print('复用 %d 条将经 merge 直接并入' % len(REUSE))
