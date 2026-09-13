"""启动雅思工作台：检查依赖 → 启动服务 → 打开浏览器。

用法：双击 启动.bat，或在项目目录运行：
    venv\\Scripts\\python.exe start.py
"""
import os
import socket
import subprocess
import sys
import threading
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
# 默认只监听本机，避免局域网内他人可调用 /api/open 打开文件；
# 需要手机/平板访问时：双击「手机访问.bat」，或设置环境变量 IELTS_HOST=0.0.0.0 后启动
HOST = os.environ.get("IELTS_HOST", "127.0.0.1")
PORT = int(os.environ.get("IELTS_PORT", "8000"))  # 端口被占用时可用 IELTS_PORT 临时指定
LOCAL_URL = f"http://127.0.0.1:{PORT}"


def lan_ip():
    """探测本机局域网 IP。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


PIP_MIRROR = ["-i", "https://mirrors.aliyun.com/pypi/simple/", "--trusted-host", "mirrors.aliyun.com"]


def ensure_deps():
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import watchdog  # noqa: F401
    except ImportError:
        print("[启动] 正在安装依赖 fastapi / uvicorn / watchdog（国内镜像）…")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", *PIP_MIRROR,
             "fastapi", "uvicorn", "watchdog"]
        )


def main():
    os.chdir(BASE)
    sys.path.insert(0, BASE)
    ensure_deps()
    ip = lan_ip()
    print("[启动] 雅思工作台已启动（按 Ctrl+C 退出）")
    print(f"  本机访问：  {LOCAL_URL}")
    if HOST == "0.0.0.0":
        if ip:
            print(f"  局域网访问：http://{ip}:{PORT}   ← 手机/平板连同一 WiFi 用这个")
    else:
        print("  （手机/平板访问：先设置环境变量 IELTS_HOST=0.0.0.0 再启动）")
    threading.Timer(1.5, lambda: webbrowser.open(LOCAL_URL)).start()
    import uvicorn
    uvicorn.run("app:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
