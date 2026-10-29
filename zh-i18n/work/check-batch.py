#!/usr/bin/env python3
# 供翻译子代理自检：python3 check-batch.py <batch> <out>
# 校验：JSON 可解析、键集与输入一致、每条花括号计数与 <tag> 标签集合和英文一致
import json, re, sys

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

batch_path, out_path = sys.argv[1], sys.argv[2]
src = json.load(open(batch_path, encoding='utf-8'))
out = json.load(open(out_path, encoding='utf-8'))
errs = []
if set(out) != set(src):
    errs.append('键集不一致：缺 %d 个 %s' % (len(set(src) - set(out)), sorted(set(src) - set(out))[:5]))
for k in set(src) & set(out):
    en, zh = str(src[k]), str(out[k])
    if zh == en:
        print('  注意 %s: 译文与英文相同（若为专名/格式串则可接受）' % k); continue
    if en.count('{') != zh.count('{') or en.count('}') != zh.count('}'):
        errs.append('%s: 花括号计数不一致 (%d/%d vs %d/%d)' % (k, en.count('{'), en.count('}'), zh.count('{'), zh.count('}')))
    if sorted(re.findall(r'<[^>]*>', en)) != sorted(re.findall(r'<[^>]*>', zh)):
        errs.append('%s: 标签集合不一致\n  EN: %s\n  ZH: %s' % (k, re.findall(r'<[^>]*>', en), re.findall(r'<[^>]*>', zh)))
    if tokens(en) != tokens(zh):
        errs.append('%s: 占位符/标签出现次数不一致\n  EN tokens: %s\n  ZH tokens: %s' % (k, tokens(en), tokens(zh)))
if errs:
    print('FAIL %d 处:' % len(errs))
    for e in errs: print(' ', e)
    sys.exit(1)
print('PASS %d/%d 条全部通过' % (len(out), len(src)))
