# 该文件负责串联执行数据库与通知配置初始化等一键启动前准备工作。
import sys
import os

# Allow importing from parent directory
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from init_hotel_db import ensure_tables, create_default_admin, ensure_sql_dir_and_migrate_db
    from init_notification_config import write_default_config as init_notify
except ImportError:
    from init_scripts.init_hotel_db import ensure_tables, create_default_admin, ensure_sql_dir_and_migrate_db
    from init_scripts.init_notification_config import write_default_config as init_notify

def main():
    print("开始系统初始化...")
    
    # 1. Database
    print("正在初始化数据库...")
    ensure_sql_dir_and_migrate_db()
    ensure_tables()
    print("✅ 数据库表结构初始化完成")
    
    # 2. Admin
    print("正在检查/创建默认管理员...")
    created, msg = create_default_admin()
    print(f"✅ {msg}")
    
    # 3. Configs
    print("正在初始化配置文件...")
    notify_path = init_notify()
    print(f"✅ 通知配置已就绪: {notify_path}")
    
    print("\n🎉 系统初始化全部完成！")
    print("接下来您可以运行 generate_mock_data.py 来生成演示数据。")

if __name__ == "__main__":
    main()
