import subprocess
import sys
import os
import time
import signal
import socket


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

def main():
    # 获取当前脚本所在目录（项目根目录）
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 路径配置
    backend_dir = os.path.join(root_dir, 'Backend-System')
    frontend_dir = os.path.join(root_dir, 'homes-frontend')
    
    # 确定 Python解释器路径 (优先使用 venv)
    if sys.platform == 'win32':
        python_exe = os.path.join(root_dir, 'venv', 'Scripts', 'python.exe')
    else:
        python_exe = os.path.join(root_dir, 'venv', 'bin', 'python')
        
    if not os.path.exists(python_exe):
        print(f"Warning: 未找到虚拟环境 {python_exe}，将使用系统 Python")
        python_exe = sys.executable

    backend_port = pick_backend_port()
    if backend_port != 5000:
        print(f"Warning: 端口 5000 已被占用，后端将改用端口 {backend_port}")

    frontend_port = pick_frontend_port()
    if frontend_port != 5173:
        print(f"Warning: 端口 5173 已被占用，前端将改用端口 {frontend_port}")

    backend_env = os.environ.copy()
    backend_env["PORT"] = str(backend_port)
    backend_env["HOST"] = "127.0.0.1"

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
