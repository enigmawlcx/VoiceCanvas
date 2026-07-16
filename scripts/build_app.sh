#!/usr/bin/env bash
set -euo pipefail

# 用法:
#   scripts/build_app.sh [arm64|x86_64|universal2]
# 说明:
#   - 不传参数时跟随当前 Python 解释器架构。
#   - x86_64 会使用独立的 .venv-x86 虚拟环境（需通过 Rosetta 拉取 x86_64 wheels）。
#   - 产物输出到 dist/<arch>/声绘魔法.app，避免不同架构互相覆盖。

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ARCH="${1:-$(uname -m)}"

case "$ARCH" in
  x86_64)
    VENV=".venv-x86"
    RUN_PREFIX=(arch -x86_64)
    ;;
  arm64 | universal2)
    VENV=".venv"
    RUN_PREFIX=()
    ;;
  *)
    echo "未知架构: $ARCH (支持 arm64 / x86_64 / universal2)" >&2
    exit 1
    ;;
esac

if [[ "$ARCH" == "x86_64" ]] && ! /usr/bin/arch -x86_64 /usr/bin/true 2>/dev/null; then
  echo "错误: 当前机器无法运行 x86_64，请先安装 Rosetta 2:" >&2
  echo "  softwareupdate --install-rosetta --agree-to-license" >&2
  exit 1
fi

BASE_PY="$(command -v python3.13 || command -v python3)"

if [[ ! -d "$VENV" ]]; then
  echo "==> 创建虚拟环境 $VENV ($ARCH)"
  "${RUN_PREFIX[@]+"${RUN_PREFIX[@]}"}" "$BASE_PY" -m venv "$VENV"
fi

PY="${RUN_PREFIX[*]:+${RUN_PREFIX[*]} }$VENV/bin/python"
echo "==> 安装依赖 ($ARCH)"
"${RUN_PREFIX[@]+"${RUN_PREFIX[@]}"}" "$VENV/bin/python" -m pip install -q --upgrade pip
"${RUN_PREFIX[@]+"${RUN_PREFIX[@]}"}" "$VENV/bin/python" -m pip install -q -r requirements.txt pyinstaller

if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
  echo "==> 运行测试"
  "${RUN_PREFIX[@]+"${RUN_PREFIX[@]}"}" "$VENV/bin/python" -m pytest -q
else
  echo "==> 警告: 已跳过测试 (SKIP_TESTS=1)" >&2
fi

echo "==> 清理旧构建 ($ARCH)"
rm -rf "build/$ARCH" "dist/$ARCH"

echo "==> 生成应用图标"
"$ROOT/scripts/generate_app_icon.sh"

echo "==> PyInstaller 打包 ($ARCH)"
VOICEMAX_TARGET_ARCH="$ARCH" "${RUN_PREFIX[@]+"${RUN_PREFIX[@]}"}" "$VENV/bin/python" -m PyInstaller \
  --noconfirm \
  --distpath "dist/$ARCH" \
  --workpath "build/$ARCH" \
  VoiceCanvas.spec

echo "==> 完成: dist/$ARCH/声绘魔法.app"
du -sh "dist/$ARCH/声绘魔法.app"
lipo -archs "dist/$ARCH/声绘魔法.app/Contents/MacOS/VoiceCanvas" 2>/dev/null || true
