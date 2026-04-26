# 该文件负责生成或触发后端初始化所需的演示数据脚本入口。
import sys
import os

# Allow importing from parent directory
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from init_hotel_db import seed_demo_data
except ImportError:
    from init_scripts.init_hotel_db import seed_demo_data

def main():
    print("开始生成模拟数据...")
    seed_demo_data()
    print("模拟数据生成完成。")

if __name__ == "__main__":
    main()
