# CyrusNee 汉化方案与当前便携版的对照

分析日期：2026-10-07。分析对象是 [CyrusNee/claude-desktop-zh-cn](https://github.com/CyrusNee/claude-desktop-zh-cn/tree/889b2b4e913b18e43303bf7ce8935358aefd23a1)，固定提交 `889b2b4e913b18e43303bf7ce8935358aefd23a1`。仓库声明适配 Claude **1.46388.4.0**，本地 AppxManifest 与 app.asar/package.json 对应版本为 **2.19675.1.0**。

结论：沿用当前版本已有的“用户菜单 → 语言”入口和切换流程，补齐两处 `zh-CN` 白名单、简体中文名称和对应的多层 JSON。当前第三方模式在本机处理账户语言接口，无需额外设计本地保存逻辑。CyrusNee 的硬编码处理有必要吸收，因为这些文案不通过主 JSON 翻译。

本次进行了脚本阅读、3,170 个前端 JS 的静态扫描、只读解析 app.asar，以及语言包键和 ICU 结构对比。根据后续择优吸收请求，已更新 `language/zh-CN` 下的语言包，并准备 8 个 JS 覆盖文件。没有执行仓库安装或卸载脚本；没有修改运行中的应用或用户配置。以下验证结果不代表已经完成界面运行验证。

仓库的 [install.ps1](https://github.com/CyrusNee/claude-desktop-zh-cn/blob/889b2b4e913b18e43303bf7ce8935358aefd23a1/install.ps1) 按以下顺序工作：

1. 扫描 `C:\Program Files\WindowsApps\Claude_*`，按目录名称倒序取第一项，使用其 `app\resources`。README 明确声明不支持便携版。
2. 关闭名为 Claude 的进程，通过 `takeown` 和 `icacls` 取得目标文件及 JS 目录的写权限。
3. 复制桌面、前端和动态文案三个 `zh-CN.json`。
4. 在包含语言数组的第一个 `shared-*.js` 或 `index-*.js` 文件内，全局替换完整数组，加入 `zh-CN`。
5. 扫描 JS，执行 23 条精确字符串替换，对修改的 JS 创建 `.zhcn-backup`，然后删除 `*.js.zst`。
6. 将 `%APPDATA%\Claude\config.json` 中的 `locale` 设置为 `zh-CN`。

它部署的三层资源分别是：

| 文件位置，均相对于 `app\resources` | 用途 |
| --- | --- |
| `zh-CN.json` | 桌面壳使用的菜单、提示和桌面设置文案 |
| `ion-dist\i18n\zh-CN.json` | 前端界面主语言包 |
| `ion-dist\i18n\dynamic\zh-CN.json` | 模型选择等动态文案 |

当前前端还会请求 `ion-dist\i18n\zh-CN.overrides.json`。为保持已校对的主文件与覆盖文案一致，适配时应一起准备这个文件；仓库原安装器没有部署它。

语言数组在本地 [shared-2-BaCC514e.js](D:/Claude/app/resources/ion-dist/assets/v1/shared-2-BaCC514e.js) 内有两处，变量分别为 `fg` 和 `bg`。原始数组为：

```js
["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"]
```

仓库将其替换为：

```js
["en-US","zh-CN","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"]
```

当前两处原始数组都能精确匹配，该脚本的全局 `.Replace()` 会覆盖两处。`fg` 用于默认语言匹配；`bg` 用于支持语言判断，也会被语言菜单作为基础列表使用。语言菜单还可在基础列表上加入当前提供的其他语言。补齐 `bg` 对中文选项有直接作用。

不过，当前语言选择器 [c49da61a8-CBee8AL6.js](D:/Claude/app/resources/ion-dist/assets/v1/c49da61a8-CBee8AL6.js) 内的名称映射只包含原有 11 种语言。仓库没有补这个映射，新增选项可能只显示 `zh-CN`。要显示“简体中文”，还应加入：

```js
"zh-CN": {name:"Chinese (Simplified)",localName:"简体中文"}
```

这个选择器还包含 `Search languages`、`No languages found`、`Language`、`1 language found`、`{count} languages found` 五条英文默认文案。它们通过组件翻译回调读取，找不到翻译时使用默认英文；相应的字符串键未出现在当前前端主英文 JSON 中。仓库的 23 条规则也没有覆盖这些默认文案，适配时需要检查组件翻译来源或定点处理，并保留 `{count}`。

进一步追踪后确认：选择器会提交 `PUT /api/account_profile`，但当前第三方模式的协议处理器已在本地实现这个接口。`GET` 返回本地资料，`PUT` 把提交字段合并进本地 `__account_profile`，返回更新结果。因此，这个版本的第三方模式不需要依赖中转服务实现账户语言设置；应优先复用现有接口。

当前 [shared-25-DXU0HC0D.js](D:/Claude/app/resources/ion-dist/assets/v1/shared-25-DXU0HC0D.js) 已有 `data-testid:"user-menu-language"` 菜单项，点击打开语言对话框。这段菜单项没有用 Hybrid 标记隐藏。常规设置项描述中的 `hiddenInHybridOrg: true` 主要涉及设置项列表及搜索，不能据此认定头像菜单中的语言入口也不可用。推荐先使用现有头像或用户菜单中的“语言”，无需为了中文去修改其他隐藏条件。

前端切换成功后，`setLocaleOverride` 通过语言规范化函数接受新语言，并保存本地选择。前端中的 effect 会把当前渲染语言提交给 `window.electronIntl.requestLocaleChange`；桌面壳加载相应 JSON 后持久保存 locale。主进程的 `DesktopIntl.requestLocaleChange` 没有向调用方返回 `act()` 的成功布尔值；若将来开发单独切换逻辑，需要读取切换后的 locale 验证，不能仅凭 Promise 返回就认定成功。沿用现有流程可减少新逻辑，也避免直接猜测配置路径。

实施顺序为：四层中文 JSON 就位 → 两处白名单加入 `zh-CN` → 补“简体中文”名称 → 从现有用户菜单切换 → 检查前端实际请求、桌面 locale 和重启后状态。应由用户明确选择中文，不用安装补丁时强制写 `%APPDATA%` 或 `D:\Claude\data`。

仓库的 23 条硬编码规则在当前版本中全部命中，总计 **37 处，涉及 7 个 JS 文件**：

| 规则范围 | 示例 |
| --- | --- |
| 错误页和按钮 | Go back home、Home、Page not found、Reload、Retry |
| 浏览器扩展提示 | 无法连接扩展、需要登录、账户不同 |
| 页面标题 | Admin settings、Analytics、Create project、Customize、Projects、Recents、Settings、Sign in、Skills、Upgrade、Artifact、Artifacts |
| 标签 | Chat、Code、Audio Description |

匹配到的文件是 `shared-28-DFptrJn_.js`、`shared-25-DXU0HC0D.js`、`shared-29-Dq-RZCx0.js`、`c10f0af0c-lYUAT4Np.js`、`shared-26-Dyl0rRaC.js`、`shared-2-BaCC514e.js`、`shared-7-v3MO7ivC.js`。当前目录没有 `*.js.zst`。

这些替换范围有限。例如，`title:"Settings"` 主要修改路由页面标题，设置页里的字段仍需要各自的 JSON 或组件翻译。同一错误页和扩展提示内还有其他英文段落未被这些规则覆盖。它没有处理 app.asar 内的硬编码，也没有翻译在线页面的所有内容。适配时还应统一现有术语，例如将 Artifact/Artifacts 译为“作品”、Chat 译为“聊天”。

语言包的键覆盖对比如下。“缺少当前键”是用本地当前版本英文资源作基准；“旧键”是仓库有而当前英文资源没有的键，不能抵消缺少的键。

| 层 | 当前键数 | 仓库键数 | 共有键 | 缺少当前键 | 仓库旧键 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 前端 | 32,807 | 25,494 | 22,482 | **10,325** | 3,012 |
| 桌面壳 | 758 | 654 | 613 | **145** | 41 |
| 动态文案 | 49 | 79 | 47 | **2** | 32 |

共有键的结构检查还发现一条前端译文的 ICU 变量不兼容，键为 `2WtTIWx05Q`：

```text
英文：Action ‘{action}’ for extension ‘{extensionId}’ (not yet implemented)
仓库：扩展 '{extensionId}' 的操作 '{action}'（尚未实现）
```

ICU 会将这些 ASCII 单引号包裹的花括号内容作为字面量，因此两个变量没有按原文插值。这一译文不能原样吸收。共有键里另有 22 条长度超过 40、与英文原文相同的文案；其中可能包含技术内容，需要逐条判断，不能仅凭相同就认定是翻译错误。

仓库译文也并非整体优于现有包。例如，现有包将 Shares Out 译为“发行在外股数”、Effort 译为“思考强度”、Beta (3Y) 译为“贝塔系数（3 年）”、Artifacts 译为“作品”；该仓库分别使用“外发份额”“工作量”，后两项保留英文。采用现有包作为基础更适合当前版本。

桌面语言加载也已核对。app.asar 中的 `.vite/build/index.chunk-DVtu79Rf.js` 会枚举 `resources` 目录下的语言 JSON，读取指定语言文件，并通过 `DesktopIntl` IPC 提供初始语言和语言切换。新增有效的 `resources\zh-CN.json`，原则上可被这条桌面加载链识别，不需要仅为注册这个 JSON 文件而改 ASAR。其他 ASAR 硬编码需要按实际位置单独处理。

桌面配置路径来自 Electron 的 `app.getPath("userData")`。本地 [Claude.cmd](D:/Claude/Claude.cmd) 当前通过已注册的 MSIX 和 `shell:AppsFolder` 启动，没有传入 `--user-data-dir D:\Claude\data`，因此不能默认将配置写到 `D:\Claude\data`。第三方模式的本地协议处理器会把 `/i18n/` 请求映射到 `ion-dist`，找不到的资源返回空对象；这说明本地中文资源方案具备加载基础，最终仍需确认实际语言请求和缓存状态。

`app\locales\zh-CN.pak` 用于 Chromium/Electron 的内置文案。Claude 设置页和主界面的大量文本来自应用的前端 JSON、JS 或桌面壳。即使这个 PAK 被加载，也不能替代上述应用资源的翻译。桌面原有的 `zh-Hans.json` 与新增的 `zh-CN.json` 也需要按各自加载链处理，不能只凭它们都表示简体中文就随意改名。

仓库的备份和卸载行为需要按源码理解：它备份修改过的 JS，但复制三个中文 JSON 前没有备份；卸载会删除中文 JSON、从 `.zhcn-backup` 恢复 JS，并把 locale 固定改为 `en-US`。它没有还原原来的 locale、JSON 内容、文件所有权或 ACL。README 关于“所有被覆盖文件均备份”的表述与脚本实现不完全一致。安装器对白名单或配置设置失败只发出警告，最终完成判断主要检查三个 JSON 是否存在，所以安装完成提示也不能作为中文已启用的验证。

已准备的文件与后续覆盖步骤如下：

1. 已按英文原文择优校对 150 处实质文案，并修正 1,029 处间距，合计 1,179 处：前端 1,145、桌面壳 32、动态文案 2。安装方案只部署新增的 `zh-CN` 主文件、覆盖文件、动态文件和桌面壳文件；原有英语、韩语资源保留为 Claude 自身的回退资源。
2. 已在 `language/zh-CN/assets/v1` 准备 8 个 JS：在同一套覆盖文件中同时处理硬编码、语言白名单与中文名称，避免分别覆盖同一 JS 导致补丁互相覆盖。
3. 共 45 条规则、60 处匹配：直接硬编码 52 处、组件默认文案 5 处、白名单 2 处、名称映射 1 处。硬编码沿用并校对仓库原有 23 条规则，再补齐同一错误页及扩展提示里的完整句子；保留路径、URL、状态值和表达式。
4. [assets-manifest.json](D:/Claude/language/zh-CN/assets-manifest.json) 记录每个原文件和补丁文件的 SHA-256、适用版本、规则及匹配数。全部 `zh-CN` JSON 的 ICU 语法、变量、分支、格式、标签和键完整性检查通过；8 个 JS 的语法检查通过。生成文件中的实际语言匹配函数也已隔离验证：接受 `zh-CN`、将 `zh-Hans` 匹配到 `zh-CN`、读取已保存的中文选择、生成正确的资源路径；名称映射及交付哈希核对通过。
5. 按 README 备份并覆盖四层中文 JSON 和 8 个 JS，重启后从现有用户菜单选择“简体中文”。只有文件名和原文件内容与本次版本一致时才使用这些 JS。升级后重新匹配补丁。
6. 实际运行时检查语言菜单、错误提示、设置字段、聊天、Code 和 Cowork 界面，以及重启后的语言保持。覆盖范围包括本次选定的文案，仍不能代表所有在线页面或 ASAR 硬编码都已翻译。

上述语言包和 JS 补丁已准备在 `language` 目录，尚未部署到运行中的应用。中文入口及本地保存链已有静态证据，最终界面效果仍需在覆盖后验证。
