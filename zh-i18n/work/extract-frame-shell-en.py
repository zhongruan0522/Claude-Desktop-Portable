#!/usr/bin/env python3
# 从 frame-shell JS 提取 {id, defaultMessage} 英文映射
import re, json, glob

en = {}
conflicts = 0
for f in sorted(glob.glob('fs-shell-5.11492.5/resources/frame/shell/**/*.js', recursive=True)):
    t = open(f, encoding='utf-8', errors='replace').read()
    pat = re.compile(
        r'\{\s*(?:id:\s*"([^"]+)",\s*defaultMessage:\s*("(?:[^"\\]|\\.)*")'
        r'|defaultMessage:\s*("(?:[^"\\]|\\.)*"),\s*id:\s*"([^"]+)")\s*\}')
    for m in pat.finditer(t):
        k = m.group(1) or m.group(4)
        raw = m.group(2) or m.group(3)
        v = json.loads(raw)
        if k in en and en[k] != v:
            conflicts += 1
            print('CONFLICT', k, repr(en[k]), '->', repr(v))
        en[k] = v

print('total ids:', len(en), 'conflicts:', conflicts)
json.dump(en, open('frame-shell-en-5.11492.5.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

de = json.load(open('app-frame-shell-5.11492.5/resources/frame/shell/i18n/frame-shell/de-DE.json', encoding='utf-8'))
ja = json.load(open('app-frame-shell-5.11492.5/resources/frame/shell/i18n/frame-shell/ja-JP.json', encoding='utf-8'))
print('de keys:', len(de), 'all in en map:', all(k in en for k in de))
print('ja keys:', len(ja), 'all in en map:', all(k in en for k in ja))
extra = [k for k in en if k not in de]
print('en ids not in de-DE:', len(extra), extra[:12])
