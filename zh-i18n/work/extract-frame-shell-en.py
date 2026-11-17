#!/usr/bin/env python3
# 从 frame-shell JS 提取 {id, defaultMessage[, description]} 英文映射
import glob, json, os, re
from common5x import paths_for, load, dump

P = paths_for()
FS_DIR = P['app_fs']
OUT = P['fs_en']

FS_MSG_RE = re.compile(
    r'\{\s*(?:(?:id|defaultMessage|description)\s*:\s*"(?:[^"\\]|\\.)*"\s*,\s*){1,2}'
    r'(?:id|defaultMessage|description)\s*:\s*"(?:[^"\\]|\\.)*"\s*\}')
FS_PROP_RE = re.compile(r'\b(id|defaultMessage)\s*:\s*("(?:[^"\\]|\\.)*")')

en = {}
conflicts = 0
for f in sorted(glob.glob(os.path.join(FS_DIR, '**/*.js'), recursive=True)):
    t = open(f, encoding='utf-8', errors='replace').read()
    for m in FS_MSG_RE.finditer(t):
        props = {pm.group(1): json.loads(pm.group(2)) for pm in FS_PROP_RE.finditer(m.group(0))}
        if 'id' not in props or 'defaultMessage' not in props:
            continue
        k, v = props['id'], props['defaultMessage']
        if k in en and en[k] != v:
            conflicts += 1
            print('CONFLICT', k, repr(en[k]), '->', repr(v))
        en[k] = v

print('version:', P['ver'], 'total ids:', len(en), 'conflicts:', conflicts)
dump(OUT, en)

i18n_dir = os.path.join(FS_DIR, 'i18n/frame-shell')
if os.path.isdir(i18n_dir):
    de = load(os.path.join(i18n_dir, 'de-DE.json'))
    ja = load(os.path.join(i18n_dir, 'ja-JP.json'))
    print('de keys:', len(de), 'all in en map:', all(k in en for k in de))
    print('ja keys:', len(ja), 'all in en map:', all(k in en for k in ja))
    extra = [k for k in en if k not in de]
    print('en ids not in de-DE:', len(extra), extra[:12])
