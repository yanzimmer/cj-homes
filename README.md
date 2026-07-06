# cj-homes

`cj-homes` 是一套面向房屋租赁/公寓管理场景的全栈管理系统，用来统一处理房源、租客、入住、合同、维修、采购、仓库以及水电与租金台账等日常业务。

## 项目是做什么的

这个项目主要服务于出租房、公寓或民宿类运营场景，帮助运营人员把原来分散在表格、聊天记录和纸质单据里的工作集中到一个系统里管理。

当前系统已经覆盖的核心能力包括：

- 房间与房源管理
- 租客信息管理
- 入住登记与搬入搬出记录
- 合同模板与合同管理
- 维修报修记录
- 采购与仓库管理
- 水电账单管理
- 租金台账管理
- 公开入住链接 / 公共业务录入链接
- 到期提醒与系统维护配置

## 技术栈

- 前端：Vue 3 + Vite
- 后端：Flask
- 数据库：SQLite
- 部署方式：支持 Docker，也支持传统方式单独启动前后端

## 目录结构

```text
.
├── homes-frontend/      # 前端页面与交互
├── Backend-System/      # Flask 后端接口、数据库初始化与业务逻辑
├── deploy/              # Nginx / Supervisord 部署配置
├── docker-compose.yml   # Docker 编排
├── Dockerfile           # 容器构建
├── start.py             # 启动脚本
└── start_backend.py     # 后端启动脚本
```

## 适合的使用场景

- 自有房源出租管理
- 长租公寓运营
- 民宿/旅居房态与入住管理
- 小团队内部的维修、采购、仓库协同

## 本地启动

### 前端

```bash
cd homes-frontend
npm install
npm run dev
```

### 后端

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r Backend-System/requirements.txt
python Backend-System/init-scripts/init_hotel_db.py --init --create-default-admin --seed-demo-data
python Backend-System/init-scripts/init_notification_config.py
python start_backend.py
```

说明：`start_backend.py` 会自动读取 `homes-frontend/package.json` 中的版本号，并在启动后端时自动带上 `BACKEND_APP_VERSION`。如果你有特殊需要，也可以手动传入 `BACKEND_APP_VERSION=1.0.1 python start_backend.py` 覆盖。

## 补充说明

- 前端默认是管理后台形态，包含登录鉴权与业务页面。
- 后端提供 REST API，并负责数据库初始化、上传处理、通知配置等能力。
- 项目里还包含 OCR / AI 相关配置入口，适合继续扩展自动识别或智能辅助能力。
