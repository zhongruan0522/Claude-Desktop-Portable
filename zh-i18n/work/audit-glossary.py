#!/usr/bin/env python3
"""
全量术语一致性与翻译质量审计脚本：
对照当前解包版本的官方英文与官方 zh-Hans.json，检查五层词典与 JS 硬编码规则：
1. 官方桌面壳 zh-Hans.json 100% 原样复用校验
2. ICU MessageFormat 结构校验（common5x.struct_ok）
3. 错别字 / 禁用词 / 括号重复词检查
4. 锁定术语表一致性检查（Artifact / Skill / Agent / Subagent / Token / Prompt / Effort / Plan / Sandbox / Remote Control / PR / Fork / Stash vs Staged / Thread / Telemetry / Rewind / Accept edits / Side chat 等；
   2026-11-27 术语统一新增：中文省略号只用单个 …、Web search=网页搜索、Review comments=审查评论；
   2026-11-28：JS 文字规则 frontend-hardcoded.json 的中文侧纳入省略号与 Review 检查，Review 检查扩到 PR/代码审查的固定搭配；
   2026-11-28 术语统一 D9：直角引号「」、Are you sure 句省略「您」、Reviewer 译「审核人员/评审者」、PR 流程用「评审」、
   limit increase request 译「限额提升请求」、产品名 Code 译「代码」、数字紧贴中文量词；
   2026-11-28 术语统一 D8：disable 一族译「停用」、句首的 Enable / Enabling / Enabled 与「and enable …」译「开启」）
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
# PR / 代码审查流程里 Review 根词的固定搭配：一律译「审查」，不得用「审阅」（人阅读文档、合同、草稿的 review 不在此列）
REVIEW_RE = re.compile(r'\breview comments?\b|\b(?:code|pr) review\b|\breviewed\b|\breviewers?\b|\b(?:pending|ready for) review\b')
# 英文恰为 Code 但不是产品名的键（文件类型、Artifact 类型、代码块语言、图标与分类名、活动摘要里的小写 code）：
# 这些仍译「代码」；其余（与 Chat、Cowork 并列的产品名）应保留 Code。同步新版本后如新增此类键，按调用点判断后加进来
CODE_KIND_KEYS = {('fe', '/GfNmXqa0P'), ('fe', '0Aa0N5O99r'), ('fe', '6DGKcWW2C1'), ('fe', 'G8PgU8iXdR'), ('fe', 'USCMzD6r9q'),
                  ('fe', 'WXQGP2/7Ta'), ('fe', 'xX14rECk4J'), ('fe', 'xwbvXroWpK'), ('fe', 'yje76+c4Gb')}
UNIT_NO_SPACE = re.compile(r'\d[年月日天周号位次个条项名份秒]')
# disable 一族（disable / disabled / disabling）一律译「禁用」，不用「停用」；英文不是这一族而译「停用」的键（Retired、deactivated、turned off、stop 等）不属此列
DISABLE_RE = re.compile(r'\b(?:disable[sd]?|disabling)\b', re.I)
# enable（功能开关）= 启用 / 已启用。原文的 turn on / is on 仍译「开启」，同一句里两种都会出现，所以只查固定位置：
# 句首的 Enable / Enabling 不译「开启」、句首的 Enabled 不含「开启」、「and enable …」不译「并开启」
# （策略说明里原样保留的字面量 “enabled” / “disabled” 不受影响）

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
        # 2026-11-27 术语统一新增
        if re.search(r'[\u4e00-\u9fff]', zh) and ('...' in zh or '……' in zh):
            glossary_warns['省略号→单个 …（禁 ... 与 ……）'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bweb search', el) and '网络搜索' in zh:
            glossary_warns['Web search→网络搜索'].append((lname, k, en[:60], zh[:60]))
        if REVIEW_RE.search(el) and '审阅' in zh:
            glossary_warns['Review（PR/代码审查流程）→审查，不用审阅'].append((lname, k, en[:60], zh[:60]))
        # 2026-11-28 术语统一 D9 新增
        if '「' in zh or '」' in zh:
            glossary_warns['引号→使用 “ ”（不用直角引号「」）'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\bare you sure\b', el) and re.match(r'^(确定要|确实要)', zh):
            glossary_warns['Are you sure…→您确定要（不省略您）'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\breviewers?\b', el) and ('审核人员' in zh or '评审者' in zh):
            glossary_warns['Reviewer→审查者/审核者（不用审核人员、评审者）'].append((lname, k, en[:60], zh[:60]))
        if REVIEW_RE.search(el) and not re.search(r'peer review', el) and '评审' in zh:
            glossary_warns['Review（PR/代码审查流程）→审查，不用评审'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'limit increase requests?', el) and '限额提升请求' in zh:
            glossary_warns['Limit increase request→提高限额请求'].append((lname, k, en[:60], zh[:60]))
        if el == 'code' and '代码' in zh and (lname, k) not in CODE_KIND_KEYS:
            glossary_warns['Code（产品名）→保留英文'].append((lname, k, en[:60], zh[:60]))
        if UNIT_NO_SPACE.search(zh):
            glossary_warns['数字与中文量词之间留空格（6 个月、365 天）'].append((lname, k, en[:60], zh[:60]))
        # 2026-11-28 术语统一 D8 新增
        if DISABLE_RE.search(el) and '停用' in zh:
            glossary_warns['Disable 一族→禁用（不用停用）'].append((lname, k, en[:60], zh[:60]))
        if re.match(r'(?:enable|enabling)\b', el) and zh.startswith('开启'):
            glossary_warns['Enable（功能开关）→启用，不用开启'].append((lname, k, en[:60], zh[:60]))
        if re.search(r'\band enable\b', el) and '并开启' in zh:
            glossary_warns['Enable（功能开关）→启用，不用开启'].append((lname, k, en[:60], zh[:60]))
        if re.match(r'enabled\b', el) and '开启' in zh:
            glossary_warns['Enable（功能开关）→启用，不用开启'].append((lname, k, en[:60], zh[:60]))

# JS 文字规则只有中文侧，按同一口径查省略号与 Review 用词（2026-11-28 之前不在检查范围内）
for i, (s, t) in enumerate(load(os.path.join(LANG, 'frontend-hardcoded.json'))):
    if re.search(r'[\u4e00-\u9fff]', t) and ('...' in t or '……' in t):
        glossary_warns['省略号→单个 …（禁 ... 与 ……）'].append(('js', f'#{i}', s[:60], t[:60]))
    if REVIEW_RE.search(s.lower()) and '审阅' in t:
        glossary_warns['Review（PR/代码审查流程）→审查，不用审阅'].append(('js', f'#{i}', s[:60], t[:60]))
    # 2026-11-28 术语统一 D9 新增（JS 文字规则只有中文侧，查同一批纯中文写法）
    if '「' in t or '」' in t:
        glossary_warns['引号→使用 “ ”（不用直角引号「」）'].append(('js', f'#{i}', s[:60], t[:60]))
    if re.search(r'\bare you sure\b', s.lower()) and re.match(r'^(确定要|确实要)', t):
        glossary_warns['Are you sure…→您确定要（不省略您）'].append(('js', f'#{i}', s[:60], t[:60]))
    if re.search(r'\breviewers?\b', s.lower()) and ('审核人员' in t or '评审者' in t):
        glossary_warns['Reviewer→审查者/审核者（不用审核人员、评审者）'].append(('js', f'#{i}', s[:60], t[:60]))
    if REVIEW_RE.search(s.lower()) and not re.search(r'peer review', s.lower()) and '评审' in t:
        glossary_warns['Review（PR/代码审查流程）→审查，不用评审'].append(('js', f'#{i}', s[:60], t[:60]))
    if UNIT_NO_SPACE.search(t):
        glossary_warns['数字与中文量词之间留空格（6 个月、365 天）'].append(('js', f'#{i}', s[:60], t[:60]))
    # 2026-11-28 术语统一 D8 新增
    if DISABLE_RE.search(s) and '停用' in t:
        glossary_warns['Disable 一族→禁用（不用停用）'].append(('js', f'#{i}', s[:60], t[:60]))
    if re.match(r'(?:enable|enabling)\b', s.lower()) and t.startswith('开启'):
        glossary_warns['Enable（功能开关）→启用，不用开启'].append(('js', f'#{i}', s[:60], t[:60]))
    if re.search(r'\band enable\b', s.lower()) and '并开启' in t:
        glossary_warns['Enable（功能开关）→启用，不用开启'].append(('js', f'#{i}', s[:60], t[:60]))
    if re.match(r'enabled\b', s.lower()) and '开启' in t:
        glossary_warns['Enable（功能开关）→启用，不用开启'].append(('js', f'#{i}', s[:60], t[:60]))

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
