# coding:utf-8
# verify_database.py
"""
数据库功能验证脚本
用于验证数据库连接和实时保存功能是否正常工作
"""

import sys
import time
import os

# 解决Windows控制台编码问题
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from datetime import datetime
from src.database.database_manager import DatabaseManager
from src.database.database_config import get_database_config, get_table_config

def test_database_connection():
    """测试数据库连接"""
    print("测试数据库连接...")

    try:
        db_config = get_database_config()
        table_name = get_table_config().get('table_name', 'fx_article_records')
        print(f"数据库配置: {db_config['host']}:{db_config['port']}/{db_config['database']} (表: {table_name})")

        with DatabaseManager(**db_config) as db:
            count = db.get_articles_count()
            print("数据库连接成功！")
            print(f"📊 当前数据库表 '{table_name}' 中有 {count} 篇文章")
            return True, db_config

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("请检查:")
        print("  1. MySQL服务是否启动")
        print("  2. database_config.py 中的配置是否正确")
        print("  3. 目标数据库是否存在")
        print("  4. 目标表是否存在 (来自 database_config.TABLE_CONFIG['table_name'])")
        return False, None

def test_insert_article():
    """测试插入文章功能"""
    print("\n🧪 测试插入文章功能...")
    
    try:
        db_config = get_database_config()
        
        # 创建测试文章数据
        test_article = {
            'title': f'测试文章 - {datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'content': '这是一篇用于测试数据库功能的文章内容。包含中文字符和特殊符号：！@#￥%……&*（）',
            'url': f'https://mp.weixin.qq.com/s/test_{int(time.time())}',
            'pub_time': '2025-08-05 20:00:00',
            'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            # 新表结构：写入 gzh_name。unit_name 将通过对照表回填。
            'gzh_name': '测试公众号',
            'view_count': 1234
        }
        
        print(f"📝 准备插入测试文章: {test_article['title']}")
        
        with DatabaseManager(**db_config) as db:
            # 获取插入前的文章数量
            count_before = db.get_articles_count()
            print(f"插入前文章数量: {count_before}")
            
            # 插入测试文章
            success = db.insert_article(test_article)
            
            if success:
                # 获取插入后的文章数量
                count_after = db.get_articles_count()
                print(f"✅ 文章插入成功！")
                print(f"插入后文章数量: {count_after}")
                print(f"新增文章数量: {count_after - count_before}")
                return True
            else:
                print(f"❌ 文章插入失败")
                return False
                
    except Exception as e:
        print(f"❌ 测试插入文章时出错: {e}")
        return False

def test_duplicate_detection():
    """专门测试去重功能"""
    print("\n🔍 测试标题去重功能...")

    try:
        db_config = get_database_config()

        with DatabaseManager(**db_config) as db:
            # 创建测试文章
            base_title = f"去重测试文章 - {datetime.now().strftime('%Y%m%d_%H%M%S')}"

            test_articles = [
                {
                    'title': base_title,
                    'content': '第一篇文章内容',
                    'url': f'https://mp.weixin.qq.com/s/test1_{int(time.time())}',
                    'pub_time': '2025-08-05 20:00:00',
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'gzh_name': '去重测试公众号',
                    'view_count': 1000
                },
                {
                    'title': base_title,  # 相同标题
                    'content': '第二篇文章内容（应该被去重）',
                    'url': f'https://mp.weixin.qq.com/s/test2_{int(time.time())}',
                    'pub_time': '2025-08-05 21:00:00',
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'gzh_name': '去重测试公众号',
                    'view_count': 2000
                },
                {
                    'title': base_title + " - 不同标题",
                    'content': '第三篇文章内容（标题不同，应该插入）',
                    'url': f'https://mp.weixin.qq.com/s/test3_{int(time.time())}',
                    'pub_time': '2025-08-05 22:00:00',
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'gzh_name': '去重测试公众号',
                    'view_count': 3000
                }
            ]

            count_before = db.get_articles_count()
            print(f"测试前文章数量: {count_before}")

            # 批量插入测试
            result = db.batch_insert_articles(test_articles)

            count_after = db.get_articles_count()
            print(f"测试后文章数量: {count_after}")
            print(f"实际新增: {count_after - count_before}")
            print(f"插入结果: 成功 {result['success']} 篇，重复 {result['duplicate']} 篇，失败 {result['failed']} 篇")

            # 验证结果
            if result['success'] == 2 and result['duplicate'] == 1 and result['failed'] == 0:
                print("✅ 去重功能测试通过！")
                return True
            else:
                print("❌ 去重功能测试失败！")
                return False

    except Exception as e:
        print(f"❌ 测试去重功能时出错: {e}")
        return False

def monitor_database_changes():
    """监控数据库变化"""
    print("\n👀 开始监控数据库变化...")
    print("请在另一个终端运行: python main_enhanced.py")
    print("按 Ctrl+C 停止监控")
    
    try:
        db_config = get_database_config()
        
        with DatabaseManager(**db_config) as db:
            initial_count = db.get_articles_count()
            print(f"初始文章数量: {initial_count}")
            print("开始监控... (每36s检查一次)")
            
            last_count = initial_count
            check_interval = 36 # 5秒检查一次
            
            while True:
                time.sleep(check_interval)
                
                try:
                    current_count = db.get_articles_count()
                    
                    if current_count != last_count:
                        new_articles = current_count - last_count
                        print(f"检测到新文章！")
                        print(f"当前文章数量: {current_count}")
                        print(f"新增文章数量: {new_articles}")
                        print(f"检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        last_count = current_count
                    else:
                        print(f"⏳ {datetime.now().strftime('%H:%M:%S')} - 文章数量: {current_count} (无变化)")
                        
                except Exception as e:
                    print(f"❌监控过程中出错: {e}")
                    time.sleep(10)  # 出错时等待更长时间
                    
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"❌监控启动失败: {e}")

def show_recent_articles(limit=10):
    """显示最近的文章"""
    print(f"\n显示最近 {limit} 篇文章...")
    
    try:
        db_config = get_database_config()
        
        with DatabaseManager(**db_config) as db:
            if not db.is_connected():
                print("❌ 数据库连接失败")
                return
            
            table_name = get_table_config().get('table_name', 'fx_article_records')
            sql = """
            SELECT article_title, gzh_name, unit_name, view_count, crawl_time, create_time 
            FROM {table_name} 
            ORDER BY create_time DESC 
            LIMIT %s
            """
            
            with db.connection.cursor() as cursor:
                cursor.execute(sql.format(table_name=table_name), (limit,))
                articles = cursor.fetchall()
                
                if articles:
                    print(f"找到 {len(articles)} 篇文章:")
                    print("-" * 80)
                    for i, article in enumerate(articles, 1):
                        print(f"{i:2d}. {article['article_title'][:40]}...")
                        # 优先展示 gzh_name；若未回填时也可展示 unit_name（对照表回填值）
                        oa_name = article.get('gzh_name') or article.get('unit_name') or ''
                        print(f"     公众号: {oa_name}")
                        print(f"     阅读量: {article['view_count'] or 0}")
                        print(f"     爬取时间: {article['crawl_time']}")
                        print(f"     保存时间: {article['create_time']}")
                        print("-" * 80)
                else:
                    print("📭 数据库中暂无文章数据")
                    
    except Exception as e:
        print(f"❌ 查询文章时出错: {e}")

def main():
    """主函数"""
    print("数据库功能验证工具")
    print("=" * 60)
    
    while True:
        print("\n请选择操作:")
        print("1. 测试数据库连接")
        print("2. 测试插入文章")
        print("3. 测试标题去重功能")
        print("4. 监控数据库变化 (实时)")
        print("5. 查看最近文章")
        print("0. 退出")

        choice = input("\n请输入选择 (0-5): ").strip()
        
        if choice == "1":
            success, _ = test_database_connection()
            if success:
                print("✅ 数据库连接测试通过！")
            else:
                print("❌ 数据库连接测试失败！")
                
        elif choice == "2":
            success = test_insert_article()
            if success:
                print("✅ 插入文章测试通过！")
            else:
                print("❌ 插入文章测试失败！")
                
        elif choice == "3":
            success = test_duplicate_detection()
            if success:
                print("✅ 去重功能测试通过！")
            else:
                print("❌ 去重功能测试失败！")

        elif choice == "4":
            monitor_database_changes()

        elif choice == "5":
            try:
                limit = int(input("请输入要显示的文章数量 (默认10): ") or "10")
                show_recent_articles(limit)
            except ValueError:
                print("❌ 请输入有效的数字")
                
        elif choice == "0":
            print("再见！")
            break
            
        else:
            print("❌ 无效选择，请重新输入")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
