#!/usr/bin/env python3
# 4.x 合并翻译结果到词典：Windows 复用 + 子代理批次译文；struct_ok 逐条校验，失败条目单独暴露
import json, os, re, sys

ROOT = '/workspace/Claude Desktop/zh-i18n'
ION_EN = os.path.join(ROOT, 'work/ion-i18n-4.29/i18n/en-US.json')
APP_EN = os.path.join(ROOT, 'work/app-i18n-4.29/resources/i18n/en-US.json')

def load(p):
    with open(p, encoding='utf-8') as f: return json.load(f)

def strip_icu(value):
    s = str(value); res = ''; i = 0
    while i < len(s):
        if s[i] == '{':
            depth = 0; j = i
            while j < len(s):
                if s[j] == '{': depth += 1
                elif s[j] == '}':
                    depth -= 1
                    if depth == 0: break
                j += 1
            if j < len(s) and re.match(r'^[A-Za-z_][A-Za-z0-9_.-]*,\s*(plural|selectordinal|select)\s*,', s[i+1:j]):
                res += '{__ICU__}'; i = j + 1; continue
        res += s[i]; i += 1
    return res

def tokens(value):
    c = {}; st = strip_icu(value)
    for t in re.findall(r'<[^>]*>|\{[A-Za-z_][A-Za-z0-9_.-]*\}', st): c[t] = c.get(t, 0) + 1
    return c

def struct_ok(en, zh):
    a, b = str(en), str(zh)
    if a.count('{') != b.count('{') or a.count('}') != b.count('}'): return False
    if sorted(re.findall(r'<[^>]*>', a)) != sorted(re.findall(r'<[^>]*>', b)): return False
    if tokens(a) != tokens(b): return False
    return True

def merge(dict_path, en_path, update_sources):
    en = load(en_path)
    d = load(dict_path)
    base_keys = len(d)
    dead = [k for k in d if k not in en]
    for k in dead: del d[k]
    applied = 0; failed = {}
    for src in update_sources:
        if not os.path.exists(src):
            failed.setdefault('_missing_file', []).append(src); continue
        for k, zh in load(src).items():
            if k not in en: failed.setdefault('_not_in_en', []).append(k); continue
            if not struct_ok(en[k], zh):
                failed[k] = {'en': en[k], 'zh': zh}; continue
            d[k] = zh; applied += 1
    tmp = dict_path + '.new'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, dict_path)
    print('%s: 原 %d 键 -> %d 键（删死键 %d，应用 %d 条更新）' %
          (os.path.basename(dict_path), base_keys, len(d), len(dead), applied))
    return failed

fe_sources = [os.path.join(ROOT, 'work/reuse-4x.json')] + \
             [os.path.join(ROOT, 'work/batches/out-batch-%d.json' % i) for i in range(1, 7)]
fe_failed = merge(os.path.join(ROOT, 'language/zh-CN/linux/dictionary.json'), ION_EN, fe_sources)

sh_sources = [os.path.join(ROOT, 'work/shell-reuse-4x.json'),
              os.path.join(ROOT, 'work/batches/out-batch-shell.json')]
sh_failed = merge(os.path.join(ROOT, 'language/zh-CN/linux/desktop-shell-dictionary.json'), APP_EN, sh_sources)

all_failed = dict(fe_failed); all_failed.update({('shell:' + k): v for k, v in sh_failed.items()})
json.dump(all_failed, open(os.path.join(ROOT, 'work/merge-failed-4x.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('校验未通过/异常条目: %d' % len(all_failed))
if all_failed: sys.exit(1)
