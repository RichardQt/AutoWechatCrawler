#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主流程封装（自动化版本）

职责：
1. 初始化日志
2. 读取配置（包含 Excel 路径等）
3. 测试数据库连接（可选）
4. 启动 AutomatedCrawler
"""

import os
import sys
import logging
from datetime import datetime
import traceback
import argparse

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from config.config_manager import get_crawler_config, get_database_config
from src.database.database_manager import DatabaseManager
from src.core.automated_crawler import AutomatedCrawler


def setup_logging() -> logging.Logger:
    """初始化日志，仅输出到控制台"""
    root = logging.getLogger()  # 根日志器
    root.setLevel(logging.INFO)

    # 清理已有处理器，避免被其他模块（如uiautomation、comtypes或basicConfig）污染
    for h in list(root.handlers):
        root.removeHandler(h)

    # 控制台处理器（UTF-8，指向stdout）
    if sys.platform.startswith('win'):
        import io
        # 确保以UTF-8写入标准输出（即使外部是管道）
        stream = io.TextIOWrapper(getattr(sys.stdout, 'buffer', sys.stdout), encoding='utf-8', errors='replace')
        console_handler = logging.StreamHandler(stream)
    else:
        console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    root.addHandler(console_handler)

    # 降低噪声库日志级别
    logging.getLogger('comtypes').setLevel(logging.WARNING)
    logging.getLogger('uiautomation').setLevel(logging.INFO)

    # 为业务命名日志器保留接口（与根日志器一致，避免重复handler）
    biz_logger = logging.getLogger("wechat_spider_main")
    biz_logger.propagate = True
    biz_logger.setLevel(logging.INFO)
    return biz_logger


def main(argv=None):
    """主程序入口 - 全自动化爬取"""
    logger = setup_logging()

    logger.info("=" * 80)
    logger.info("🚀 微信公众号全自动爬取流程启动 🚀")
    logger.info("版本: v3.0 - 全自动化版本")
    logger.info("执行时间: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 80)

    # 参数解析：支持 --excel 覆盖配置中的 excel_file
    parser = argparse.ArgumentParser(description="WeChat 全自动爬取入口")
    parser.add_argument("--excel", dest="excel", default=None, help="Excel 路径，覆盖配置中的 crawler.excel_file")
    args = parser.parse_args(argv)

    # 读取爬虫配置
    crawler_cfg = get_crawler_config()
    excel_file = args.excel or crawler_cfg.get('excel_file', 'target_articles.xlsx')
    if not os.path.exists(excel_file):
        logger.error("❌ 未找到 Excel 文件: %s", excel_file)
        logger.error("请在项目根目录放置目标公众号 Excel 文件 (默认: target_articles.xlsx)")
        sys.exit(1)

    # 测试数据库连接
    db_config = get_database_config()
    logger.info("🔍 测试数据库连接...")
    try:
        with DatabaseManager(**db_config) as db:
            count = db.get_articles_count()
            logger.info(f"✅ 数据库连接成功！当前已有 {count} 篇文章")
            save_to_db = True
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        logger.warning("⚠️ 将仅保存到本地文件，不写入数据库")
        save_to_db = False

    try:
        logger.info("启动全自动化爬取流程...")
        crawler = AutomatedCrawler(
            excel_path=excel_file,
            save_to_db=save_to_db,
            db_config=db_config,
            crawler_config=crawler_cfg,
        )
        success = crawler.run()
        if success:
            logger.info("✅ 爬取流程完成，程序正常结束")
            sys.exit(0)
        else:
            logger.error("❌ 爬取流程失败")
            sys.exit(1)
    except ImportError as e:
        logger.error("❌ 依赖库缺失: %s", e)
        logger.error("请先安装依赖: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error("❌ 主流程异常: %s", e)
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()