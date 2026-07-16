import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import settings as settings_api
from app.api import studio as studio_api
from app.api import usage as usage_api
from app.api import voices as voices_api
from app.db import init_db


def get_bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


WEB_DIR = get_bundle_root() / "web"


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="声绘魔法 / VoiceCanvas")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Starlette 对未捕获异常默认返回纯文本响应，前端 fetch().json() 解析会
        # 直接抛出难以理解的 SyntaxError；这里统一兜底为 JSON，保证前端始终能读到 detail。
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(settings_api.router)
    app.include_router(voices_api.router)
    app.include_router(studio_api.router)
    app.include_router(usage_api.router)

    # 注意：StaticFiles 挂载在 "/" 会捕获所有未匹配路径，之后的路由/挂载都是巧合覆盖到的死路由。
    # 后续新增的 API 路由（app.include_router(...) 等）必须写在这行之前注册，否则会被静默 404。
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")
    return app


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_server(app: FastAPI, port: int) -> None:
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


_APPLE_LANGUAGES_ENV_FLAG = "VOICEMAX_APPLE_LANGUAGES_SET"


def _force_chinese_native_menu() -> None:
    """把原生右键菜单（剪切/拷贝/粘贴等）固定为简体中文。

    进程内运行期通过 `NSUserDefaults.setObject_forKey_` 动态写入
    `AppleLanguages` 对 WebKit/AppKit 的本地化解析不生效（该解析在框架加载
    的更早阶段已经完成）。唯一可靠的做法是在进程刚启动、任何 Cocoa/WebKit
    框架被触碰之前，通过 `-AppleLanguages` 命令行参数指定语言——这是
    NSUserDefaults 优先级最高的"参数域"，Foundation 会直接扫描进程的原始
    argv 读取它，不受 Python 自身参数解析影响（因为这些参数被放在模块名
    /可执行文件之后，Python 只会当作普通脚本参数忽略，不影响进程真实的
    argv 内容）。

    因此这里用同一个解释器/可执行文件自我重新执行一次，附带该参数。
    `-AppleLanguages` 必须紧接在可执行文件之后、早于 `-m` 或脚本路径，
    Foundation 才能在框架加载前正确读取语言偏好。
    声绘魔法是纯中文界面的产品，直接固定为简体中文，不做系统语言探测。
    用环境变量标记避免重复重启造成死循环。
    """
    if sys.platform != "darwin":
        return
    if os.environ.get(_APPLE_LANGUAGES_ENV_FLAG) == "1":
        return
    os.environ[_APPLE_LANGUAGES_ENV_FLAG] = "1"

    apple_languages_args = ["-AppleLanguages", "(zh-Hans-CN, zh-Hans, zh_CN)"]
    if getattr(sys, "frozen", False):
        argv = [sys.executable, *apple_languages_args]
    elif len(sys.argv) > 0 and Path(sys.argv[0]).name == "run.py":
        argv = [sys.executable, *apple_languages_args, sys.argv[0]]
    else:
        argv = [sys.executable, *apple_languages_args, "-m", "app.main"]

    try:
        os.execv(sys.executable, argv)
    except OSError:
        logger.warning("重启进程以固定右键菜单语言失败，将使用系统默认语言", exc_info=True)


def _restore_native_context_menu() -> None:
    """还原文本框右键菜单为系统标准菜单（剪切/拷贝/粘贴/全选等）。

    pywebview 在 macOS 上默认会在 `debug=False`（生产模式）时于
    `willOpenMenu_withEvent_` 中清空右键菜单的全部条目，只为隐藏 "Reload/
    Inspect Element" 等浏览器专属项，代价是标准编辑菜单也被一并清空，
    右键点击文本框时只剩下系统自动补上的"自动填充/服务"两项。
    若改用 `webview.start(debug=True)` 虽能恢复菜单，但会同时打开
    Web Inspector 并在右键菜单中加入"检查元素"，不适合面向普通用户的正式应用。
    这里改为直接跳过菜单清空逻辑，仅恢复标准编辑菜单，不开启开发者工具。
    """
    if sys.platform != "darwin":
        return
    try:
        from webview.platforms import cocoa

        cocoa.BrowserView.WebKitHost.willOpenMenu_withEvent_ = lambda self, menu, event: None
    except Exception:
        logger.warning("恢复系统右键菜单失败，将使用 pywebview 默认行为", exc_info=True)


def main() -> None:
    _force_chinese_native_menu()

    import webview

    _restore_native_context_menu()

    init_db()
    app = create_app()
    port = find_free_port()

    server_thread = threading.Thread(target=run_server, args=(app, port), daemon=True)
    server_thread.start()
    time.sleep(0.5)

    webview.create_window("声绘魔法", f"http://127.0.0.1:{port}")
    webview.start()


if __name__ == "__main__":
    main()
