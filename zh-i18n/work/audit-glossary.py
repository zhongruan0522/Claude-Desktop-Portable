#!/usr/bin/env python3
"""
全量术语一致性与翻译质量审计脚本：
对照当前解包版本的官方英文与官方 zh-Hans.json，检查五层词典与 JS 硬编码规则：
1. 官方桌面壳 zh-Hans.json 100% 原样复用校验
2. ICU MessageFormat 结构校验（common5x.struct_ok）
3. 错别字 / 禁用词 / 括号重复词检查
4. 锁定术语表一致性检查（Artifact / Skill / Agent / Subagent / Token / Prompt / Effort / Plan / Sandbox / Remote Control / PR / Fork / Stash vs Staged / Thread / Telemetry / Rewind / Accept edits / Side chat 等）
5. 同英文多中文译法统计
"""
import json, os, re, sys
from collections import Counter, defaultdict
from common5x import ROOT, WORK, LANG, paths_for, load, struct_ok

P = paths_for()
print('审计目标版本:', P['ver'])

fe_en = load(os.path.join(P['ion_i18n'], 'en-US.json'))
fe_zh = load(os.path.join(LANG, 'linux/dictionary.json'))
ov_zh = load(os.path.join(LANG, 'linux/overrides.json'))
sh_en = load(os.path.join(P['app_i18n'], 'en-US.json'))
sh_zh = load(os.path.join(LANG, 'linux/desktop-shell-dictionary.json'))
sh_off = load(os.path.join(P['app_i18n'], 'zh-Hans.json'))
fs_en = load(P['fs_en'])
fs_zh = load(os.path.join(LANG, 'linux/frame-shell-dictionary.json'))
dyn_en = load(os.path.join(P['ion_i18n'], 'dynamic/en-US.json'))
dyn_zh = load(os.path.join(LANG, 'dynamic/zh-CN.json'))

# 1. Official zh-Hans exact match check
off_diff = [k for k in sh_en if k in sh_off and sh_zh.get(k) != sh_off[k]]
print(f'\n[1] 官方壳 zh-Hans.json 复用: {len(sh_off) - len(off_diff)}/{len(sh_off)} 完全一致（差异 {len(off_diff)} 条）')
for k in off_diff[:10]:
    print(f'  DIFF {k}: ours={sh_zh.get(k)!r} vs off={sh_off[k]!r}')

# 2. Overrides sync check
ov_diff = [k for k in ov_zh if k in fe_zh and ov_zh[k] != fe_zh[k]]
print(f'[2] overrides vs dictionary 同步: {len(ov_zh) - len(ov_diff)}/{len(ov_zh)} 一致（差异 {len(ov_diff)} 条）')

# 3. Structural & typo check across all layers
layers = [('fe', fe_en, fe_zh), ('sh', sh_en, sh_zh), ('fs', fs_en, fs_zh), ('dyn', dyn_en, dyn_zh)]
struct_fails = []
typo_hits = defaultdict(list)
glossary_warns = defaultdict(list)

BAD_TYPOS = ('撤消', '帐单', '帐号', '帐户', '迷您', '您们')

for lname, em, zm in layers:
    for k, en in em.items():
        zh = zm.get(k, '')
        if not zh:
            struct_fails.append((lname, k, 'MISSING'))
            continue
        if zh != en and not struct_ok(en, zh):
            struct_fails.append((lname, k, 'ICU_FAIL'))
        for w in BAD_TYPOS:
            if w in zh:
                if lname == 'sh' and k in sh_off:
                    continue  # 官方壳原样复用，不私自改写
                typo_hits[w].append((lname, k, zh[:80]))
        if re.search(r'([\u4e00-\u9fff]{2,4})[（(]\1[）)]', zh):
            typo_hits['括号重复词'].append((lname, k, zh[:80]))
        # Skip official desktop-shell keys from glossary warnings (official is canonical)
        if lname == 'sh' and k in sh_off:
            continue
        el = en.lower()
        if re.search(r'\bartifacts?\b', el) and '作品' in zh:
            glossary_warns['Artifact→作品'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bremote control\b', el) and '远程控制' in zh:
            glossary_warns['Remote Control→远程控制'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bsub-?agents?\b', el) and ('子智能体' in zh or '子代理' in zh):
            glossary_warns['Subagent→中文'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bagents?\b', el) and '智能体' in zh:
            glossary_warns['Agent→智能体'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bsandbox\w*\b', el) and '沙箱' in zh:
            glossary_warns['Sandbox→沙箱'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bpull requests?\b', el) and '拉取请求' in zh:
            glossary_warns['PR→拉取请求'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bside chat\b', el) and ('侧边聊天' in zh or '旁支聊天' in zh):
            glossary_warns['Side chat→聊天'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bthreads?\b', el) and '线程' in zh:
            glossary_warns['Thread→线程'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\btelemetry\b', el) and '诊断' in zh:
            glossary_warns['Telemetry→诊断'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\baccount\b', el) and '账号' in zh:
            glossary_warns['Account→账号'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bcomputer use\b', el) and '电脑操作' in zh:
            glossary_warns['Computer use→电脑操作'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\boutput styles?\b', el) and '输出样式' in zh:
            glossary_warns['Output style→输出样式'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\befforts?\b', el) and any(w in zh for w in ('思考深度', '推理强度', '投入度')):
            glossary_warns['Effort→非思考强度'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bprompt[- ]cache\b|\bsystem prompt\b|\bprompt injection\b', el) and re.search(r'提示(?!词)', zh):
            glossary_warns['Prompt→提示(缺词)'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\b(input|output|cached|max|prompt-cache)\s+tokens?\b|\btoken\s+limits?\b', el) and ('令牌' in zh or '词元' in zh):
            glossary_warns['LLM Token→令牌/词元'].append((lname, k, en[:60], zh[:60]))

print(f'[3] 结构校验失败: {len(struct_fails)} 条')
for x in struct_fails[:10]:
    print(' ', x)

print(f'[4] 错别字/重复词: {sum(len(v) for v in typo_hits.values())} 条')
for w, items in sorted(typo_hits.items()):
    print(f'  {w}: {len(items)} 处 (样例: {items[:3]})')

print(f'[5] 术语规范残余告警: {sum(len(v) for v in glossary_warns.values())} 条')
for w, items in sorted(glossary_warns.items()):
    print(f'  {w}: {len(items)} 处')
    for it in items[:3]:
        print(f'    {it[0]}:{it[1]} | EN: {it[2]} | ZH: {it[3]}')

# 6. Cross-layer duplicate EN consistency
en_to_zh = defaultdict(set)
for lname, em, zm in layers:
    for k, en in em.items():
        en_to_zh[en].add(zm.get(k, ''))
multi = {en: zhs for en, zhs in en_to_zh.items() if len(zhs) > 1}
print(f'[6] 跨层同英文多译法组数: {len(multi)}')

if struct_fails or off_diff or ov_diff or typo_hits:
    sys.exit(1)
print('✔ 术语与结构核心审计通过')
