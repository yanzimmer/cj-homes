import os
import signal
import socket
import subprocess
import sys
import time


def detect_python(root_dir):
    if sys.platform == "win32":
        venv_python = os.path.join(root_dir, "venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(root_dir, "venv", "bin", "python")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable


def detect_local_ip():
    ip = "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        pass
    finally:
        s.close()
    return ip


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "Backend-System")
    python_exe = detect_python(root_dir)
    local_ip = detect_local_ip()

    print("=" * 56)
    print("正在单独启动后端服务...")
    print(f"Python: {python_exe}")
    print(f"目录: {backend_dir}")
    print("后端监听: 0.0.0.0:5000")
    print(f"本机访问: http://127.0.0.1:5000")
    print(f"局域网访问: http://{local_ip}:5000")
    print("=" * 56)

    process = subprocess.Popen([python_exe, "app.py"], cwd=backend_dir, shell=False)
    try:
        while True:
            time.sleep(1)
            if process.poll() is not None:
                raise RuntimeError(f"后端进程已退出，退出码: {process.returncode}")
    except KeyboardInterrupt:
        pass
    finally:
        if process.poll() is None:
            if sys.platform == "win32":
                subprocess.call(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                process.send_signal(signal.SIGTERM)
        print("后端服务已停止。")


if __name__ == "__main__":
    main()
