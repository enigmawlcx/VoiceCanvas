# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(SPECPATH)

# 目标架构：arm64 / x86_64 / universal2；留空则跟随当前解释器架构。
target_arch = os.environ.get("VOICEMAX_TARGET_ARCH") or None

datas = [(str(project_root / "web"), "web")]

for pkg in ("webview", "keyring", "uvicorn", "anyio", "multipart", "imageio_ffmpeg"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas

binaries = []
hiddenimports = collect_submodules("app")
hiddenimports += [
    "app.main",
    "app.api.settings",
    "app.api.studio",
    "app.api.usage",
    "app.api.voices",
    "app.db",
    "app.db.schema",
    "app.db.usage_repo",
    "app.db.projects_repo",
    "app.db.voices_repo",
    "app.services.minimax_client",
    "app.services.voices",
    "app.services.annotate",
    "app.services.polish",
    "app.services.synthesize",
    "keyring.backends.macOS",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "pydub",
    "audioop",
    "imageio_ffmpeg",
]

for pkg in ("webview", "keyring", "uvicorn", "anyio", "multipart", "imageio_ffmpeg"):
    _, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "respx", "test", "tests"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceCanvas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VoiceCanvas",
)

app = BUNDLE(
    coll,
    name="声绘魔法.app",
    icon=str(project_root / "assets" / "VoiceCanvas.icns"),
    bundle_identifier="com.voicecanvas.app",
    info_plist={
        "CFBundleName": "声绘魔法",
        "CFBundleDisplayName": "声绘魔法",
        "NSHighResolutionCapable": True,
        # 不声明这两项时，系统会将本 App 视为仅支持英文（Development Region
        # 默认为 en），导致 WebKit/AppKit 提供的原生 UI（如文本框右键菜单）
        # 始终以英文展示，而不跟随系统语言设置。
        "CFBundleDevelopmentRegion": "zh_CN",
        "CFBundleLocalizations": ["zh-Hans", "zh_CN", "en"],
    },
)
