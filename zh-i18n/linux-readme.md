# Linux（官方 APT 版）汉化说明

适用于通过 Anthropic 官方 apt 源（`downloads.claude.ai/claude-desktop/apt/stable`）安装的
Claude Desktop，安装目录 `/usr/lib/claude-desktop`。安装器**自动识别 6.x / 5.x / 4.x / 3.x 资源布局**，
已在 **6.28899.6（amd64，asar 布局 + frame-shell 层）**、**5.11492.5**、**5.1231.2**、**4.23118.1（amd64，asar 布局）** 与
**3.6556.2（amd64，明文目录布局）** 上完整验证：
安装 → 全量校验 → 幂等重装 → 升级检测 → 恢复后与官方原版**逐字节一致**。

## 4.x 布局（4.29.0 起）

- 前端整体打包进 `resources/ion-dist.asar`（4,500+ 条目，全条目 SHA-256 integrity）：
  词典 `i18n/*.json`、动态文案 `i18n/dynamic/*.json`、JS 资源 `assets/v1/*.js`。
- 桌面壳词典移入 `app.asar` 内 `resources/i18n/<locale>.json`（原 resources 顶层
  `en-US.json`/`zh-CN.json` 不复存在）。
- 汉化方式：安装器在 asar 内新增 `zh-CN` 词条、按内容规则就地补丁 JS、重建 asar
  并重算全部 integrity，重建后自检（逐条目 SHA-256 比对）通过才落盘；`reset` 整档还原。

## 5.x 布局（5.1231.x 起）

- 前端与桌面壳词典路径不变；`resources/i18n/` 官方开始自带 `zh-Hans.json`
  （简体中文桌面壳官方翻译），按"官方优先"并入桌面壳词典（见下）。
- **frame/shell 捆绑包**（作品共享页 / Artifact 查看器外壳；4.23118.x 后期已引入、
  5.x 延续，同一份 frame-shell 词典对两个版本均生效）：
  英文原文内嵌于 JS 的 `{id, defaultMessage}` 消息对，官方附带 10 种语言的词典（5.11492.5 时仅各 108 键，
  6.28899.x 为各 1,901 键；无 en-US.json，无中文）；捆绑包由模拟器经 `shell-manifest.json` 伺服，
  **启动时对清单内每个文件做 bytes+SHA-256 校验**，可用语言硬编码在
  `frame-shell.html` 的 meta 标签（`data-shipped` / `data-catalogs`）里。
- 汉化方式：在 asar 内新增 `frame/shell/i18n/frame-shell/zh-CN.json`（全部 1,898 键，
  英文原文从 JS 提取）、登记 `shell-manifest.json`（bytes + sha256 + contentType）、
  在 `frame-shell.html` 语言清单中加入 `zh-CN`（并同步被修改文件的清单哈希，
  否则启动校验会拒绝整个捆绑包）。

## 使用

```bash
sudo ./install-linux.sh            # 安装/更新汉化
sudo ./install-linux.sh check      # 查看状态
sudo ./install-linux.sh reset      # 恢复英文原版
sudo ./install-linux.sh --set-locale   # 安装并把 ~/.config/Claude/config.json 的 locale 写为 zh-CN
```

安装完成后启动 Claude，从头像/用户菜单进入“语言”，选择“简体中文”。

- **需要 sudo**：应用目录归 root 所有；脚本非 root 运行时会自动请求提权。
- **依赖 python3**（Debian/Ubuntu 桌面自带）。
- **Claude 升级后**（`apt upgrade` 会覆盖整个应用目录）：重新运行一次 install 即可。
  脚本按版本号（deb 版本或词典 en-US 哈希）检测变化，自动清理旧备份并按新版重打；
  词典与新版英文资源自动合并，新增键以英文显示，改动了原文的旧译文会自动回退英文
  （ICU 结构安全检查），不会出现变量丢失或标签损坏。
- 从 3.x 升级到 4.x 后残留的 `resources/ion-dist/` 明文目录（旧版部署物）会被新版
  应用忽略，可留可删，不影响汉化。

## 与 Windows 版的对应关系

| Windows（install.cmd） | Linux（install-linux.sh） | 说明 |
| --- | --- | --- |
| `app\resources\` | `/usr/lib/claude-desktop/resources/` | 4.x 前端在 ion-dist.asar、桌面壳词典在 app.asar 内 |
| `_repair-backup\` | `/usr/lib/claude-desktop/.zh-CN-backup/` | 放在 resources 之外，避免被应用的语言枚举误读 |
| 8 个版本锁定 JS 覆盖文件 | 按内容匹配的规则集 | Linux 不用预生成 JS：白名单/名称映射/persona/硬编码规则均按内容命中，版本更迭时自动重新匹配 |
| app.asar locale 映射补丁 | 同款补丁 | Linux Electron 不校验 asar 签名；重建后全条目 SHA-256 完整性自检通过 |
| AppX 清单注册 zh-CN | 无需 | 前端按词典文件枚举语言，asar 内 `i18n/zh-CN.json` 直接被识别 |

## 覆盖率（Linux 6.28899.6，2026-11-23 增量同步；2026-11-21 全量精校与官方术语对齐）

| 层 | 键数 | 已翻译 | 说明 |
| --- | ---: | ---: | --- |
| 前端主词典 | 46,448 | 45,940（等效 100%） | 安装器口径 0 键回退；508 键为专名/官方保留词（Artifact/Skill/PR/Diff/Fork 等）/OAuth scope/格式串 |
| 前端覆盖（overrides） | 290 | 290 | 与主词典全量同步，安装时按 ICU 结构过滤 |
| 动态文案 | 51 | 51 | 已对齐 `Token`、`思考强度` 等术语 |
| 桌面壳（菜单/弹窗/托盘） | 1,575 | 1,550（等效 100%） | 官方 `zh-Hans.json` **1,567/1,567 条 100% 原样复用**（含 25 条官方保留英文专名） |
| frame-shell（5.x+ 层） | 1,898 | 1,885（等效 100%） | 英文原文自 JS 提取；剩余 13 键为专名/纯格式串 |

2026-11-24 安装器的 JS 文字规则改为按词法定位字符串字面量（根治「已知限制」里按引号配对扫描的盲区）：
`install-linux.py` 的 `patch_js_text` 不再按引号出现顺序配对，改为照搬 acorn 分词器上下文规则的 JS 词法扫描，
区分注释、字符串、模板与正则字面量并按解码后的值查表；只改查找方式，三份规则表与 Windows 安装器共用、未改动。
以 6.28899.6 实测：994 处真实字面量命中全部正确替换（此前正确 821 处、漏替换 171 处界面文案、另有 19 处落在
更长的英文字符串内部形成中英混排），现在漏替换 0 处、误替换 0 处。代价是 JS 补丁阶段要做的词法扫描：对 6,225 个前端
文件（152 MB）本机实测约 24 秒，此前约 14 秒。验证：以 acorn 8.19 的解析结果为标准答案
逐项比对字面量区间与解码值，官方包 7,085 个 JS 文件零出入（`js-audit.py` 默认跳过含旧式 HTML 注释字样的文件，本版 79 个；
2026-11-27 提交前另行用同一套比对核对，结果一致）；多视角对抗测试累计 218 组用例共 27,082 份语料，
经 V8 判定后真正不一致 0 份（其余 101 份是 V8 不接受的代码、78 份是 acorn 与 V8 切分不同的写法，均按 V8
处理），另用 V8 直接核对了 acorn 解析不了的 119 例。新增 `zh-i18n/work/js-lex-test.py`（179 例加 7 个残缺
输入的单元测试，不需要 Node，已并入干跑验证链第 00 步）、`js-audit.py` 与 `js-ast-dump.js`（以 acorn 为标准
答案审计官方包里的全部 JS，同步新版本后运行）。已经用旧安装器打过补丁的安装目录需要 `reset` 后重新
`install` 才能修正此前漏替换和中英混排的字符串。

2026-11-23 对照官方 APT 最新版 6.28899.6 增量同步：官方前端词典 46,447 → 46,448 键（新增 2、死键 1，存量英文原文零变更）。
新增 `J5MyIE7Qp5`「Sessions don’t use your value for {name}.」（Code 标签页环境变量设置的警告）与 `okFGaP/EGD`
「Some sessions aren’t listed. …」（会话恢复列表末尾的说明，取代旧键 `YpBEFNvVe1`「Older sessions aren’t listed. …」）；
桌面壳 1,575 键、动态文案 51 键、overrides 290 键、frame-shell 1,898 键均零变化，官方壳 `zh-Hans.json` 1,567 键与我们的
译文零差异。官方本版同时修订了非英语翻译的 251 条译文值（前端 238、桌面壳 13；英文原文未变，多为 Legacy / Monitor /
Premium 等术语统一以及标点、敬语调整），逐条对照调用点复核并经对抗验证后修正存量中文 12 条：3 条实义错误
（`C9WGEuJVec`「of」是“3 of 5”徽标里的分隔词却译作「的」，`YXoHk0YjYL`「Power」是用户成熟度分层却译作「电源」，
`ZVNBBAiaLC`「Review behavior for {name}」把 Review 当成动词译作「查看…的行为」），以及 9 条术语一致性修正
（web fetch 统一「网页抓取」、定时任务的「查看指令 / 编辑指令」、「导出用租户 ID」及引用该字段名的说明、「发展中」
层级、「全成本薪酬」、「{serverName} 嵌入应用」等）。独立复核：另写脚本重算五层差异，与仓库报告零出入；安装器的语言
白名单（3 处）、名称映射、locale 映射锚点全部恰好命中；frame-shell 的 1,898 个 id 经 acorn 语法树交叉验证与正则提取
完全一致；JS 规则逐条命中与 6.28899.2 完全相同（276 个文件、精确规则 229 处、文字规则 840 处），没有规则在本版失效，
前端 ion-dist JS 也没有新增未被规则覆盖的硬编码界面文案（桌面壳主进程 JS 里新增的几条硬编码英文提示、
文字规则引擎按引号配对扫描的既有盲区，均不在现有机制覆盖范围内，见「已知限制」）。安装器零改动。新增维护脚本 `zh-i18n/work/verify-chain.sh`，把干跑验证链
固化为一条命令。验证：五层词典全量校验与术语审计通过 → 干跑验证链（部署校验 manifest 49 文件字节+SHA-256 全过 →
重复安装幂等 → reset 恢复后与官方原版逐字节一致 → 从原版重装逐字节可复现）。

2026-11-21 全量逐条精校与 Agent/官方术语统一：
- **官方译文 100% 原样复用**：升级 `install-linux.py` 与 `zh-i18n/work/common5x.py` 的 `struct_ok()` 为完整 ICU MessageFormat 语法校验器（兼容中文省略 `one` 分支与直写 `{var}` 的合法复数写法），桌面壳原样并入全部 **1,567/1,567 条**官方 `zh-Hans.json`（补齐此前因复数校验过严跳过的 94 条，并额外检出修复 1 条原脚本漏报的运行期变量名错写 Bug `QD+x5dnPVC`）；跨层同原文 70 条直接锁定复用官方译文；全库人称对齐官方统一为「您」（仅用户发给 Claude 的第一人称示例提示词保持「你」）。
- **全量 50,261 键 + 887 条 JS 硬编码规则逐条对照英文精校**：拆分 165 个批次（高优 Agent/术语/跨层 A 组 54 批 + 通用界面 B 组 111 批）全覆盖核对，累计修正 **4,435 条**语义错译、串键、多义词误译与术语偏移（含 `CHGpxkyOsd` 串键错译「引导插图」、`g3hx72ya32` 错译「充分规划知识」、`E37670` LLM 错译「法学硕士」、`Checks cancelled` 错译「支票已取消」、`+ tax` 反译「含税」、`wall clock` 错译「挂钟」、`/web-setup` 斜杠命令误译、终端光标 `Block` 错译「阻止」、`Background` 后台/背景颠倒、`Canvas LMS` 错译「画布」、`O8rEfJhp62` `Rewind` 错译「快退」、`oUQNLoQUff` 语序错误等），并统一跨层 360 处同英文长句译法；同步精校 `hardcoded.json`、`assets-manifest.json`、`frontend-hardcoded.json`（修正 236 处、清理 4 条脏条目）。
- **术语规范留仓与脚本升级**：沉淀完整规范至 [glossary.md](glossary.md)，升级 `zh-i18n/work/` 下 `common5x.py`、`analyze-diff-5x.py`、`reuse-check-5x.py`、`tm-reuse-5x.py`、`check-batch.py`、`unpack-deb.py`，新增全库术语与质量审计脚本 `audit-glossary.py`（官方壳复用 1,567/1,567、结构失败 0、错别字 0、术语告警 0）。

2026-11-21 对照官方 APT 最新版 6.28899.2 增量同步：官方前端词典 44,218 → 46,447 键（新增 3,588、
死键 1,359）；桌面壳 1,310 → 1,575 键（新增 272、死键 7）；动态文案零变化；overrides 清理死键 10
（300 → 290 键）；frame-shell JS 英文 1,846 → 1,898 键（新增 148、死键 96，存量英文原文零变更；
官方附带 10 语言词典扩充至 1,901 键，仍无中文）。官方壳 `zh-Hans.json` 由 893 大幅扩充至 1,567 键，
按“官方优先”并入结构兼容的 1,448 条（直接补齐新键 261 条、覆写存量 219 条，统一改为「你」人称；
94 条因官方省略复数 `one` 分支或占位符次数差异未采纳）。新译 3,391 条（前端 3,377 + 壳 10 +
frame-shell 4，并行批次全部通过 ICU 变量/分支/富文本标签结构校验）；复用翻译记忆 350 条（含跨层复用
前端新译 71 条至 frame-shell）、Windows 词典 6 条；清理死键 1,472。同步升级 `zh-i18n/work/` 脚本：
`make-batches-5x.py` 按 `BATCH_SIZE` 动态分批与补零编号，`tm-reuse-5x.py` 支持跨层复用已译批次与旧版
`frame-shell-en` 基线并跳过已译批次，`analyze-diff-5x.py` 增加 frame-shell `changed_en` 对比，
`check-batch.py` 增加敬称「您」检查提醒。安装器零改动（6.x 沿用 5.x 资源布局，结构驱动规则自动命中）。
验证：五层词典全量校验通过 → 安装 → 部署校验（manifest 49 文件字节+SHA-256 全过）→ 幂等重装 →
reset 恢复后与官方原版逐字节一致。

2026-11-17 对照官方 APT 最新版 5.11492.5 解包复核与补漏：修复 `install-linux.py` 与提取脚本中
`frame-shell` JS 消息正则未匹配带 `description` 字段条目的问题（1,844 → 1,846 键，补译席位开通弹窗
2 键），并同步修复词典更新后重跑安装器时 `frame-shell.html` 的 `data-catalogs` 指纹刷新逻辑；
复查前端 `zh == en` 条目在 JS 调用点上下文，补译此前误留英文的 17 条界面文案（输入框、作品、
可被发现、可能存在、已印记、签发 ID-JAG、使用者密钥/机密、电子表格、抓取、周期切换及方案卡片等），
统一 2 条 `effort` 术语为「思考强度」，修正 3 条 UUID 占位符多余空格；同步升级 `zh-i18n/work/`
流程脚本（新增 `unpack-deb.py` 与 `common5x.py`，自动获取/解包最新 deb 并消除跨脚本硬编码版本号）。

2026-11-14 对照 5.11492.5 增量同步：官方前端词典 43,833 → 44,218 键（新增 657、死键 272，
存量英文原文零变更）；桌面壳 1,279 → 1,310 键（新增 35、死键 4）；动态文案零变化；
frame-shell JS 英文 1,826 → 1,844 键（新增 49、死键 31）。官方壳 zh-Hans 864 → 893 键，
结构兼容 824 条并入（其中 7 条专名官方改随英文口径，如 Team/Design/Enterprise/Caps Lock）；
官方附带 frame-shell 语言词典裁剪至各 108 键（仅高频键，其余运行时回退 JS 默认英文），
我们保持 1,844 键全量覆盖不受影响。新译 637 条（前端 611 + 壳 6 + frame-shell 20，
并行批次全部通过 ICU 变量/分支/富文本标签结构校验）；复用翻译记忆 73 条、Windows 词典 4 条。
清理死键 307（前端 272 + 壳 4 + frame-shell 31）。安装器零改动（结构驱动规则自动命中，
5.11492.5 安装根仍在 `/usr/lib/claude-desktop`）。验证：安装 → 部署校验（manifest 51 文件
字节+SHA-256 全过）→ 幂等重装 → reset 恢复后与官方原版逐字节一致。

2026-11-12 对照 5.1231.2 增量同步：官方前端词典 42,695 → 43,833 键（新增 1,623、死键 485，
存量英文原文零变更、存量译文结构校验 0 失败）；桌面壳 1,130 → 1,279 键（新增 162、死键 13）；
动态文案零变化。**官方壳新增自带 zh-Hans.json（864 键）**：按"官方优先"将结构兼容的 797 条
并入桌面壳词典（覆盖 749 条存量译文、补齐 48 条新键）；56 条因官方把复数分支简化等
ICU 结构差异未采纳、保留原译文。新译 2,369 条（前端 1,608 + 壳 112 + frame-shell 649，
并行批次全部通过 ICU 变量/分支/富文本标签结构校验）；复用翻译记忆 20 条、Windows 词典 1,174 条
（frame-shell 1,173 + 前端 1）。清理死键 507（前端 485 + 壳 13 + overrides 9）。
安装器新增 frame-shell 词典层支持（见上文 5.x 布局），`Plugins`/`Customize` 等硬编码
文案在本版已进词典键，旧的 Linux 适配规则自然失配、保留以兼容 4.x。

2026-11-10 对照 4.23118.1 增量同步：4.23118.1（2026-11-09，捆绑 Claude Code 2.1.321）
为修复版本——前端 ion-dist.asar 的 JS 与英文资源相对 4.23118.0 **零变化**（仅官方更新了
10 种语言的自带翻译，各语言同样新增的 4 个自动充值条款键本词典此前已译）；桌面壳
app.asar 代码有实质更新（worktree 技能菜单、file index 等），英文词典键与值零变化。
词典仅随官方壳 zh-Hans 微调 1 条译名（会话记录→对话记录），无新增、无死键。

2026-11-06 对照 4.23118.0 解包资源增量同步：官方前端词典 41,771 → 42,695 键（纯新增
1,150、删除 226，英文原文零变更，存量译文全部有效）；新译 1,171 条（前端 1,150 +
桌面壳 21，并行批次全部通过 ICU 变量/分支/富文本标签结构校验，安装器干跑 0 键回退）；
复用官方壳 zh-Hans.json 译名 5 条、Windows 词典 3 条；清理死键 233 个（前端 226 +
壳 3 + overrides 4）；复用译名中 4 条人称统一为您→你。

术语规范详见 [glossary.md](glossary.md)（官方优先复用，对齐官方 `zh-Hans.json` 及 Agent 圈常用语）：
保留 `Artifact`、`Skill`/`Skills`、`Remote Control`、`Agent`/`Subagent`/`Agentic`、`Token`（LLM 计量，认证用「令牌」）、`PR`、`Diff`、`Fork`、`Dispatch`（动词「派发」）、`MCP App`、`Cowork`、`Claude Code` 等专名；统一 `提示词`（LLM）、`钩子`、`工作树`、`思考强度`、`套餐`（订阅）vs `计划模式`/`计划`（Agent 规划）、`沙盒`、`计算机使用`、`对话`/`侧边对话`/`会话`、`对话记录`、`定时任务`、`自动模式`、`自动接受编辑`、`绕过权限`、`回退`、`引导`、`暂存`（Git stash）vs `待提交`/`待提交区`（Git staged）、`讨论串`（评论用「评论串」）、`发现项`、`遥测`、`受阻`（任务态）vs `已阻止`（安全拦截）、`快速输入`、`会话栏`、`运行器` 等，全库统一官方人称「您」。

## 已知限制

- 订阅账号登录时，主界面在线加载 claude.ai 网页，本地语言包与 JS 补丁不覆盖该部分；
  第三方 API/中转模式走本地 ion-dist 前端，汉化完整生效（与 Windows 版一致）。
- 桌面壳主进程（`app.asar` 内 `.vite/build` 的 JS）里的硬编码英文提示不在汉化范围内：安装器对
  `app.asar` 只写入词典、locale 映射与 frame-shell 层。例如 6.28899.6 新增的
  「Claude Code wasn’t started, because …」几条会话无法启动的原因说明仍显示英文。
- 安装器的 JS 文字规则自 2026-11-24 起按词法定位字符串字面量（照搬 acorn 分词器的上下文规则，按解码后的
  值查表），按引号配对扫描的盲区已根治，规则表未改动。边界：只处理 ES 模块代码（前端 `/assets` 下的 JS
  都是模块，旧式 HTML 注释不识别）；预筛假定压缩器只把非 ASCII 字符、引号、反斜杠和斜杠写成转义，
  `work/js-audit.py` 在同步新版本时核对这一前提，不成立会直接报错；遇到残缺输入（未闭合的字符串、注释、
  模板等）会报错中止，不做兜底；acorn 与 V8 切分不同的一类写法按 V8 处理（如异步函数表达式的体之后紧跟
  斜杠）。已经用旧安装器打过补丁的安装目录不会自动修正此前漏替换和中英混排的字符串，需要 `reset` 后
  重新 `install`。
- 恢复（reset）只还原本脚本改动过的文件；`apt remove claude-desktop` 卸载不需要先 reset。
- 在线页面的 DOM 注入翻译（javaht 的 app.asar 深度改法）未移植，保持与 Windows 包相同的
  设计取向。

## 文件

- `install-linux.sh` — 主脚本（bash 编排：提权、环境检查、停进程、调用助手）
- `install-linux.py` — Python 助手（布局检测、asar 重建引擎、词典合并、JS 补丁、备份与
  还原、locale 写入），由主脚本调用，也可单独运行：
  `ZH_RESOURCES=… ZH_BACKUP=… ZH_LANG=… python3 install-linux.py check`
- `language/zh-CN/linux/dictionary.json` — 前端词典（46,448 键全量映射的基础词典）
- `language/zh-CN/linux/desktop-shell-dictionary.json` — 桌面壳词典（1,575 键，官方 zh-Hans 优先并入）
- `language/zh-CN/linux/frame-shell-dictionary.json` — frame-shell 词典（5.x+ 层，1,898 键）
- `language/zh-CN/linux/overrides.json` — 覆盖文案（290 键）
- `language/zh-CN/dynamic/zh-CN.json` — 动态文案（Windows/Linux 通用）
- `language/zh-CN/hardcoded.json`、`frontend-hardcoded.json`、`assets-manifest.json` — JS 规则
  （与 Windows 安装器共用，安装时按当前版本内容重新匹配）
- `zh-i18n/work/` — 维护用同步脚本（`unpack-deb.py` 拉取/解包/清理最新 deb，`analyze-diff-5x.py`
  五层差异分析，`verify-chain.sh` 干跑验证链：JS 词法器单元测试 → install → 部署校验 → 重复安装幂等 →
  reset 逐字节复原 → 从原版重装可复现）；`js-lex-test.py` 是安装器里 JS 词法扫描的单元测试（不需要
  Node，改了安装器的词法扫描后要跑）；`js-audit.py` 与 `js-ast-dump.js` 以 acorn 的解析结果为标准答案
  审计官方安装包里的全部 JS（需要 Node 与 acorn，同步新版本后运行：`ACORN=<acorn 包目录>
  python3 zh-i18n/work/js-audit.py [版本]`）
