#!/usr/bin/env python3
"""
垂直视频裁剪工具 - GUI启动脚本
方便打包为exe文件
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gui_app import main
    print("启动垂直视频裁剪工具GUI...")
    main()
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖包:")
    print("pip install -r requirements.txt")
    input("按回车键退出...")
except Exception as e:
    print(f"启动错误: {e}")
    input("按回车键退出...")