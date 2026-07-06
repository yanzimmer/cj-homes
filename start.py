import subprocess
import sys
import os
import time
import signal
import socket
import shutil

from version_helper import resolve_backend_app_version


BACKEND_REQUIRED_MODULES = ("flask", "flask_cors", "flasgger", "jwt")


def pick_backend_port(start_port=5000, max_port=5010):
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"未找到可用端口（尝试范围: {start_port}-{max_port}）")


def pick_frontend_port(start_port=5173, max_port=5183):
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"未找到可用前端端口（尝试范围: {start_port}-{max_port}）")


def get_lan_ip():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    finally:
        probe.close()
    return "127.0.0.1"


def _iter_python_candidates(root_dir):
    candidates = []

    if sys.platform == 'win32':
        venv_python = os.path.join(root_dir, 'venv', 'Scripts', 'python.exe')
    else:
        venv_python = os.path.join(root_dir, 'venv', 'bin', 'python')
    candidates.append(venv_python)

    configured_python = os.environ.get('PYTHON_EXE', '').strip()
    if configured_python:
        candidates.append(configured_python)

    for name in ('python3', 'python'):
        resolved = shutil.which(name)
        if resolved:
            candidates.append(resolved)

    for path_dir in os.environ.get('PATH', '').split(os.pathsep):
        path_dir = path_dir.strip()
        if not path_dir:
            continue
        for name in ('python3', 'python'):
            candidates.append(os.path.join(path_dir, name))

    candidates.append(sys.executable)

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        normalized = os.path.abspath(candidate)
        if normalized in seen or not os.path.exists(normalized):
            continue
        seen.add(normalized)
        yield normalized


def _python_can_run_backend(python_exe):
    probe = (
        "import importlib.util, sys\n"
        f"mods = {BACKEND_REQUIRED_MODULES!r}\n"
        "missing = [name for name in mods if importlib.util.find_spec(name) is None]\n"
        "sys.exit(0 if not missing else 1)\n"
    )
    result = subprocess.run(
        [python_exe, '-c', probe],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def pick_python_executable(root_dir):
    for candidate in _iter_python_candidates(root_dir):
        if _python_can_run_backend(candidate):
            return candidate
    raise RuntimeError(
        "未找到可用的 Python 解释器。请确认已安装 Flask、Flask-Cors、flasgger、PyJWT 等后端依赖。"
    )

def main():
    # 获取当前脚本所在目录（项目根目录）
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 路径配置
    backend_dir = os.path.join(root_dir, 'Backend-System')
    frontend_dir = os.path.join(root_dir, 'homes-frontend')
    
    python_exe = pick_python_executable(root_dir)
    print(f"[后端] 使用 Python: {python_exe}")
    backend_app_version, version_source = resolve_backend_app_version(root_dir)

    backend_port = pick_backend_port()
    if backend_port != 5000:
        print(f"Warning: 端口 5000 已被占用，后端将改用端口 {backend_port}")

    frontend_port = pick_frontend_port()
    if frontend_port != 5173:
        print(f"Warning: 端口 5173 已被占用，前端将改用端口 {frontend_port}")

    backend_env = os.environ.copy()
    backend_env["PORT"] = str(backend_port)
    backend_env["HOST"] = "127.0.0.1"
    backend_env["BACKEND_APP_VERSION"] = backend_app_version

    frontend_env = os.environ.copy()
    frontend_env["VITE_API_BASE_URL"] = "/api"
    frontend_env["VITE_API_PROXY_TARGET"] = f"http://127.0.0.1:{backend_port}"
    lan_ip = get_lan_ip()
    frontend_env["VITE_PUBLIC_APP_ORIGIN"] = f"http://{lan_ip}:{frontend_port}"

    processes = []

    try:
        print("="*50)
        print("正在启动房屋租赁管理系统...")
        print("="*50)
        print(f"[版本] 后端版本号将使用: {backend_app_version} ({version_source})")

        # 1. 启动后端
        print(f"[后端] 正在启动 (目录: {backend_dir})...")
        backend_process = subprocess.Popen(
            [python_exe, 'app.py'],
            cwd=backend_dir,
            env=backend_env,
            shell=False  # 直接执行，不通过 shell
        )
        processes.append(('Backend', backend_process))
        print("[后端] 已尝试启动")

        # 2. 启动前端
        print(f"[前端] 正在启动 (目录: {frontend_dir})...")
        npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'
        frontend_process = subprocess.Popen(
            [npm_cmd, 'run', 'dev', '--', '--host', '0.0.0.0', '--port', str(frontend_port), '--strictPort'],
            cwd=frontend_dir,
            env=frontend_env,
            shell=False
        )
        processes.append(('Frontend', frontend_process))
        print("[前端] 已尝试启动")

        print("="*50)
        print("服务启动中。按 Ctrl+C 停止所有服务。")
        print(f"后端地址(仅本机): http://127.0.0.1:{backend_port}")
        print(f"前端地址(本机): http://localhost:{frontend_port}")
        print(f"前端地址(局域网): http://{lan_ip}:{frontend_port}")
        print("="*50)

        # 监控进程状态
        while True:
            time.sleep(1)
            for name, p in processes:
                if p.poll() is not None:
                    print(f"\nError: {name} 进程意外退出 (代码: {p.returncode})")
                    raise KeyboardInterrupt # 触发退出清理

    except KeyboardInterrupt:
        print("\n\n正在停止服务...")
    finally:
        # 清理进程
        for name, p in processes:
            if p.poll() is None:
                print(f"正在停止 {name}...")
                if sys.platform == 'win32' and name == 'Frontend':
                    # Windows 下 npm shell=True 需要 kill 进程树
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(p.pid)], 
                                  stdout=subprocess.DEVNULL, 
                                  stderr=subprocess.DEVNULL)
                else:
                    p.terminate()
        print("所有服务已停止。")

if __name__ == "__main__":
    main()
