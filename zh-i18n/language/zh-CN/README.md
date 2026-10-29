# Claude 简体中文语言包

以 Claude **2.19675.1.0** 的英文资源为基础合并并校对，并按新版界面补充翻译。目前包含前端 32,810 个键、覆盖文案 355 个键、动态文案 49 个键、桌面壳 758 个键。安装时只新增 `zh-CN` 资源，不覆盖原有英文和其他语言文件。

2026-10-08 补充 Claude **2.26454.0.0** 新增的 Cowork 受信任文件夹说明（`3xPFv/Ldgz`）。该文案通过语言包加载，无需硬编码替换；后续安装会自动部署。此项补充不表示已经覆盖新版的全部新增文案。

同日补充“允许导入数据的来源组织”的标题和简短说明（`JWDj9FZ3tB`、`YIm8r9KgW7`）。展开的详细说明暂不翻译。

本次同时准备了 `assets/v1` 中的 **8 个版本校验 JS 覆盖文件**，另有 25 条精确硬编码规则和 862 条经过安全筛选的前端文字规则。`install.cmd` 会在安装时自动部署这些资源、扫描当前版本的前端 JS 并保存原文件，安装完成后可从用户菜单选择“简体中文”。

## 安装与恢复

1. 完全退出 Claude，包括托盘中的进程，然后运行根目录的 `install.cmd`。
2. 安装脚本会复制四层中文资源、应用 8 个版本校验 JS 补丁、25 条精确规则和 862 条安全文字规则、注册 `zh-CN` 桌面语言并保存原文件到 `_repair-backup`。
3. 重新启动 Claude，从头像或用户菜单进入“语言”，选择“简体中文”。
4. 如需撤销汉化而保留应用，运行 `install.cmd /reset`。`uninstall.cmd` 只负责卸载便携应用、AppX 注册、Cowork 服务和缓存，不执行恢复。
5. 若继续手动覆盖语言文件，目标位置见下表；手动方式不会自动保存原文件。

## 在线界面与第三方接入

订阅用户使用 Anthropic 账号登录时，Claude 可能直接在内置窗口中在线加载 `https://claude.ai` 的主界面。聊天、设置和语言选择由网页提供，应用目录里的本地语言文件与 JS 补丁不会覆盖这部分界面；启动后网页还可能把账号语言同步回桌面壳。

第三方 API、中转或自定义端点通常使用应用目录中的本地 `ion-dist` 前端，此时本语言包、语言选择器补丁和硬编码翻译才会生效。因此安装完成后订阅模式仍显示英文属于加载路径差异，不是语言文件没有复制成功。

| 语言包中的文件 | 复制到 |
| --- | --- |
| `zh-CN.json` | `D:\Claude\app\resources\ion-dist\i18n\` |
| 同名 `*.overrides.json` | `D:\Claude\app\resources\ion-dist\i18n\` |
| `dynamic` 中对应语言的 JSON | `D:\Claude\app\resources\ion-dist\i18n\dynamic\` |
| `desktop-shell` 中对应语言的 JSON | `D:\Claude\app\resources\` |
| `assets/v1` 中全部 8 个 JS | `D:\Claude\app\resources\ion-dist\assets\v1\` |

`resources.pri` 及 `resources.scale-*.pri` 是 Windows AppX 的资源索引文件。它们必须放在 `D:\Claude` 根目录，供 AppX 注册、Cowork 和系统资源加载使用，不能移动到 `app`。`plugin-english.txt` 和 `settings-english-keys.txt` 只是分析用的英文键列表，不属于安装包；安装脚本会自动清理旧文件。

`hardcoded.json` 和 `frontend-hardcoded.json` 由安装脚本读取，不直接复制到 Claude 目录；它们只对当前前端 JS 中实际存在的英文字符串进行替换。文字规则只匹配完整引号字符串，并跳过属性名、图标名、枚举值、路径和配置键。

`.overrides.json` 会覆盖主语言文件中的同名文案，因此只复制主文件可能仍会显示旧文案。`dynamic` 文件包含模型选择和思考模式等动态文案。

JS 覆盖文件只适用于本次核对的 **2.19675.1.0** 和原始文件内容。`assets-manifest.json` 记录原文件及覆盖文件的 SHA-256、逐条替换规则和匹配数量。更新 Claude 后不要照搬这些 JS；应重新按新版本匹配。通过安装脚本部署的内容使用 `install.cmd /reset` 恢复原 JSON、JS、`app.asar` 和 AppX 清单。

## 校对原则

- 以较新的 javaht 语言包为覆盖基础，对比 LifeActor 和 good9527 的译文，择优合并并补充人工校对。
- 修正“技巧/技能”“清晰/清除”“重复/复制”等误译，统一作品、技能、钩子和思考强度等术语。
- 保留 Claude、Cowork、Claude Code、模型及字体名称等专名；保留路径、URL、命令、快捷键、配置枚举和示例值，保证能够直接复制使用。
- 对 ICU 消息进行实际语法解析，检查变量、必要分支、数字格式和富文本标签。中文复数允许使用 `other` 分支；英文冠词变量通过空的 ICU 分支消化。
- 本次只准备了 `language` 目录内的覆盖资源。安装脚本会额外更新 `app.asar` 中的桌面语言映射；其余硬编码和在线页面文案仍需针对实际来源单独适配。更新 Claude 后，应重新按新版本英文资源检查新增键。

## good9527 对比更新

2026-10-07 对比 good9527 包与当前版本共有的 15,502 个前端键，选定并优化前端 765 处、桌面壳 1 处，共 766 处不同文案。其中 401 处直接采用其译文，其余结合英文原文、现有术语和实际使用位置重新校对。相同英文的重复键也同步统一；数量不重复计算英语和韩语两套文件。

主要改进包括“复制插件”“自动充值”“标记为已修复”“查看会话记录”“强制终止”，以及 Git 操作、财务指标、成员管理和权限说明。同步生成同名 `.overrides.json`，避免覆盖文案继续使用旧翻译。

未采用其中 25 处丢失变量、必要 ICU 分支或富文本标签的译文；也未采用改坏路径和 URL、残留整段英文、丢失原文步骤或机械直译的内容。以本地当前版本英文资源为准，保留全部 32,807 个前端键。

## CyrusNee 对比更新

2026-10-07 对比 CyrusNee 包与当前版本共有的 22,482 个前端键、613 个桌面壳键和 47 个动态文案键，择优校对和统一 **150 处实质文案**，另修正 **1,029 处中文术语或产品名间距**，合计 **1,179 处**，按键计算。安装包只保留并部署 `zh-CN` 资源，原有其他语言资源继续由 Claude 自身提供。

改进包括正确保留 Pro/Max、Canva、Chrome、PowerPoint、Outline 和 `x-forwarded-email`，修复 `cwd: ~/projects` 路径示例，并改进“设备工具访问权限”“配对码”“需要你的输入”“Cowork 虚拟机包”等。保留作品、技能、钩子和思考强度等现有术语。没有采用 Cowork → 协作者、Authorization → 授权、device-code → 设备代码等不适合产品名称或配置值的翻译；没有采用 ICU 单引号导致变量不再插值的译文。

8 个固定 JS 中共应用 **45 条规则、60 处匹配**：52 处直接硬编码文案、5 处语言选择器默认文案、两处语言白名单和一处中文名称映射；另从本仓库的前端补丁补充了当前版本命中的 persona `zh-CN` 映射规则。路径、状态值、账户变量、命令及跳转逻辑保留原样。

当前版本的第三方模式会在本机处理 `GET/PUT /api/account_profile`，把语言写入本地 `__account_profile`；选择器成功后保存前端语言选择，前端随后请求桌面壳同步语言。因此建议直接沿用原有“用户菜单 → 语言”流程，不必另建保存逻辑或强行修改用户配置目录。详见 [实施分析](../CyrusNee-analysis.md)。

## lijunyu726 对比更新

对比 [lijunyu726/ClaudeDesktop-SimplifiedChinese](https://github.com/lijunyu726/ClaudeDesktop-SimplifiedChinese) 的 2.16120.0 语言包。该项目的 2.16120.0 主语言包比当前 Claude 2.19675.1 少 564 个键，且包含当前版本已经删除的旧键，因此没有整包覆盖。当前版本中仍为英文、且译文明确适用的 4 个文案已择优合并：`Claude on AWS`、`Claude Platform`、`FCF` 和 `group/project`。`P/S`、`PIN`、`Ultracode` 等可能是产品名或操作名称的内容保留原文，避免误译。

## Ann2025001 对比更新

对比 [Ann2025001/Claude-Desktop-zh-CN](https://github.com/Ann2025001/Claude-Desktop-zh-CN) 的补充词典。该项目的主 JSON 与当前版本高度重合，但其中的 `frontend-hardcoded-zh-CN.json` 还覆盖了大量没有 i18n 键的本地界面文字。已筛选其中 862 条纯文字规则，保留当前项目的 Cowork、作品、产品名和配置值术语；安装时只替换带引号的显示文字，并跳过属性名、图标名、枚举值、路径和配置键。

该项目还提供修改 `app.asar`、在线页面 DOM 注入和改写 `Claude.exe` 完整性校验的模式。那些模式会导致 Authenticode 变为 `HashMismatch`，可能使 Cowork 沙箱失效，因此没有纳入本安装脚本。

验证：全部 `zh-CN` JSON 的键完整性、ICU 语法、变量、必要分支、格式和标签检查通过；8 个生成 JS 的语法检查通过，规则匹配数量与清单一致。对生成文件中的实际语言匹配函数进行隔离验证，确认 `zh-CN` 可被接受、`zh-Hans` 能匹配到 `zh-CN`、已保存的中文选择不回退英文，三类前端语言资源路径均有对应文件。“简体中文”名称及交付文件哈希核对通过。实际应用文件未修改，尚未在 Claude 中验证运行界面。

## 来源

- [javaht/claude-desktop-zh-cn](https://github.com/javaht/claude-desktop-zh-cn)，对比版本 `daee457c47594a10a93153456f59328e0eb6fee6`（Release 1.4.11）。MIT 许可见同目录 `LICENSE.javaht.txt`。
- [LifeActor/Claude_zh-CN_LanguagePack](https://github.com/LifeActor/Claude_zh-CN_LanguagePack)，使用其公开的前端和桌面壳中文资源参与对比。
- [good9527/Claude-Desktop-Chinese](https://github.com/good9527/Claude-Desktop-Chinese)，对比版本 `8f6b32e258fe92f55f484819a09e240547630338` 的 `dist/zh-CN.json`。MIT 许可见同目录 `LICENSE.good9527.txt`。
- [Cao-Junqi/Claude-Desktop-3P-Patch](https://github.com/Cao-Junqi/Claude-Desktop-3P-Patch)，择优吸收 Windows 端当前版本可命中的硬编码中文规则；该仓库的旧版本主语言包未直接覆盖当前版本资源。
- [lijunyu726/ClaudeDesktop-SimplifiedChinese](https://github.com/lijunyu726/ClaudeDesktop-SimplifiedChinese)，对比提交 `2b9f6f206f972a01c62325e3725eef76c6ca6162`；吸收当前版本仍缺失的有效译文和在线 UI 加载机制说明。MIT 许可见同目录 `LICENSE.lijunyu726.txt`。
- [Ann2025001/Claude-Desktop-zh-CN](https://github.com/Ann2025001/Claude-Desktop-zh-CN)，对比提交 `59e404d7063bdc39be2382b6f5e15e1bc5e1c474`；吸收安全筛选后的前端硬编码文字规则，未采用其 `app.asar`、在线 DOM 注入和 `Claude.exe` 校验修改。MIT 许可见同目录 `LICENSE.Ann2025001.txt`。
- [CyrusNee/claude-desktop-zh-cn](https://github.com/CyrusNee/claude-desktop-zh-cn)，对比版本 `889b2b4e913b18e43303bf7ce8935358aefd23a1`。译文与补丁按当前版本择优适配；MIT 许可见同目录 `LICENSE.CyrusNee.txt`。
- 本地当前版本的原始英文 JSON 和此前整理的中文资源。

## Linux（官方 APT 版）

2026-10-24 新增 Linux 支持，入口为根目录 `install-linux.sh`，详见 [linux-readme.md](../../linux-readme.md)。
在 Linux 3.6556.2 上：以前端 37,201 键英文资源为基准，沿用本包全部可用译文（含文本回配），
并新翻译约 4,850 个新增键；桌面壳在原有译文基础上吸收官方 zh-Hans.json 并新译 212 键，
覆盖 828/872。全部新译文通过 ICU 变量、分支与富文本标签结构校验。

与 Windows 安装器的差异：Linux 不使用版本锁定的 JS 覆盖文件，改为全部按内容匹配
（语言白名单、名称映射、persona 映射、硬编码规则、862 条文字规则 + 2 条 Linux 适配规则），
Claude 升级后重跑脚本即可自动重新匹配；合并词典时逐键做 ICU 结构校验，原文已变化
（结构不匹配）的旧译文自动回退英文，避免部署损坏的插值。恢复后经全树哈希比对与
官方 deb 解包结果逐字节一致；重建的 app.asar 全部 615 个条目 SHA-256 完整性校验通过。
