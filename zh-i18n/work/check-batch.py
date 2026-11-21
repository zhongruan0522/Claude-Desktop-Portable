#!/usr/bin/env python3
# 供翻译子代理自检：python3 check-batch.py <batch> <out>
# 校验：JSON 可解析、键集与输入一致、ICU MessageFormat 结构校验通过、人称「您」与常见错别字检查
import json, os, sys
from common5x import struct_ok

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
    if '你' in zh and '迷你' not in zh:
        print('  注意 %s: 包含「你」，仓库约定对齐官方「您」（仅用户发给 Claude 的示例提示词除外）' % k)
    for bad in ('撤消', '帐单', '帐号', '帐户', '迷您', '您们'):
        if bad in zh:
            errs.append('%s: 包含禁用错别字「%s」' % (k, bad))
    if not struct_ok(en, zh):
        errs.append('%s: ICU/占位符/标签结构校验失败\n  EN: %s\n  ZH: %s' % (k, en, zh))
if errs:
    print('FAIL %d 处:' % len(errs))
    for e in errs: print(' ', e)
    sys.exit(1)
print('PASS %d/%d 条全部通过' % (len(out), len(src)))
