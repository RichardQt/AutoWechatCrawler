# coding:utf-8
# enhanced_wx_crawler.py - 增强版微信文章链接抓取器
import os
import requests
import json
import urllib3
import utils
import pandas as pd
from datetime import datetime
import time
import random
import re
from bs4 import BeautifulSoup
import html
from src.database.database_manager import DatabaseManager


class EnhancedWxCrawler(object):
    """增强版翻页内容抓取，支持保存到文件"""
    urllib3.disable_warnings()

    def __init__(self, appmsg_token, biz, cookie, begin_page_index=0, end_page_index=5, save_to_file=True, get_content=True,
                 unit_name="", save_to_db=False, db_config=None):
        # 起始页数
        self.begin_page_index = begin_page_index
        # 结束页数
        self.end_page_index = end_page_index
        # 抓了多少条了
        self.num = 1
        # 是否保存到文件
        self.save_to_file = save_to_file
        # 是否获取文章内容
        self.get_content = get_content
        # 存储抓取的文章数据
        self.articles_data = []
        # 单位名称（公众号名称）
        self.unit_name = unit_name
        # 是否保存到数据库
        self.save_to_db = save_to_db
        # 数据库管理器
        self.db_manager = None

        # 初始化数据库连接
        if self.save_to_db:
            try:
                if db_config:
                    self.db_manager = DatabaseManager(**db_config)
                else:
                    self.db_manager = DatabaseManager()  # 使用默认配置
                print("✅ 数据库连接已建立，将实时保存文章数据")
            except Exception as e:
                print(f"❌ 数据库连接失败: {e}")
                print("⚠️ 将只保存到文件，不保存到数据库")
                self.save_to_db = False

        self.appmsg_token = appmsg_token
        self.biz = biz
        self.headers = {
            "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/57.0.2987.132 MQQBrowser/6.2 Mobile",
            "Cookie": cookie
        }
        self.cookie = cookie

    def article_list(self, context):
        """解析文章列表"""
        try:
            articles = json.loads(context).get('general_msg_list')
            return json.loads(articles)
        except Exception as e:
            print(f"❌ 解析文章列表失败: {e}")
            return None

    def extract_articles_from_page(self, articles_data):
        """从页面数据中提取文章信息"""
        extracted_articles = []

        if not articles_data or 'list' not in articles_data:
            return extracted_articles

        for a in articles_data['list']:
            # 收集所有文章（主条和副条统一处理）
            all_articles = []

            # 添加主条文章
            if 'app_msg_ext_info' in a.keys() and '' != a.get('app_msg_ext_info').get('content_url',''):
                main_article = {
                    'title': a.get('app_msg_ext_info').get('title', ''),
                    'url': a.get('app_msg_ext_info').get('content_url', ''),
                    'pub_time': self.format_time(a.get('comm_msg_info', {}).get('datetime', 0)),
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                all_articles.append(main_article)

            # 添加副条文章
            if 'app_msg_ext_info' in a.keys():
                for m in a.get('app_msg_ext_info').get('multi_app_msg_item_list',[]):
                    sub_article = {
                        'title': m.get('title', ''),
                        'url': m.get('content_url', ''),
                        'pub_time': self.format_time(a.get('comm_msg_info', {}).get('datetime', 0)),
                        'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    all_articles.append(sub_article)

            # 统一处理所有文章
            for article_info in all_articles:
                # 若启用入库，先按标题在库去重；存在则直接跳过，不发请求
                if self.save_to_db and self.db_manager:
                    try:
                        title_to_check = (article_info.get('title') or '').strip()
                        if title_to_check and self.db_manager.check_article_title_exists(title_to_check):
                            print(f"⚠️ 数据库已存在该文章标题，跳过不请求: {title_to_check[:60]}...")
                            continue
                    except Exception:
                        pass
                # 每篇文章处理前添加延迟 (10-20秒)
                delay = random.randint(10, 20)
                print(f"每篇文章间等待 {delay} 秒...")
                time.sleep(delay)

                # 如果需要获取文章内容
                if self.get_content:
                    content_data = self.get_article_content(article_info['url'])
                    if content_data:
                        if content_data.get('error') == 'captcha_required':
                            print("🛑 遇到验证码，停止获取内容")
                            return extracted_articles
                        elif content_data.get('error') == 'invalid_params':
                            print("⚠️ URL参数错误，跳过此文章内容获取")
                        elif content_data.get('error') == 'not_article_page':
                            print("⚠️ 非文章页面，跳过内容获取")
                        else:
                            article_info.update({
                                'content': content_data.get('content', ''),
                                'content_length': content_data.get('content_length', 0),
                            })

                # 根据公众号名称映射到单位名称
                gzh_name = self.unit_name  # 这里的unit_name实际上是公众号名称
                if self.save_to_db and self.db_manager:
                    # 使用数据库管理器的映射方法
                    resolved_unit_name = self.db_manager.resolve_unit_name(gzh_name)
                    article_info['unit_name'] = resolved_unit_name if resolved_unit_name else ''
                else:
                    # 如果没有数据库连接，保持为空
                    article_info['unit_name'] = ''

                # 实时保存到数据库
                if self.save_to_db and self.db_manager:
                    try:
                        # 按标题去重：存在则跳过不入库
                        title_to_check = (article_info.get('title') or '').strip()
                        if title_to_check and self.db_manager.check_article_title_exists(title_to_check):
                            print(f"⚠️ 数据库已存在该文章标题，跳过: {title_to_check[:60]}...")
                            extracted_articles.append(article_info)
                            print(f"{self.num}条 {article_info['title']}")
                            self.num += 1
                            continue

                        success = self.db_manager.insert_article(article_info)
                        if success:
                            print(f"💾 第{self.num}条文章已保存到数据库: {article_info['title']}")
                        else:
                            # 标题重复为主
                            if article_info.get('title', '').strip() and self.db_manager.check_article_title_exists(article_info.get('title', '').strip()):
                                print(f"⚠️ 第{self.num}条文章标题重复，已跳过: {article_info['title']}")
                            else:
                                print(f"❌ 第{self.num}条文章数据库保存失败: {article_info['title']}")
                    except Exception as e:
                        print(f"❌ 数据库保存出错: {e}")

                extracted_articles.append(article_info)
                print(f"{self.num}条 {article_info['title']}")
                self.num += 1

        return extracted_articles

    def validate_and_fix_url(self, url):
        """
        验证和修复文章URL
        :param url: 原始URL
        :return: 修复后的URL或None
        """
        if not url:
            return None

        # HTML解码
        url = html.unescape(url)

        # 移除可能的HTML转义字符
        url = url.replace('&amp;', '&')

        # 检查URL是否完整
        if not url.startswith('http'):
            print(f"⚠️ URL格式不正确: {url[:50]}...")
            return None

        # 检查URL长度，微信文章URL通常比较长
        if len(url) < 50:
            print(f"⚠️ URL过短，可能不完整: {url}")
            return None

        # 检查是否包含必要的参数
        required_params = ['__biz', 'mid', 'idx', 'sn']
        missing_params = []

        for param in required_params:
            if param not in url:
                missing_params.append(param)

        if missing_params:
            print(f"⚠️ URL缺少必要参数: {missing_params}")
            print(f"   URL: {url[:100]}...")
            return None

        # 确保URL以https开头
        if url.startswith('http://'):
            url = url.replace('http://', 'https://', 1)

        return url

    def format_time(self, timestamp):
        """格式化时间戳"""
        try:
            if timestamp:
                return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            else:
                return ''
        except:
            return ''

    def get_article_content(self, article_url):
        """
        获取文章内容
        :param article_url: 文章URL
        :return: 文章内容字典
        """
        if not article_url:
            return None

        # 验证和修复URL
        article_url = self.validate_and_fix_url(article_url)
        if not article_url:
            print("❌ URL无效，跳过")
            return None

        try:
            print(f"📄 获取文章内容: {article_url[:50]}...")
            print(f"🔗 完整URL: {article_url}")

            # 添加随机延迟避免被封 (5-10秒，因为文章处理前已有延迟)
            delay = random.randint(1,5)
            print(f"获取内容前等待 {delay} 秒...")
            time.sleep(delay)

            response = requests.get(
                article_url,
                headers=self.headers,
                verify=False,
                timeout=30
            )

            if response.status_code != 200:
                print(f"❌ 请求失败，状态码: {response.status_code}")
                return None

            html_content = response.text

            # 检查各种错误情况
            if "参数错误" in html_content:
                print("❌ 微信返回'参数错误'，URL可能不完整或已失效")
                print(f"   问题URL: {article_url}")
                return {
                    'content': '',
                    'error': 'invalid_params'
                }

            # 检查是否遇到验证码页面
            if "环境异常" in html_content or "完成验证" in html_content or "secitptpage/verify" in html_content:
                print("⚠️ 遇到微信验证码页面，需要手动验证")
                return {
                    'content': '',
                    'error': 'captcha_required'
                }

            # 检查是否为真实文章页面
            if "js_content" not in html_content and "rich_media_content" not in html_content:
                print("⚠️ 非文章页面，可能被重定向或文章不存在")
                return {
                    'content': '',
                    'error': 'not_article_page'
                }

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 提取文章标题
            title = ""
            title_tag = soup.find('h1', {'class': 'rich_media_title'}) or soup.find('meta', {'property': 'og:title'})
            if title_tag:
                if title_tag.name == 'meta':
                    title = title_tag.get('content', '')
                else:
                    title = title_tag.get_text(strip=True)

            # 提取文章作者
            author = ""
            author_tag = soup.find('a', {'class': 'rich_media_meta_link'}) or soup.find('meta', {'property': 'og:article:author'})
            if author_tag:
                if author_tag.name == 'meta':
                    author = author_tag.get('content', '')
                else:
                    author = author_tag.get_text(strip=True)

            # 提取文章内容
            content = ""
            content_div = soup.find('div', {'class': 'rich_media_content'}) or soup.find('div', {'id': 'js_content'})
            if content_div:
                # 移除脚本和样式标签
                for script in content_div(["script", "style"]):
                    script.decompose()

                # 获取纯文本内容
                content = content_div.get_text(separator='\n', strip=True)

                # 清理多余的空行
                content = re.sub(r'\n\s*\n', '\n\n', content)
                content = content.strip()

            # 提取发布时间
            pub_time = ""
            time_tag = soup.find('em', {'class': 'rich_media_meta_text'}) or soup.find('span', {'class': 'rich_media_meta_text'})
            if time_tag:
                pub_time = time_tag.get_text(strip=True)

            result = {
                'title': title,
                'author': author,
                'content': content,
                'pub_time': pub_time,
                'content_length': len(content),
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            print(f"✅ 内容获取成功，长度: {len(content)} 字符")
            return result

        except Exception as e:
            print(f"❌ 获取文章内容失败: {e}")
            return None

    def save_data(self):
        """保存数据到文件"""
        if not self.articles_data:
            print("⚠️ 没有数据需要保存")
            return None, None

        # 根据是否获取内容选择不同的保存目录
        if self.get_content:
            data_dir = "./data/with_content"
            file_prefix = "articles_with_content"
        else:
            data_dir = "./data/basic_links"
            file_prefix = "article_links"

        os.makedirs(data_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_file = os.path.join(data_dir, f"{file_prefix}_{timestamp}.xlsx")
        json_file = os.path.join(data_dir, f"{file_prefix}_{timestamp}.json")

        try:
            # 创建过滤后的数据副本，去除author和detailed_pub_time列
            filtered_data = []
            for article in self.articles_data:
                filtered_article = {}
                for key, value in article.items():
                    # 排除author和detailed_pub_time字段
                    if key not in ['author', 'detailed_pub_time']:
                        filtered_article[key] = value
                filtered_data.append(filtered_article)

            # 保存为Excel
            df = pd.DataFrame(filtered_data)
            df.to_excel(excel_file, index=False, engine='openpyxl')
            print(f"📊 Excel文件已保存: {excel_file}")

            # 保存为JSON
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(filtered_data, f, ensure_ascii=False, indent=2)
            print(f"💾 JSON文件已保存: {json_file}")

            return excel_file, json_file

        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
            return None, None

    def run(self):
        """运行爬虫"""
        current_page = self.begin_page_index

        print(f"🚀 开始抓取文章{'内容' if self.get_content else '链接'}...")
        print(f"📋 页数范围: {self.begin_page_index} - {self.end_page_index}")
        if self.get_content:
            print(f"📄 将获取文章完整内容（速度较慢）")
        else:
            print(f"🔗 仅获取文章链接信息（速度较快）")

        while current_page <= self.end_page_index:
            try:
                print(f"\n📄 正在抓取第 {current_page + 1} 页...")
                
                # 翻页地址
                page_url = "https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={}&f=json&offset={}&count=10&is_ok=1&scene=&uin=777&key=777&pass_ticket={}&wxtoken=&appmsg_token={}&x5=0&f=json"
                
                # 将 cookie 字符串清理并字典化
                clean_cookie = self.cookie.replace('\u00a0', ' ').strip()
                wx_dict = utils.str_to_dict(clean_cookie, join_symbol='; ', split_symbol='=')
                
                # 请求地址
                response = requests.get(
                    page_url.format(
                        self.biz, 
                        current_page * 10, 
                        wx_dict['pass_ticket'], 
                        self.appmsg_token
                    ), 
                    headers=self.headers, 
                    verify=False,
                    timeout=30
                )
                
                if response.status_code != 200:
                    print(f"❌ 请求失败，状态码: {response.status_code}")
                    break
                
                # 将文章列表字典化
                articles = self.article_list(response.text)
                
                if not articles:
                    print("❌ 解析文章列表失败，可能Cookie已过期")
                    break
                
                # 提取文章信息
                page_articles = self.extract_articles_from_page(articles)
                
                if not page_articles:
                    print("⚠️ 本页没有找到文章，可能已到最后一页")
                    break
                
                # 添加到总数据中
                self.articles_data.extend(page_articles)
                print(f"✅ 第 {current_page + 1} 页完成，获取 {len(page_articles)} 篇文章")
                
                current_page += 1
                
                # 添加延迟避免被封
                if current_page <= self.end_page_index:
                    print("⏳ 等待 3 秒...")
                    time.sleep(3)
                
            except KeyboardInterrupt:
                print("\n⏹️ 用户中断抓取")
                break
            except Exception as e:
                print(f"❌ 抓取第 {current_page + 1} 页时出错: {e}")
                current_page += 1
                continue
        
        # 保存数据
        if self.save_to_file and self.articles_data:
            self.save_data()

        # 关闭数据库连接
        if self.db_manager:
            self.db_manager.disconnect()
            print("💾 数据库连接已关闭")

        print(f"\n🎉 抓取完成！")
        print(f"📊 总共获取 {len(self.articles_data)} 篇文章链接")
        if self.save_to_db:
            print(f"💾 数据已实时保存到数据库")

        return self.articles_data

    def print_summary(self):
        """打印抓取摘要"""
        if not self.articles_data:
            print("📊 没有数据可显示")
            return

        print(f"\n📊 抓取摘要")
        print("=" * 50)
        print(f"📖 总文章数: {len(self.articles_data)}")

        # 如果获取了内容，显示内容统计
        if self.get_content:
            content_articles = [a for a in self.articles_data if a.get('content')]
            print(f"📄 成功获取内容: {len(content_articles)} 篇")
            if content_articles:
                avg_length = sum(a.get('content_length', 0) for a in content_articles) / len(content_articles)
                print(f"� 平均内容长度: {int(avg_length)} 字符")

        # 显示最新几篇文章
        print(f"\n📋 最新文章:")
        for i, article in enumerate(self.articles_data[:5]):
            title = article['title'][:50] + "..." if len(article['title']) > 50 else article['title']
            if self.get_content and article.get('content_length'):
                print(f"   {i+1}. {title} ({article['content_length']}字)")
            else:
                print(f"   {i+1}. {title}")

        if len(self.articles_data) > 5:
            print(f"   ... 还有 {len(self.articles_data) - 5} 篇文章")
