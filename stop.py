import os
import signal
import subprocess
import sys
import time


BACKEND_PORT_RANGE = range(5000, 5011)
FRONTEND_PORT_RANGE = range(5173, 5184)


def run_command(command):
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip()
    except OSError:
        return ""


def get_listening_pids_unix(port):
    output = run_command(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"])
    if not output:
        return set()
    return {int(line.strip()) for line in output.splitlines() if line.strip().isdigit()}


def get_listening_pids_windows(port):
    output = run_command(["netstat", "-ano", "-p", "tcp"])
    pids = set()
    target = f":{port}"
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid = parts[4]
        if local_address.endswith(target) and state == "LISTENING" and pid.isdigit():
            pids.add(int(pid))
    return pids


def get_listening_pids(port):
    if sys.platform == "win32":
        return get_listening_pids_windows(port)
    return get_listening_pids_unix(port)


def get_process_command(pid):
    if sys.platform == "win32":
        output = run_command(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine",
            ]
        )
        return output.strip()
    output = run_command(["ps", "-p", str(pid), "-o", "command="])
    return output.strip()


def is_backend_process(command, root_dir):
    return "Backend-System" in command or command.endswith(" app.py") or "app.py" in command


def is_frontend_process(command, root_dir):
    lowered = command.lower()
    return (
        "homes-frontend" in command
        or "vite" in lowered
        or ("node" in lowered and "5173" in lowered)
        or ("npm" in lowered and "run dev" in lowered)
    )


def terminate_pid(pid):
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


def force_kill_pid(pid):
    if sys.platform == "win32":
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        pass


def stop_group(name, ports, matcher, root_dir):
    matched = {}
    skipped = {}

    for port in ports:
        for pid in get_listening_pids(port):
            if pid in matched or pid in skipped:
                continue
            command = get_process_command(pid)
            if matcher(command, root_dir):
                matched[pid] = {"port": port, "command": command}
            else:
                skipped[pid] = {"port": port, "command": command}

    if not matched:
        print(f"[{name}] 未发现可关闭的进程")
        return

    print(f"[{name}] 找到 {len(matched)} 个进程")
    for pid, info in matched.items():
        print(f"  - PID {pid} 端口 {info['port']}")
        terminate_pid(pid)

    time.sleep(1.0)

    for pid in list(matched):
        if get_process_command(pid):
            print(f"  - PID {pid} 未退出，强制结束")
            force_kill_pid(pid)


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    print("=" * 50)
    print("正在关闭前后端服务...")
    print("=" * 50)
    stop_group("后端", BACKEND_PORT_RANGE, is_backend_process, root_dir)
    stop_group("前端", FRONTEND_PORT_RANGE, is_frontend_process, root_dir)
    print("=" * 50)
    print("关闭完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
