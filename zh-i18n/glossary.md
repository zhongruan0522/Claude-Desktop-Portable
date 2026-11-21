# Claude Desktop Linux 汉化术语与校对规范

> 本规范适用于本仓库维护的 Linux 全量五层词典（`language/zh-CN/linux/{dictionary,overrides,desktop-shell-dictionary,frame-shell-dictionary}.json`、`language/zh-CN/dynamic/zh-CN.json`）以及 JS 硬编码规则（`hardcoded.json`、`frontend-hardcoded.json`、`assets-manifest.json`）。后续版本增量同步与校对请统一以本文档与 `zh-i18n/work/audit-glossary.py` 为准。

---

## 一、最高原则：官方优先、直接复用

1. **官方桌面壳 `zh-Hans.json` 全量原样复用**：
   - `app.asar:/resources/i18n/zh-Hans.json` 提供的全部官方简体中文条目直接原样并入桌面壳词典（零改动，含官方人称「您」、官方保留英文专名及官方中文复数简化写法）。
   - `install-linux.py` 与 `zh-i18n/work/common5x.py` 的 `struct_ok()` 已升级为完整 ICU MessageFormat 校验器，兼容中文省略 `one` 分支或直写 `{var}` 的合法复数写法。
2. **跨层同原文复用**：前端、`frame-shell`、`dynamic` 中与官方 `zh-Hans.json` 英文原文完全一致且无语境歧义的条目，直接复用官方译文。
3. **全库人称对齐官方**：
   - 界面/系统面向用户的全部文案统一使用官方人称 **`您`**（不再把官方「您」改为「你」）。
   - **唯一例外**：用户发给 Claude 的第一人称示例提示词（如 `I want... First ask me to point you at...` / `Hey Claude, could you...`，其中 `you` 指代 Claude 本人）保留 **`你`**。
   - 严禁误改词中字（如「迷你」不可误作「迷您」），严禁使用「您们」。

---

## 二、官方既定术语（全库对齐 `zh-Hans.json`）

| 英文原文 | 规范译法 | 语境区分与禁用词 |
| :--- | :--- | :--- |
| `Artifact` / `Artifacts` | 保留 **`Artifact`** / **`Artifacts`** | 禁用「作品」「制品」「工件」「产物」 |
| `Skill` / `Skills` | 保留 **`Skill`** / **`Skills`** | 仅指 Claude Skill 功能/对象；人类通用技能（如招聘要求、熟练度）仍译「技能」 |
| `Remote Control` | 保留 **`Remote Control`** | 禁用「远程控制」 |
| `Cowork` / `Claude Code` / `Code tab` / `Claude Design` / `Claude Tag` | 保留专名（`Code 标签页`、`Code 会话`） | 保持原名不译 |
| `Token` | LLM 计量保留 **`Token`**；认证/凭据用 **`令牌`** | 严禁把 LLM 输入/输出/缓存 Token 译作「令牌」「词元」或小写 `token` |
| `Prompt` | LLM 语境用 **`提示词`**；UI 弹窗/询问用 **`提示`** | `System prompt`=系统提示词、`Prompt cache`=提示词缓存、`Prompt injection`=提示词注入 |
| `Hook` / `Hooks` | **`钩子`** | 如「工作树钩子」「模型切换钩子」；文章开场白 hook 除外 |
| `Worktree` | **`工作树`** | 命令行如 `git worktree list`、`skip-worktree` 保持原样 |
| `Effort` | **`思考强度`** | 禁用「思考深度」「推理强度」「投入度」「力度档位」 |
| `Plan`（订阅计费） | **`套餐`** | 禁用「计划」「方案」，与 Agent 计划模式彻底区分 |
| `Sandbox` | **`沙盒`** | 禁用「沙箱」 |
| `Computer use` | **`计算机使用`** | 禁用「电脑操作」 |
| `Quick Entry` | **`快速输入`** | — |
| `Chat` / `Conversation` / `Side Chat` / `Session` | `Chat`/`Conversation`=**`对话`**、`Side Chat`=**`侧边对话`**、`Session`=**`会话`** | 禁用「旁支聊天」「侧边聊天」；除指第三方聊天软件外统一以「对话」替代「聊天」 |
| `Transcript` | **`对话记录`** | 禁用「转录」「会话记录」；真实语音转写保留「转写文本」，会议记录保留「会议记录」 |
| `Memory` | AI 记忆=**`记忆`**；RAM 内存=**`内存`** | 严格按语境区分 |
| `Scheduled task` / `Routine` | **`定时任务`** | 禁用「例行程序」「计划任务」；普通英语 routine 保持「常规/日常」 |
| `Auto mode` / `Bypass permissions` | **`自动模式`** / **`绕过权限`** | — |
| `Connector` / `Plugin` / `Extension` | **`连接器`** / **`插件`** / **`扩展程序`**（紧凑短语可用 **`扩展`**） | — |
| `Account` | **`账户`** | 禁用「账号」「帐号」「帐户」；`account executive` 保持「客户经理」 |
| `Dictation` | **`听写`** | 禁用「语音输入」 |
| `Repository` / `Workspace` / `Marketplace` / `Directory` | **`仓库`** / **`工作区`** / **`市场`** / **`目录`** | — |
| `SSH agent` / `Git origin` | **`SSH 代理`** / **`origin`**（或 **`Git 源`**） | Web/iframe `origin` 译「来源」 |
| `Pin` / `Unpin` | 列表/文件夹/对话=**`置顶`/`取消置顶`**；Git origin=**`锁定`/`重新锁定`**；任务栏=**`固定`/`取消固定`** | 按语境区分 |
| `Dismiss` / `Share` / `Blocked`（安全拦截） | **`关闭`** / 协作权限 **`共享`**、外发 **`分享`** / **`已阻止`** | — |

---

## 三、项目选定 Agent / Coding / 产品术语（官方未覆盖项）

| 英文原文 | 规范译法 | 语境区分与禁用词 |
| :--- | :--- | :--- |
| `Agent` / `Subagent` / `Agentic` | 保留 **`Agent`** / **`Subagent`** / **`Agentic`** | 禁用「智能体」「代理」「子智能体」「子代理」（SSH agent 保持「SSH 代理」） |
| `Plan mode` / `Plan`（Agent 规划） | **`计划模式`** / **`计划`** | 与订阅「套餐」彻底隔离 |
| `Blocked`（Agent 任务/会话状态） | **`受阻`** / **`已受阻`** | 与安全策略拦截「已阻止」彻底区分 |
| `Steer` | **`引导`** | 如「引导会话…」「跟进并引导」 |
| `Accept edits` | **`自动接受编辑`** | 禁用单独「接受编辑」 |
| `Rewind` | **`回退`** | 禁用「快退」 |
| `Extended thinking` / `Adaptive thinking` | **`扩展思考`** / **`自适应思考`** | 禁用「深入思考」指代 Extended thinking |
| `MCP App` / `MCP Apps` | 保留 **`MCP App`** / **`MCP Apps`** | 禁用「MCP 应用」 |
| `Pull Request` / `PR` | **`PR`** | 禁用「拉取请求」及小写 `pull request` |
| `Diff` | 保留 **`Diff`** | 仅指代码差异；普通英语 difference 保持「差异/区别」 |
| `Stash`（Git 储藏） | **`暂存`** | 如「暂存更改」「暂存列表」「已暂存」 |
| `Staged`（Git index 待提交） | **`待提交`** / **`待提交区`** | 与 `Stash = 暂存` 严格区分，避免同句撞词 |
| `Fork`（会话分叉） | 保留 **`Fork`** | 禁用「分叉」「复刻」「派生」 |
| `Dispatch` | 功能名保留 **`Dispatch`**，动词译 **`派发`** | 禁用「调度」「发送」「《Dispatch》」 |
| `Thread`（消息/讨论串） | **`讨论串`**（评论作 **`评论串`**） | 严禁译作「线程」 |
| `Findings` | **`发现项`** | 禁用「调查结果」指代代码/安全扫描发现 |
| `Telemetry` | **`遥测`** | 禁用「诊断数据」 |
| `Duplicate`（操作动词） | **`创建副本`** | 与 `Copy = 复制` 彻底区分；名词 duplicates 仍译「重复项」 |
| `Output style` | **`输出风格`** | 禁用「输出样式」 |
| `Monitor`（后台事件监控功能） | **`监控器`**（动词 **`监控`**） | 硬件显示器仍译「显示器」 |
| `Ready for review` | **`待审查`** | 禁用「可审查」「可供审阅」 |

---

## 四、通用校对红线

1. **零错别字**：统一使用「撤销」（禁「撤消」）、「账单」（禁「帐单」）、「账户」（禁「账号」「帐号」「帐户」）。
2. **避免常见机翻陷阱**：Canvas LMS（教育平台）保持 `Canvas` 不译「画布」；`background` 后台任务不译「背景」；`active` 生效中不译「主动」；macOS `Option` 键不译「选项」；`egress` 统一「出站」不译「出口」；`brief` 简报不译「简介」；`top` 热门/常用不译「顶级」。
3. **排版与 ICU 安全**：中英文与数字间保留单空格（标点紧邻处不加空格）；全角中文标点一致；严格通过 `common5x.struct_ok()` 校验。
