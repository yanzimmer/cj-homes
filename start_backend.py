import os
import signal
import socket
import subprocess
import sys
import time

from version_helper import resolve_backend_app_version


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


def pick_backend_port(start_port=5000, max_port=5010):
    preferred = os.getenv("PORT")
    if preferred:
        try:
            return int(preferred)
        except ValueError:
            pass

    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"未找到可用端口（尝试范围: {start_port}-{max_port}）")


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "Backend-System")
    python_exe = detect_python(root_dir)
    local_ip = detect_local_ip()
    backend_port = pick_backend_port()
    backend_app_version, version_source = resolve_backend_app_version(root_dir)
    backend_env = os.environ.copy()
    backend_env["PORT"] = str(backend_port)
    backend_env["BACKEND_APP_VERSION"] = backend_app_version

    print("=" * 56)
    print("正在单独启动后端服务...")
    print(f"Python: {python_exe}")
    print(f"目录: {backend_dir}")
    print(f"后端版本: {backend_app_version} ({version_source})")
    print(f"后端监听: 0.0.0.0:{backend_port}")
    print(f"本机访问: http://127.0.0.1:{backend_port}")
    print(f"局域网访问: http://{local_ip}:{backend_port}")
    print("=" * 56)

    processes = [
        subprocess.Popen([python_exe, "app.py"], cwd=backend_dir, env=backend_env, shell=False),
        subprocess.Popen([python_exe, "notification_worker.py"], cwd=backend_dir, env=backend_env, shell=False),
    ]
    try:
        while True:
            time.sleep(1)
            for process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f"后端子进程已退出，退出码: {process.returncode}")
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is not None:
                continue
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
