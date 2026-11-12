#!/usr/bin/env python3
# 按英文原文值做翻译记忆复用: 从现有词典/Windows 词典/官方壳构建 value->zh 映射,
# 对批次中相同英文原文的键直接复用, 剩余写入 tm-rest-*.json
import json, re

ROOT = '/workspace/Claude Desktop/zh-i18n'

def load(p): return json.load(open(p, encoding='utf-8'))

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

def _tokens(value):
    c = {}; st = strip_icu(value)
    for t in re.findall(r'<[^>]*>|\{[A-Za-z_][A-Za-z0-9_.-]*\}', st): c[t] = c.get(t, 0) + 1
    return c

def struct_ok(en, zh):
    a, b = str(en), str(zh)
    if a.count('{') != b.count('{') or a.count('}') != b.count('}'): return False
    if sorted(re.findall(r'<[^>]*>', a)) != sorted(re.findall(r'<[^>]*>', b)): return False
    if _tokens(a) != _tokens(b): return False
    return True

FE_EN = load(ROOT + '/work/ion-i18n-5.1231.2/i18n/en-US.json')
SH_EN = load(ROOT + '/work/app-i18n-5.1231.2/resources/i18n/en-US.json')
FS_EN = load(ROOT + '/work/frame-shell-en-5x.json')
ZH_OFF = load(ROOT + '/work/app-i18n-5.1231.2/resources/i18n/zh-Hans.json')

# 翻译记忆: 英文原文 -> 中文 (优先级: 官方壳 zh-Hans > Windows 壳 > Windows 前端 > Linux 现有词典)
def build_tm(en_map, zh_map):
    tm = {}
    for k, zh in zh_map.items():
        en = en_map.get(k)
        if en is None or zh == en or not struct_ok(en, zh): continue
        tm.setdefault(en, zh)
    return tm

tm = {}
tm.update(build_tm(load(ROOT + '/language/zh-CN/linux/dictionary.json'), load(ROOT + '/language/zh-CN/linux/dictionary.json')))
tm.update(build_tm(load(ROOT + '/work/app-i18n-4.23118.1/resources/i18n/en-US.json'),
                   load(ROOT + '/language/zh-CN/linux/desktop-shell-dictionary.json')))
tm.update(build_tm(load(ROOT + '/language/zh-CN/zh-CN.json'), load(ROOT + '/language/zh-CN/zh-CN.json')))
tm.update(build_tm(SH_EN, ZH_OFF))  # 官方壳优先级最高, 后写覆盖

stats = {}
import os
os.makedirs(ROOT + '/work/batches', exist_ok=True)
for name in sorted(os.listdir(ROOT + '/work/batches')):
    if not name.endswith('.json') or name.startswith('tm-'): continue
    batch = load(ROOT + '/work/batches/' + name)
    hit, rest = {}, {}
    for k, en in batch.items():
        zh = tm.get(en)
        if zh is not None and struct_ok(en, zh): hit[k] = zh
        else: rest[k] = en
    if hit:
        json.dump(hit, open(ROOT + '/work/batches/tm-%s.json' % name[:-5], 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    json.dump(rest, open(ROOT + '/work/batches/' + name, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    stats[name] = (len(batch), len(hit), len(rest))
    print('%s: %d -> TM复用 %d, 待译 %d' % (name, len(batch), len(hit), len(rest)))

total_rest = sum(v[2] for v in stats.values())
print('总待译: %d' % total_rest)
