# 后端部署指南（非 Docker）

本指南说明如何在不使用 Docker 的情况下部署运行 `Backend-System`。适用于本地开发与传统服务器（Linux/Windows）环境。

## 环境要求

- Python 版本：推荐 3.10–3.12
- SQLite：随 Python 内置，无需单独安装
- 操作系统：Linux、Windows、macOS（生产环境建议 Linux/macOS）

## 目录结构与重要路径

- 代码目录：`Backend-System/`
- 数据库：`Backend-System/sql/hotel.db`
- 静态上传：`Backend-System/static/uploads/`
- 配置文件：`Backend-System/config/notification_config.json`

## 安装依赖

以项目根目录为当前路径（包含 `Backend-System` 的那个目录）。

### Windows（PowerShell）

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
pip install --upgrade pip
pip install flask flask-cors pyjwt
# Windows 生产建议使用 Waitress（Gunicorn 在 Windows 上不理想）
pip install waitress
```

### Linux/macOS（bash）

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install flask flask-cors pyjwt gunicorn
```

## 初始化数据库与配置

项目内置初始化脚本，首次部署必须执行：

```bash
# 以项目根目录为当前路径
python Backend-System/init-scripts/init_hotel_db.py --init --create-default-admin --seed-demo-data
python Backend-System/init-scripts/init_notification_config.py
```

- 默认管理员：`admin / 123456`（创建后请尽快修改密码）
- 如已存在数据，`--seed-demo-data` 会自动跳过插入演示数据

## 启动服务（不使用 Docker）

### 开发模式（单进程）

```bash
python Backend-System/app.py  # 监听 0.0.0.0:5000
```

### 生产模式

- Linux/macOS（推荐 Gunicorn）：

```bash
cd Backend-System
gunicorn --preload -w 3 -b 0.0.0.0:5000 app:app
```

说明：`--preload` 可避免首次启动并发初始化导致的数据库迁移/列添加竞态。

- Windows（推荐 Waitress）：

```powershell
python -c "import sys; sys.path.append('Backend-System'); from app import app; from waitress import serve; serve(app, host='0.0.0.0', port=5000)"
```

## 可选：Nginx 反向代理（非 Docker）

生产环境建议使用 Nginx 将外网端口 80 反向代理至后端 `5000`：

```nginx
server {
  listen 80;
  server_name _;

  location /api/ {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_pass http://127.0.0.1:5000;
  }
}
```

## 登录与接口自检

1) 登录获取令牌：

```bash
curl -s -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

输出包含 `token` 字段。后续请求在请求头中携带：`Authorization: Bearer <token>`。

提示：所有受保护接口会在响应头返回滑动续期令牌：`X-Refreshed-Token` 与 `X-Token-Expires`。

## 常见问题

- 数据库锁冲突（database is locked）：避免并发启动多个进程初始化数据库；生产使用 `gunicorn --preload`；项目已启用 WAL 与 busy_timeout 以降低冲突。
- 修改密钥与令牌有效期：编辑 `Backend-System/common.py` 中 `SECRET_KEY` 与 `JWT_EXPIRATION_DELTA`。
- 更改监听端口：
  - 开发模式改 `app.py` 中 `port=5000`；
  - 生产模式 `gunicorn -b 0.0.0.0:<端口>` 或 Waitress `serve(..., port=<端口>)`。
- 初始化脚本路径问题：确保在项目根目录执行脚本，或使用绝对路径；脚本会自动迁移旧位置配置/数据库到新路径。

如需进一步协助（如生成 `requirements.txt`、添加 Systemd 服务、SSL 配置等），可在本 README 基础上扩展部署方案。
