#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号爬虫工具集 v3.0 - 主入口点
专为Windows任务计划程序设计，无需任何用户交互，直接执行Excel全自动爬取流程。
"""

import os
import sys

# Add the project root directory and config directory to the path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'config'))

from src.core.main_enhanced import main

if __name__ == '__main__':
    main()