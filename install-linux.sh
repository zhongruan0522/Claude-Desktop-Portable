#!/usr/bin/env bash
# ============================================================================
#  Claude Desktop 简体中文汉化脚本（官方 APT 版 Linux）
#
#  适用于通过官方 apt 源安装的 Claude Desktop（默认 /usr/lib/claude-desktop）。
#  同时支持 4.x（前端打包于 ion-dist.asar、桌面壳词典在 app.asar 内）与
#  3.x（ion-dist 明文目录）两种资源布局，自动识别。
#  语言包：language/zh-CN（Windows 版基础上按 Linux 版校对合并 + 新翻译
#  约 4,850 个键；前端覆盖约 97%，桌面壳 100%，动态文案 100%）。
#
#  用法：
#    sudo ./install-linux.sh                 # 安装/更新汉化（Claude 升级后重跑即可）
#    sudo ./install-linux.sh check           # 查看汉化状态
#    sudo ./install-linux.sh reset           # 恢复英文原版（保留应用）
#    sudo ./install-linux.sh --set-locale    # 安装并把用户 locale 写为 zh-CN
#    ./install-linux.sh --resources 目录 …   # 指定非默认资源目录（免 sudo 时自动提权）
#
#  说明：
#    * 修改 /usr/lib/claude-desktop 需要 sudo；脚本会自动请求提权。
#    * 需要 python3（Debian/Ubuntu 桌面自带）；主脚本须与 install-linux.py
#      （Python 助手）与 language 目录同处。
#    * 规则按内容匹配、不锁文件名；Claude 升级后重跑本脚本，词典自动与
#      新版英文资源合并，新增键暂以英文显示。
#    * 安装后启动 Claude，从头像/用户菜单进入“语言”选择“简体中文”。
#      订阅模式在线加载 claude.ai 的部分不受本地语言包影响；第三方
#      API/中转模式完整生效。
# ============================================================================
set -euo pipefail

ORIGINAL_ARGS=("$@")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANG_DIR="${SCRIPT_DIR}/language/zh-CN"
HELPER="${SCRIPT_DIR}/install-linux.py"
RESOURCES="${CLAUDE_RESOURCES:-/usr/lib/claude-desktop/resources}"
SET_LOCALE=0
COMMAND="install"

while [ $# -gt 0 ]; do
  case "$1" in
    install|reset|check) COMMAND="$1" ;;
    --set-locale) SET_LOCALE=1 ;;
    --resources) shift; RESOURCES="${1:?--resources 需要一个目录参数}" ;;
    --lang-dir) shift; LANG_DIR="${1:?--lang-dir 需要一个目录参数}" ;;
    -h|--help) sed -n '3,24p' "$0" | sed 's/^# \{1,2\}//'; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
  shift
done

APP_DIR="$(dirname "$RESOURCES")"
BACKUP_DIR="${APP_DIR}/.zh-CN-backup"

fail() { echo "错误: $*" >&2; exit 1; }

# ---------- sudo ----------
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || fail "当前不是 root 且系统没有 sudo。请以 root 运行本脚本。"
  echo "需要 root 权限修改 ${APP_DIR}，正在请求 sudo…"
  exec sudo -E env CLAUDE_RESOURCES="${CLAUDE_RESOURCES:-}" "$0" "${ORIGINAL_ARGS[@]}"
fi

# ---------- 环境检查 ----------
# 4.x 前端打包在 ion-dist.asar；3.x 为明文 ion-dist/ 目录。两种布局均支持。
if [ -f "${RESOURCES}/ion-dist.asar" ] || [ -f "${RESOURCES}/ion-dist/i18n/en-US.json" ]; then :; else
  fail "未找到 ${RESOURCES}/ion-dist.asar（4.x）或 ${RESOURCES}/ion-dist/i18n/en-US.json（3.x）。请确认已通过官方 apt 源安装 Claude Desktop；解包/自定义安装可用 --resources 指定资源目录。"
fi
[ -f "${RESOURCES}/app.asar" ] || fail "未找到 ${RESOURCES}/app.asar"
[ -f "${LANG_DIR}/linux/dictionary.json" ] || fail "未找到语言包 ${LANG_DIR}/linux/dictionary.json。脚本须与 language 目录同处（或用 --lang-dir 指定）。"
[ -f "${HELPER}" ] || fail "未找到助手 ${HELPER}。脚本须与 install-linux.py 同目录。"

if command -v python3 >/dev/null 2>&1; then
  RUNNER="python3"
else
  fail "未找到 python3，请先安装：sudo apt install python3"
fi

stop_claude() {
  if pgrep -x claude-desktop >/dev/null 2>&1; then
    echo "· 正在退出 Claude…"
    pkill -x claude-desktop 2>/dev/null || true
    for _ in 1 2 3 4 5; do pgrep -x claude-desktop >/dev/null 2>&1 || break; sleep 1; done
    pkill -9 -x claude-desktop 2>/dev/null || true
  fi
}

run_helper() {
  if ! ZH_RESOURCES="$RESOURCES" ZH_BACKUP="$BACKUP_DIR" ZH_LANG="$LANG_DIR" \
      "$RUNNER" "$HELPER" "$1"; then
    fail "助手运行失败（模式: $1）"
  fi
}

apply_locale() {
  command -v python3 >/dev/null 2>&1 || { echo "· 跳过 locale 写入（需要 python3）"; return; }
  local user="${SUDO_USER:-}"
  [ -z "$user" ] || [ "$user" = "root" ] && { echo "· 跳过 locale 写入（未识别到真实用户）"; return; }
  local home_dir cfg
  home_dir="$(getent passwd "$user" | cut -d: -f6)"
  cfg="$home_dir/.config/Claude/config.json"
  echo "· 写入 locale=zh-CN → $cfg"
  # 以目标用户身份运行；py 文件由当前(root) shell 打开后经 stdin 传入，
  # 目标用户无须读取脚本所在目录
  if ! sudo -u "$user" "$RUNNER" - set-locale "$cfg" < "$HELPER"; then
    echo "· locale 写入失败（不影响已完成的汉化）"
  fi
}

case "$COMMAND" in
  install)
    stop_claude
    run_helper install
    if [ "$SET_LOCALE" -eq 1 ]; then apply_locale; fi
    ;;
  reset)
    stop_claude
    run_helper reset
    ;;
  check)
    run_helper check
    ;;
esac
