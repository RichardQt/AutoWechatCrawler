# coding:utf-8
# run_database_crawler.py
"""
微信公众号爬虫数据库版本统一启动脚本
支持多种爬虫模式，统一保存到数据库
"""

import os
import sys
import logging
from datetime import datetime

# 配置日志
def setup_logging():
    """设置日志配置 - 仅控制台输出"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    print("📝 日志输出: 仅控制台")
    return None

def check_dependencies():
    """检查必要的依赖"""
    print("🔍 检查依赖...")
    
    missing_deps = []
    
    try:
        import pymysql
        print("✅ pymysql 已安装")
    except ImportError:
        missing_deps.append("pymysql")
    
    try:
        import pandas
        print("✅ pandas 已安装")
    except ImportError:
        missing_deps.append("pandas")
    
    try:
        import requests
        print("✅ requests 已安装")
    except ImportError:
        missing_deps.append("requests")
    
    if missing_deps:
        print(f"❌ 缺少依赖: {', '.join(missing_deps)}")
        print("请运行: python install_database_dependencies.py")
        return False
    
    print("✅ 所有依赖检查通过")
    return True

def test_database_connection():
    """测试数据库连接"""
    print("\n🔍 测试数据库连接...")
    
    try:
        from database_manager import DatabaseManager
        
        with DatabaseManager() as db:
            count = db.get_articles_count()
            print(f"✅ 数据库连接成功！当前有 {count} 篇文章")
            return True
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("请检查:")
        print("  1. MySQL服务是否启动")
        print("  2. 数据库配置是否正确 (database_config.py)")
        print("  3. 数据库 'xuanfa' 和表 'fx_article_records' 是否存在")
        return False

def run_basic_crawler():
    """运行基础文章链接爬虫 (带数据库)"""
    print("\n🚀 启动基础文章链接爬虫 (带数据库功能)")
    print("=" * 60)
    
    try:
        from database_crawler_example import main
        main()
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
    except Exception as e:
        print(f"❌ 运行失败: {e}")

def run_readnum_crawler():
    """运行批量阅读量爬虫 (带数据库)"""
    print("\n🚀 启动批量阅读量爬虫 (带数据库功能)")
    print("=" * 60)
    
    try:
        from batch_readnum_database_example import main
        main()
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
    except Exception as e:
        print(f"❌ 运行失败: {e}")

def run_automated_crawler():
    """运行全自动化爬虫 (带数据库)"""
    print("\n🚀 启动全自动化爬虫 (带数据库功能)")
    print("=" * 60)
    
    print("⚠️ 全自动化爬虫数据库集成功能开发中...")
    print("请使用其他爬虫模式")

def show_database_stats():
    """显示数据库统计信息"""
    print("\n📊 数据库统计信息")
    print("=" * 40)
    
    try:
        from database_manager import DatabaseManager
        
        with DatabaseManager() as db:
            total_count = db.get_articles_count()
            print(f"📖 总文章数: {total_count}")
            
            # 可以添加更多统计信息
            print("✅ 统计信息获取成功")
            
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")

def install_dependencies():
    """安装依赖"""
    print("\n📦 安装数据库依赖...")
    
    try:
        from install_database_dependencies import main
        main()
    except ImportError:
        print("❌ 找不到安装脚本 install_database_dependencies.py")
    except Exception as e:
        print(f"❌ 安装失败: {e}")

def show_help():
    """显示帮助信息"""
    print("\n📖 微信公众号爬虫数据库版本使用说明")
    print("=" * 60)
    print("本工具支持将微信公众号文章数据实时保存到MySQL数据库中")
    print()
    print("🎯 主要功能:")
    print("  1. 基础文章链接爬虫 - 获取文章基本信息和内容")
    print("  2. 批量阅读量爬虫 - 获取文章阅读量、点赞数等统计数据")
    print("  3. 全自动化爬虫 - 自动获取Cookie并批量抓取 (开发中)")
    print()
    print("💾 数据库功能:")
    print("  - 实时保存文章数据到MySQL数据库")
    print("  - 自动生成文章ID (时间+随机数)")
    print("  - 自动设置爬取渠道为'微信公众号'")
    print("  - 支持断线重连和错误处理")
    print()
    print("📋 使用前准备:")
    print("  1. 安装依赖: 选择选项 6")
    print("  2. 配置数据库: 编辑 database_config.py")
    print("  3. 创建数据库表: 执行 fx_article_records.sql")
    print("  4. 测试连接: 选择选项 4")
    print()
    print("📚 详细文档: 查看 DATABASE_README.md")

def main():
    """主函数"""
    # 设置日志
    log_file = setup_logging()
    
    print("🎯 微信公众号爬虫数据库版本")
    print("=" * 60)
    print(f"📝 日志文件: {log_file}")
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请先安装必要的依赖")
        return
    
    while True:
        print("\n" + "=" * 60)
        print("请选择操作:")
        print("1. 🔗 基础文章链接爬虫 (带数据库)")
        print("2. 📊 批量阅读量爬虫 (带数据库)")
        print("3. 🤖 全自动化爬虫 (带数据库) [开发中]")
        print("4. 📈 查看数据库统计")
        print("5. 🔍 测试数据库连接")
        print("6. 📦 安装/更新依赖")
        print("7. 📖 查看帮助")
        print("0. 🚪 退出")
        print("=" * 60)
        
        choice = input("请输入选择 (0-7): ").strip()
        
        if choice == "1":
            if test_database_connection():
                run_basic_crawler()
            else:
                print("❌ 数据库连接失败，无法运行爬虫")
                
        elif choice == "2":
            if test_database_connection():
                run_readnum_crawler()
            else:
                print("❌ 数据库连接失败，无法运行爬虫")
                
        elif choice == "3":
            run_automated_crawler()
            
        elif choice == "4":
            show_database_stats()
            
        elif choice == "5":
            test_database_connection()
            
        elif choice == "6":
            install_dependencies()
            
        elif choice == "7":
            show_help()
            
        elif choice == "0":
            print("👋 再见！")
            break
            
        else:
            print("❌ 无效选择，请重新输入")
        
        input("\n按回车键继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 用户中断，程序退出")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        logging.error(f"程序异常: {e}", exc_info=True)
