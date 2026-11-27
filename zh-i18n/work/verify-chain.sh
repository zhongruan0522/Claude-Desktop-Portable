#!/usr/bin/env bash
# 干跑验证链（只操作 zh-i18n/work/test-run/ 下的副本，不碰真实安装目录）：
#   JS 词法器单元测试 → install → 部署校验 → check → 重复安装（幂等）→ reset → 与官方原版逐字节对比 → 从原版重装（可复现）
# 用法: bash zh-i18n/work/verify-chain.sh [版本]
#   缺省版本取 work/ 下检测到的最高解包版本（common5x.current_ver）；日志与 md5 记录在 zh-i18n/work/test-run/log/
#   任一步失败立即退出（退出码 1）并保留现场；全部通过后删除 resources 副本、仅保留 log/
set -euo pipefail

WORK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$WORK")"
INST="$ROOT/install-linux.py"
if [ $# -gt 0 ]; then
  VER="$1"
else
  VER="$(cd "$WORK" && python3 -c 'import sys; sys.path.insert(0, "."); from common5x import current_ver; print(current_ver())')"
fi
[ -f "$WORK/deb-$VER/usr/lib/claude-desktop/resources/ion-dist.asar" ] || { echo "未找到解包目录 deb-$VER，请先运行 unpack-deb.py" >&2; exit 1; }

RUN="$WORK/test-run"
LOG="$RUN/log"
RES="$RUN/resources"
rm -rf "$RUN"
mkdir -p "$LOG"
export ZH_RESOURCES="$RES"
export ZH_BACKUP="$RUN/.zh-CN-backup"
export ZH_LANG="$ROOT/language/zh-CN"

md5() { md5sum "$RES/ion-dist.asar" "$RES/app.asar" | sed 's#  .*/#  #'; }
step() { local name="$1"; shift; "$@" > "$LOG/$name.log" 2>&1 || { echo "✗ 步骤 $name 失败，日志 $LOG/$name.log："; cat "$LOG/$name.log"; exit 1; }; }

cp -a "$WORK/deb-$VER/usr/lib/claude-desktop/resources" "$RES"
md5 > "$LOG/00-original.md5"
step 00-js-lex-test python3 "$WORK/js-lex-test.py" "$INST"      # 安装器里 JS 词法扫描的单元测试（不需要 Node）
step 01-install python3 "$INST" install
md5 > "$LOG/01-install.md5"
step 02-verify-deploy python3 "$WORK/verify-deploy-5x.py"
step 03-check python3 "$INST" check
step 04-reinstall python3 "$INST" install
md5 > "$LOG/04-reinstall.md5"
step 05-reinstall-again python3 "$INST" install
md5 > "$LOG/05-reinstall-again.md5"
step 06-reset python3 "$INST" reset
md5 > "$LOG/06-after-reset.md5"
step 07-verify-reset python3 "$WORK/verify-reset-5x.py"
rm -rf "$RUN/.zh-CN-backup"
step 08-install-fresh python3 "$INST" install
md5 > "$LOG/08-install-fresh.md5"

FAIL=0
chk() { if cmp -s "$LOG/$1.md5" "$LOG/$2.md5"; then echo "✔ $3"; else echo "✗ $3"; FAIL=1; fi; }
chk 06-after-reset 00-original "reset 恢复后与官方原版 $VER 逐字节一致"
chk 08-install-fresh 01-install "从原版重装与首次安装逐字节一致（可复现）"
chk 05-reinstall-again 04-reinstall "已打补丁树上重复安装幂等"
if cmp -s "$LOG/01-install.md5" "$LOG/04-reinstall.md5"; then
  echo "· 已打补丁树上重装与首装逐字节一致"
else
  echo "· 已打补丁树上首次重装发生一次布局收敛（与首装 md5 不同），再次重装后稳定"
fi
for f in 00-js-lex-test 01-install 02-verify-deploy 03-check 06-reset 07-verify-reset; do echo "--- $f ---"; cat "$LOG/$f.log"; done
if [ "$FAIL" -eq 0 ]; then
  rm -rf "$RES" "$RUN/.zh-CN-backup"
  echo "✔ 干跑验证链全部通过（$VER），已删除 resources 副本，日志保留在 $LOG"
fi
exit "$FAIL"
