# Linux（官方 APT 版）汉化说明

适用于通过 Anthropic 官方 apt 源（`downloads.claude.ai/claude-desktop/apt/stable`）安装的
Claude Desktop，安装目录 `/usr/lib/claude-desktop`。安装器**自动识别 4.x / 3.x 两种资源布局**，
已在 **4.16336.0（amd64，asar 布局）** 与 **3.6556.2（amd64，明文目录布局）** 上完整验证：
安装 → 全量校验 → 幂等重装 → 升级检测 → 恢复后与官方原版**逐字节一致**。

## 4.x 布局（4.29.0 起）

- 前端整体打包进 `resources/ion-dist.asar`（4,500+ 条目，全条目 SHA-256 integrity）：
  词典 `i18n/*.json`、动态文案 `i18n/dynamic/*.json`、JS 资源 `assets/v1/*.js`。
- 桌面壳词典移入 `app.asar` 内 `resources/i18n/<locale>.json`（原 resources 顶层
  `en-US.json`/`zh-CN.json` 不复存在）。
- 汉化方式：安装器在 asar 内新增 `zh-CN` 词条、按内容规则就地补丁 JS、重建 asar
  并重算全部 integrity，重建后自检（逐条目 SHA-256 比对）通过才落盘；`reset` 整档还原。

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

## 覆盖率（Linux 4.16336.0，2026-11-05 全量同步）

| 层 | 键数 | 已翻译 | 说明 |
| --- | ---: | ---: | --- |
| 前端主词典 | 41,771 | 41,322（98.9%，等效 100%） | 安装器口径 0 键回退；其余 449 键为专名/OAuth scope/格式串（Google Play、CI、{kb}KB、证书块等），按原样保留英文 |
| 前端覆盖（overrides） | 313 | 313 | 安装时按当前版英文资源过滤 |
| 动态文案 | 51 | 51 | |
| 桌面壳（菜单/弹窗/托盘） | 1,112 | 1,097（98.7%，等效 100%） | 其余 15 键为 Claude、{title}: {value} 等专名/格式串，保留英文 |

2026-11-05 对照 4.16336.0 解包资源增量同步：官方前端词典 39,482 → 41,771 键（纯新增
3,715、删除 1,426，英文原文零变更，存量译文全部有效）；新译 3,779 条（前端 3,712 +
桌面壳 65 + 动态 2，并行批次全部通过 ICU 变量/分支/富文本标签结构校验，安装器干跑
0 键回退）；复用官方壳新自带 zh-Hans.json 译名 114 条、Windows 词典 3 条；清理死键
1,463 个（前端 1,426 + 壳 14 + overrides 23）；跨批次统一人称（您→你，282 条）与
术语（计划任务/例行程序/快速输入，24 条），修复 12 条嵌套 ICU 结构。

术语沿用 Windows 包：
作品（Artifacts）、技能（Skills）、思考强度（Effort）、工作树（worktree）、运行器（runner）、
会话栏（Session Rail）、定时任务（routine / scheduled task，官方已将 Routines 更名为
Scheduled tasks，两者统一译作定时任务）、快速输入（Quick Entry）、
远程控制（Remote Control）等；保留 Claude、Cowork、Claude Code、Inventory、P/S 等专名与配置值。

## 已知限制

- 订阅账号登录时，主界面在线加载 claude.ai 网页，本地语言包与 JS 补丁不覆盖该部分；
  第三方 API/中转模式走本地 ion-dist 前端，汉化完整生效（与 Windows 版一致）。
- 恢复（reset）只还原本脚本改动过的文件；`apt remove claude-desktop` 卸载不需要先 reset。
- 在线页面的 DOM 注入翻译（javaht 的 app.asar 深度改法）未移植，保持与 Windows 包相同的
  设计取向。

## 文件

- `install-linux.sh` — 主脚本（bash 编排：提权、环境检查、停进程、调用助手）
- `install-linux.py` — Python 助手（布局检测、asar 重建引擎、词典合并、JS 补丁、备份与
  还原、locale 写入），由主脚本调用，也可单独运行：
  `ZH_RESOURCES=… ZH_BACKUP=… ZH_LANG=… python3 install-linux.py check`
- `language/zh-CN/linux/dictionary.json` — 前端词典（41,771 键全量映射的基础词典）
- `language/zh-CN/linux/desktop-shell-dictionary.json` — 桌面壳词典（1,112 键）
- `language/zh-CN/linux/overrides.json` — 覆盖文案（313 键）
- `language/zh-CN/dynamic/zh-CN.json` — 动态文案（Windows/Linux 通用）
- `language/zh-CN/hardcoded.json`、`frontend-hardcoded.json`、`assets-manifest.json` — JS 规则
  （与 Windows 安装器共用，安装时按当前版本内容重新匹配）
