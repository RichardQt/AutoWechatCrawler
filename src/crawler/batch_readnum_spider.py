#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号批量阅读量抓取器
基于现有代码架构，整合文章链接获取和阅读量抓取功能
"""

import os
import re
import json
import time
import random
import requests
import pandas as pd
import winreg
import ctypes
import contextlib
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

from src.proxy.read_cookie import ReadCookie
from src.ui.wechat_browser_automation import WeChatBrowserAutomation, UI_AUTOMATION_AVAILABLE
from src.utils import utils
from src.database.database_manager import DatabaseManager
from config import get_crawler_config

class BatchReadnumSpider:
    """批量微信公众号阅读量抓取器"""
    
    def __init__(self, auth_info: dict = None, save_to_db=False, db_config=None, unit_name="", crawler_config=None):
        """
        初始化批量阅读量抓取器
        :param auth_info: 包含appmsg_token, biz, cookie_str和headers的字典
        :param save_to_db: 是否保存到数据库
        :param db_config: 数据库配置
        :param unit_name: 公众号名称（将通过对照表映射为单位名称）
        """
        # 初始化认证信息
        self.appmsg_token = None
        self.biz = None
        self.cookie_str = None
        self.auth_info = auth_info  # 存储传入的认证数据

        # 数据库相关配置
        self.save_to_db = save_to_db
        self.unit_name = unit_name
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

        # 请求头配置 - 参考spider_readnum.py的成功实现
        self.headers = {
            'cache-control': 'max-age=0',
            'x-wechat-key': '',
            'x-wechat-uin': '',
            'exportkey': '',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090c37) XWEB/14315 Flue',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-dest': 'document',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9',
            'priority': 'u=0, i',
        }

        # 从传入的auth_info加载认证信息和更新headers
        if self.auth_info:
            self.load_auth_info()
        else:
            print("❌ BatchReadnumSpider 初始化时未提供认证数据。")

        # 数据存储 - 统一存储所有字段
        self.articles_data = []

        # 频率控制（引入配置）
        self.request_count = 0
        self.last_request_time = 0
        self.crawler_config = crawler_config or get_crawler_config()
        self.min_interval = self.crawler_config.get('min_interval', 3)
        self.article_delay_range = self.crawler_config.get('article_delay_range', [10, 15])
        self.page_delay_range = self.crawler_config.get('page_delay_range', [10, 20])
        self.refresh_count_cfg = self.crawler_config.get('refresh_count', 3)
        self.refresh_delay_cfg = self.crawler_config.get('refresh_delay', 3.0)
        self.timeout = self.crawler_config.get('timeout', 30)
        self.max_retries = self.crawler_config.get('max_retries', 3)

        # 创建数据目录
        os.makedirs("./data/readnum_batch", exist_ok=True)
        # key 刷新节流
        self.last_key_refresh_time = None
        self.min_rekey_interval_sec = self.crawler_config.get('min_rekey_interval_sec', 1500)

        # ===== 预加载公众号->单位映射（在内存中加速 & 保证写库前即完成映射） =====
        self.gzh_unit_map = {}
        if self.save_to_db and self.db_manager:
            try:
                with self.db_manager.connection.cursor() as cursor:
                    cursor.execute("SELECT gzh_name, unit_name FROM fx_unit_gzh_contrast WHERE gzh_name IS NOT NULL AND gzh_name <> ''")
                    rows = cursor.fetchall()
                    for r in rows:
                        g = (r.get('gzh_name') or '').strip()
                        u = (r.get('unit_name') or '').strip()
                        if g and u:
                            self.gzh_unit_map[g] = u
                print(f"✅ 已预加载公众号→单位映射 {len(self.gzh_unit_map)} 条")
            except Exception as e:
                print(f"⚠️ 预加载公众号映射失败，将回退逐条解析: {e}")

    def load_auth_info(self):
        """从传入的认证数据加载认证信息和headers"""
        if not self.auth_info:
            print("❌ 未传入有效的认证数据，无法加载认证信息。")
            return False

        try:
            self.appmsg_token = self.auth_info.get('appmsg_token')
            self.biz = self.auth_info.get('biz')
            self.cookie_str = self.auth_info.get('cookie_str')

            # 更新请求头，使用抓包获取的真实headers
            captured_headers = self.auth_info.get('headers', {})
            if captured_headers:
                # 使用抓包获取的所有headers覆盖默认值
                # 特别重要的是x-wechat-key，这是获取阅读量的关键
                for key, value in captured_headers.items():
                    self.headers[key] = value

                # 检查关键的headers是否存在
                key_headers = ['x-wechat-key', 'x-wechat-uin', 'exportkey']
                missing_headers = [h for h in key_headers if h not in captured_headers]

                if missing_headers:
                    print(f"⚠️ 缺少关键headers: {missing_headers}")
                    # 如果缺少x-wechat-key，使用默认值（来自spider_readnum.py的成功实现）
                    if 'x-wechat-key' in missing_headers:
                        print("🔑 使用默认的x-wechat-key值")
                else:
                    print(f"✅ 已更新所有 {len(captured_headers)} 个请求头参数，包含关键的x-wechat-key")

                # 显示x-wechat-key的前20个字符用于验证
                if 'x-wechat-key' in captured_headers:
                    print(f"🔑 x-wechat-key: {captured_headers['x-wechat-key'][:20]}...")
                elif 'x-wechat-key' in self.headers:
                    print(f"🔑 使用默认x-wechat-key: {self.headers['x-wechat-key'][:20]}...")
            else:
                print("⚠️ 未获取到headers信息，使用默认的x-wechat-key")
                print(f"🔑 默认x-wechat-key: {self.headers['x-wechat-key'][:20]}...")

            print(f"✅ 成功加载认证信息")
            print(f"   __biz: {self.biz}")
            print(f"   appmsg_token: {self.appmsg_token[:20]}...")
            print(f"   headers: {list(captured_headers.keys())}")
            return True
        except Exception as e:
            print(f"❌ 加载认证信息失败: {e}")
            return False

    def validate_cookie(self):
        """
        验证Cookie是否有效
        :return: 是否有效
        """
        print("🔍 验证Cookie有效性...")

        if not all([self.appmsg_token, self.biz, self.cookie_str]):
            print("❌ 认证信息不完整")
            return False

        try:
            # 尝试获取第一页文章列表来验证Cookie
            print("🔍 尝试获取文章列表以验证Cookie...")
            test_articles = self.get_article_list(begin_page=0, count=1)
            if test_articles:
                print("✅ Cookie验证成功")
                return True
            else:
                print("❌ Cookie验证失败，可能已过期")
                return False
        except Exception as e:
            print(f"❌ Cookie验证过程中出错: {e}")
            return False


    
    @contextlib.contextmanager
    def manage_system_proxy(self, proxy_address="127.0.0.1:8080"):
        """
        代理管理上下文管理器，临时禁用系统代理
        """
        INTERNET_OPTION_SETTINGS_CHANGED = 39
        INTERNET_OPTION_REFRESH = 37
        InternetSetOption = ctypes.windll.wininet.InternetSetOptionW
        
        original_state = {"enabled": False, "server": ""}
        was_active = False
        key = None
        
        try:
            # 打开注册表项
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 
                               0, winreg.KEY_READ | winreg.KEY_WRITE)
            
            # 读取原始代理状态
            try:
                original_state["enabled"] = winreg.QueryValueEx(key, "ProxyEnable")[0] == 1
                original_state["server"] = winreg.QueryValueEx(key, "ProxyServer")[0]
            except FileNotFoundError:
                pass
            
            # 检查代理是否是我们需要禁用的那个
            if original_state["enabled"] and original_state["server"] == proxy_address:
                was_active = True
                print(f"🔧 检测到活动代理 {proxy_address}，正在临时禁用...")
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                InternetSetOption(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
                InternetSetOption(0, INTERNET_OPTION_REFRESH, 0, 0)
            
            yield  # 执行主代码块
            
        finally:
            # 恢复原始代理设置
            if was_active and key:
                print(f"🔧 正在恢复代理 {proxy_address}...")
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                InternetSetOption(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
                InternetSetOption(0, INTERNET_OPTION_REFRESH, 0, 0)
            if key:
                winreg.CloseKey(key)
    
    def rate_limit(self):
        """智能频率控制"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            print(f"⏳ 频率控制：等待 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        # 每10个请求增加额外延迟
        if self.request_count % 10 == 0:
            extra_delay = random.randint(5, 10)
            print(f"⏳ 第{self.request_count}个请求，额外延迟 {extra_delay} 秒...")
            time.sleep(extra_delay)
    
    def get_article_list(self, begin_page=0, count=10):
        """
        获取文章列表
        :param begin_page: 起始页数
        :param count: 每页文章数量
        :return: 文章列表
        """
        if not all([self.appmsg_token, self.biz, self.cookie_str]):
            print("❌ 认证信息不完整，无法获取文章列表")
            return []
        
        # 频率控制
        self.rate_limit()
        
        # 构建请求URL
        page_url = "https://mp.weixin.qq.com/mp/profile_ext"
        params = {
            "action": "getmsg",
            "__biz": self.biz,
            "f": "json",
            "offset": begin_page * count,
            "count": count,
            "is_ok": 1,
            "scene": "",
            "uin": "777",
            "key": "777",
            "pass_ticket": "",
            "wxtoken": "",
            "appmsg_token": self.appmsg_token,
            "x5": 0
        }
        
        # 解析cookie
        clean_cookie = self.cookie_str.replace('\u00a0', ' ').strip()
        cookie_dict = utils.str_to_dict(clean_cookie, join_symbol='; ', split_symbol='=')
        
        if 'pass_ticket' in cookie_dict:
            params['pass_ticket'] = cookie_dict['pass_ticket']
        
        # 更新请求头
        headers = self.headers.copy()
        headers["Cookie"] = self.cookie_str
        
        try:
            print(f"📡 获取文章列表：第{begin_page+1}页，每页{count}篇")
            
            # 增加简单重试机制（最多 self.max_retries 次）
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = requests.get(page_url, params=params, headers=headers, verify=False, timeout=self.timeout)
                    break
                except Exception as e:
                    if attempt == self.max_retries:
                        print(f"❌ 请求失败（第{attempt}次/共{self.max_retries}次）: {e}")
                        return []
                    wait = min(3, attempt)
                    print(f"⚠️ 请求异常第{attempt}次，{wait}s后重试: {e}")
                    time.sleep(wait)
            
            if response.status_code != 200:
                print(f"❌ 请求失败，状态码: {response.status_code}")
                return []
            
            # 解析响应
            try:
                content_json = response.json()
            except:
                print("❌ 响应不是有效的JSON格式")
                print(f"🔍 响应内容前500字符: {response.text[:500]}")
                return []

            # 调试：打印响应的关键信息
            print(f"🔍 响应状态: {response.status_code}")
            print(f"🔍 响应键: {list(content_json.keys())}")

            # 检查是否有错误
            if "base_resp" in content_json:
                base_resp = content_json["base_resp"]
                print(f"🔍 base_resp: {base_resp}")
                if base_resp.get("err_msg") == "freq control":
                    print("⚠️ 遇到频率控制限制，建议稍后重试")
                    return []
                elif base_resp.get("ret") != 0:
                    print(f"❌ API返回错误: ret={base_resp.get('ret')}, err_msg={base_resp.get('err_msg')}")
                    return []

            # 检查是否需要验证
            if content_json.get("ret") == -3:
                print("❌ Cookie验证失败，可能已过期")
                print("💡 可能的原因:")
                print("   1. Cookie已过期（通常24小时后过期）")
                print("   2. Cookie格式不正确或被截断")
                print("   3. 微信检测到异常访问模式")
                print("💡 解决方案:")
                print("   1. 重新运行程序获取新的Cookie")
                print("   2. 确保在微信中正常访问文章后再抓取")
                print("   3. 降低抓取频率，增加延迟时间")
                return []

            # 解析文章列表
            if "general_msg_list" not in content_json:
                print("❌ 响应中没有找到文章列表")
                print(f"🔍 完整响应: {content_json}")
                return []
            
            articles_json = json.loads(content_json["general_msg_list"])
            articles = []
            
            for item in articles_json.get("list", []):
                # 处理主文章
                if "app_msg_ext_info" in item and item["app_msg_ext_info"].get("content_url"):
                    main_article = item["app_msg_ext_info"]
                    articles.append({
                        "title": main_article.get("title", ""),
                        "url": main_article.get("content_url", ""),
                        "author": main_article.get("author", ""),
                        "digest": main_article.get("digest", ""),
                        "create_time": item.get("comm_msg_info", {}).get("datetime", 0)
                    })
                
                # 处理副文章
                if "app_msg_ext_info" in item:
                    for sub_article in item["app_msg_ext_info"].get("multi_app_msg_item_list", []):
                        articles.append({
                            "title": sub_article.get("title", ""),
                            "url": sub_article.get("content_url", ""),
                            "author": sub_article.get("author", ""),
                            "digest": sub_article.get("digest", ""),
                            "create_time": item.get("comm_msg_info", {}).get("datetime", 0)
                        })
            
            print(f"✅ 成功获取 {len(articles)} 篇文章")
            return articles
            
        except Exception as e:
            print(f"❌ 获取文章列表失败: {e}")
            return []

    def extract_article_content_and_stats(self, article_url):
        """
        从文章页面提取文章内容、阅读量、点赞数等统计信息
        参考spider_readnum.py的成功实现
        :param article_url: 文章URL
        :return: 包含内容和统计信息的字典
        """
        if not article_url:
            return None

        # 频率控制
        self.rate_limit()

        try:
            print(f"📊 抓取统计数据: {article_url[:50]}...")

            # 修复HTML编码的URL
            import html
            clean_url = html.unescape(article_url)
            print(f"🔍 清理后URL: {clean_url}")

            # 解析URL获取参数
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(clean_url)
            query_params = parse_qs(parsed_url.query)

            print(f"🔍 解析到的参数: {query_params}")

            # 构建请求参数，参考spider_readnum.py的成功实现
            # 注意：spider_readnum.py中参数都是列表格式
            params = {}
            for key in ['__biz', 'mid', 'idx', 'sn', 'chksm']:
                if key in query_params:
                    params[key] = query_params[key]  # parse_qs已经返回列表格式

            # 添加必要的参数
            # 从cookie中提取pass_ticket
            pass_ticket_match = re.search(r'pass_ticket=([^;]+)', self.cookie_str)
            if pass_ticket_match:
                params['pass_ticket'] = [pass_ticket_match.group(1)]

            params['wx_header'] = ['1']

            print(f"🔍 请求参数: {params}")

            # 使用实例的headers（已经包含了抓包获取的关键参数）
            headers = self.headers.copy()

            print(f"🔍 使用headers: {list(headers.keys())}")

            # 验证关键的x-wechat-key是否存在
            if 'x-wechat-key' in headers:
                print(f"🔑 确认x-wechat-key存在: {headers['x-wechat-key'][:20]}...")
            else:
                print("❌ 警告：x-wechat-key不存在，可能无法获取阅读量数据")

            # 添加Cookie
            headers['Cookie'] = self.cookie_str

            # 使用代理管理器临时禁用系统代理
            with self.manage_system_proxy("127.0.0.1:8080"):
                # 使用GET请求访问文章页面
                base_url = "https://mp.weixin.qq.com/s"
                # 获取单篇文章：同样使用超时与重试
                for attempt in range(1, self.max_retries + 1):
                    try:
                        response = requests.get(base_url, params=params, headers=headers, timeout=self.timeout)
                        break
                    except Exception as e:
                        if attempt == self.max_retries:
                            print(f"❌ 文章请求失败（第{attempt}次/共{self.max_retries}次）: {e}")
                            return None
                        wait = min(3, attempt)
                        print(f"⚠️ 文章请求异常第{attempt}次，{wait}s后重试: {e}")
                        time.sleep(wait)

                if response.status_code != 200:
                    print(f"❌ 文章请求失败，状态码: {response.status_code}")
                    return None

                html_content = response.text
# ----- 保存到html-----debug测试
                # # 保存HTML内容到debug目录
                # try:
                #     debug_dir = "./data/debug"
                #     os.makedirs(debug_dir, exist_ok=True)
                    
                #     # 生成文件名，使用时间戳和文章标题的前20个字符
                #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                #     # 从URL中提取文章标识符
                #     import urllib.parse
                #     parsed = urllib.parse.urlparse(clean_url)
                #     query_params = urllib.parse.parse_qs(parsed.query)
                #     mid = query_params.get('mid', ['unknown'])[0]
                    
                #     filename = f"article_{timestamp}_{mid}.html"
                #     filepath = os.path.join(debug_dir, filename)
                    
                #     with open(filepath, 'w', encoding='utf-8') as f:
                #         f.write(html_content)
                    
                #     print(f"🔍 HTML内容已保存到: {filepath}")
                #     print(f"📏 文件大小: {len(html_content)} 字符")
                    
                # except Exception as e:
                #     print(f"⚠️ 保存HTML文件失败: {e}")

                # # 记录HTML长度用于调试
                # print(f"📏 HTML长度: {len(html_content)} 字符")

                # ------

                # 检查是否遇到验证码页面
                if "环境异常" in html_content or "完成验证" in html_content or "secitptpage/verify" in html_content:
                    print("⚠️ 遇到微信验证码页面，需要手动验证")
                    print(f"📄 请手动在浏览器中访问: {article_url}")
                    print("💡 建议：降低抓取频率，增加延迟时间")
                    return {
                        'read_count': -1,  # 用-1表示验证码页面
                        'like_count': -1,
                        'share_count': -1,
                        'error': 'captcha_required'
                    }

                # 检查是否为真实文章页面
                if "js_content" not in html_content and "rich_media_content" not in html_content:
                    print("⚠️ 非文章页面，可能被重定向或文章不存在")
                    return {
                        'read_count': -2,  # 用-2表示非文章页面
                        'like_count': -2,
                        'share_count': -2,
                        'error': 'not_article_page'
                    }

                # 提取文章基本信息
                title_match = re.search(r'<meta property="og:title" content="(.*?)"', html_content)

                title = title_match.group(1) if title_match else "未找到标题"

                # 提取文章内容
                content = self.extract_article_content(html_content)

                # 提取发布时间
                publish_time = self.extract_publish_time(html_content)

                # 提取公众号名称
                account_name = self.extract_account_name(html_content)

                # 构建完整的文章数据，包含内容和统计信息
                article_data = {
                    "title": title.strip(),
                    "url": article_url,
                    "content": content,
                    "publish_time": publish_time,
                    "account_name": account_name,
                    "read_count": 0,
                    "like_count": 0,
                    "old_like_count": 0,
                    "share_count": 0,
                    "comment_count": 0,
                    "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # 使用spider_readnum.py中验证成功的正则表达式提取统计数据

                # 提取阅读量 - 使用成功验证的模式
                read_num_match = re.search(r"var cgiData = {[^}]*?read_num: '(\d+)'", html_content)
                read_count = int(read_num_match.group(1)) if read_num_match else 0

                if read_count > 0:
                    print(f"🔍 阅读量: {read_count}")
                else:
                    print("⚠️ 未找到阅读量数据，可能该文章未公开显示阅读量")

                article_data["read_count"] = read_count

                # 若阅读量为0且非验证码/非文章页面，标记为疑似key过期，供上层触发re-key
                if read_count == 0:
                    article_data["error"] = article_data.get("error") or "key_expired"

                # 提取点赞数 - 使用成功验证的模式
                like_num_match = re.search(r"window\.appmsg_bar_data = {[^}]*?like_count: '(\d+)'", html_content)
                like_count = int(like_num_match.group(1)) if like_num_match else 0

                if like_count > 0:
                    print(f"🔍 点赞数: {like_count}")
                else:
                    print("⚠️ 未找到点赞数据")

                article_data["like_count"] = like_count

                # 提取历史点赞数 - 使用成功验证的模式
                old_like_num_match = re.search(r"window\.appmsg_bar_data = {[^}]*?old_like_count: '(\d+)'", html_content)
                old_like_count = int(old_like_num_match.group(1)) if old_like_num_match else 0

                if old_like_count > 0:
                    print(f"🔍 历史点赞数: {old_like_count}")

                article_data["old_like_count"] = old_like_count

                # 提取分享数 - 使用成功验证的模式
                share_count_match = re.search(r"window\.appmsg_bar_data = {[^}]*?share_count: '(\d+)'", html_content)
                share_count = int(share_count_match.group(1)) if share_count_match else 0

                if share_count > 0:
                    print(f"🔍 分享数: {share_count}")

                article_data["share_count"] = share_count

                print(f"✅ 统计数据: 阅读{article_data['read_count']} 点赞{article_data['like_count']} 分享{article_data['share_count']}")
                return article_data

        except Exception as e:
            print(f"❌ 提取统计数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def refresh_wechat_key_for_article(self, article_url: str) -> bool:
        """
        触发一次临时抓包以刷新 x-wechat-key：
        1) 启动抓包器
        2) 优先刷新当前微信文章窗口；若失败/无新包，回退为发送链接再点击
        3) 读取最新cookie/headers，更新当前实例认证信息
        """
        try:
            now_ts = time.time()
            # 简单的节流，避免短时间内多次re-key
            if self.last_key_refresh_time and (now_ts - self.last_key_refresh_time) < self.min_rekey_interval_sec:
                remain = int(self.min_rekey_interval_sec - (now_ts - self.last_key_refresh_time))
                print(f"⏳ 距上次key刷新过短（剩余{remain}s），跳过本次re-key")
                return False

            print("🔄 开始临时刷新x-wechat-key流程…")
            reader = ReadCookie()
            if not reader.start_cookie_extractor():
                print("❌ 抓包器启动失败，无法刷新key")
                return False

            # 优先：只刷新当前文章窗口，避免再次发送链接
            captured = False
            try:
                if UI_AUTOMATION_AVAILABLE:
                    autom = WeChatBrowserAutomation()
                    print("🔁 正在刷新当前微信文章窗口以触发新请求…")
                    autom.auto_refresh_browser(refresh_count=self.refresh_count_cfg,
                                               refresh_delay=self.refresh_delay_cfg,
                                               cookie_reader=reader)
                else:
                    print("⚠️ UI自动化不可用，跳过窗口刷新步骤")
            except Exception as e:
                print(f"⚠️ 刷新文章窗口时出错: {e}")

            # 等待抓包结果（先给较短时间）
            if reader.wait_for_new_cookie(timeout=45):
                captured = True
            else:
                print("⚠️ 刷新未触发到新包，回退为重新打开该文章…")
                try:
                    if UI_AUTOMATION_AVAILABLE:
                        autom = WeChatBrowserAutomation()
                        autom.send_and_open_latest_link(article_url, cookie_reader=reader)
                        # 再等一次
                        captured = reader.wait_for_new_cookie(timeout=90)
                    else:
                        print("❌ UI自动化不可用，无法回退到重新打开链接")
                except Exception as e:
                    print(f"❌ 回退重新打开链接时出错: {e}")

            auth_info = None
            if captured:
                auth_info = reader.get_latest_cookies()

            # 结束抓包器
            try:
                reader.stop_cookie_extractor()
            except Exception:
                pass

            if not captured or not auth_info:
                print("❌ 未能获取新的认证信息（x-wechat-key）")
                return False

            # 用新的认证信息更新当前实例
            print("✅ 获取到新的认证信息，正在更新请求头…")
            self.auth_info = auth_info
            if not self.load_auth_info():
                print("⚠️ 新认证信息加载失败")
                return False

            self.last_key_refresh_time = time.time()
            print("✅ x-wechat-key刷新完成")
            return True
        except Exception as e:
            print(f"❌ 刷新key流程异常: {e}")
            return False

    def extract_article_content(self, html_content):
        """
        从HTML中提取文章正文内容
        :param html_content: HTML内容
        :return: 文章正文
        """
        try:
            # 方法1: 使用BeautifulSoup更准确地提取内容
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # 尝试多种方式提取文章内容
            content_div = None

            # 优先尝试id="js_content"
            content_div = soup.find('div', {'id': 'js_content'})
            if not content_div:
                # 尝试class="rich_media_content"
                content_div = soup.find('div', {'class': 'rich_media_content'})
            if not content_div:
                # 尝试包含rich_media_content的class
                content_div = soup.find('div', class_=lambda x: x and 'rich_media_content' in x)

            if content_div:
                # 移除脚本和样式标签
                for script in content_div(["script", "style"]):
                    script.decompose()

                # 获取纯文本内容
                content_text = content_div.get_text(separator='\n', strip=True)

                # 清理多余的空行
                content_text = re.sub(r'\n\s*\n', '\n\n', content_text)
                content_text = content_text.strip()

                if content_text:
                    print(f"✅ 成功提取文章内容，长度: {len(content_text)} 字符")
                    return content_text

            # 方法2: 如果BeautifulSoup失败，使用spider_readnum.py中验证成功的正则表达式方法
            print("🔄 尝试使用正则表达式方法提取内容...")
            content_match = re.search(r'id="js_content".*?>(.*?)</div>', html_content, re.S)
            if content_match:
                # 简单清理HTML标签
                content = re.sub(r'<.*?>', '', content_match.group(1))
                content = content.strip()
                if content:
                    print(f"✅ 正则表达式方法成功提取内容，长度: {len(content)} 字符")
                    return content

            print("⚠️ 未找到文章内容")
            return "未找到文章内容"

        except Exception as e:
            print(f"⚠️ 提取文章内容失败: {e}")
            return "提取内容失败"

    def extract_publish_time(self, html_content):
        """
        从HTML中提取文章发布时间
        :param html_content: HTML内容
        :return: 发布时间
        """
        try:
            print("🔍 开始提取发布时间...")

            # 优先尝试提取 var createTime = '2025-08-04 14:02'; 格式
            createtime_pattern = r"var createTime = '([^']+)'"
            match = re.search(createtime_pattern, html_content)
            if match:
                found_time = match.group(1)
                print(f"✅ 通过createTime变量找到发布时间: {found_time}")
                return found_time

            # 尝试多种方式提取发布时间
            time_patterns = [
                # 常见的日期格式
                (r'<em class="rich_media_meta rich_media_meta_text"[^>]*>(\d{4}-\d{2}-\d{2})</em>', "em标签中的日期"),
                (r'<span class="rich_media_meta rich_media_meta_text"[^>]*>(\d{4}-\d{2}-\d{2})</span>', "span标签中的日期"),
                (r'var publish_time = "(\d{4}-\d{2}-\d{2})"', "JavaScript变量中的日期"),
                (r'"publish_time":"(\d{4}-\d{2}-\d{2})"', "JSON中的日期"),

                # 更多可能的格式
                (r'<em[^>]*class="[^"]*rich_media_meta[^"]*"[^>]*>(\d{4}-\d{2}-\d{2})</em>', "em标签变体"),
                (r'<span[^>]*class="[^"]*rich_media_meta[^"]*"[^>]*>(\d{4}-\d{2}-\d{2})</span>', "span标签变体"),
                (r'publish_time["\']?\s*[:=]\s*["\']?(\d{4}-\d{2}-\d{2})', "通用publish_time"),
                (r'createTime["\']?\s*[:=]\s*["\']?(\d{4}-\d{2}-\d{2})', "createTime变量"),
                (r'ct\s*=\s*["\']?(\d{10})["\']?', "时间戳格式"),

                # 包含时间的完整格式
                (r'<em class="rich_media_meta rich_media_meta_text"[^>]*>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})</em>', "完整时间em"),
                (r'<span class="rich_media_meta rich_media_meta_text"[^>]*>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})</span>', "完整时间span"),

                # 中文格式
                (r'(\d{4}年\d{1,2}月\d{1,2}日)', "中文日期格式"),
                (r'发布时间[：:]\s*(\d{4}-\d{2}-\d{2})', "发布时间标签"),
            ]

            for pattern, description in time_patterns:
                match = re.search(pattern, html_content)
                if match:
                    found_time = match.group(1)
                    print(f"✅ 通过{description}找到发布时间: {found_time}")

                    # 如果是时间戳，转换为日期格式
                    if pattern.endswith("时间戳格式"):
                        try:
                            timestamp = int(found_time)
                            formatted_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                            print(f"🔄 时间戳转换结果: {formatted_time}")
                            return formatted_time
                        except:
                            pass

                    return found_time

            # 如果都没找到，尝试搜索任何包含日期的文本
            print("🔍 尝试搜索任何日期格式...")
            general_date_patterns = [
                r'(\d{4}-\d{1,2}-\d{1,2})',
                r'(\d{4}/\d{1,2}/\d{1,2})',
                r'(\d{4}\.\d{1,2}\.\d{1,2})',
            ]

            for pattern in general_date_patterns:
                matches = re.findall(pattern, html_content)
                if matches:
                    print(f"🔍 找到可能的日期: {matches[:5]}")  # 只显示前5个

            print("❌ 未找到发布时间")
            return "未找到发布时间"

        except Exception as e:
            print(f"⚠️ 提取发布时间失败: {e}")
            return "提取时间失败"

    def extract_account_name(self, html_content):
        """
        从HTML中提取公众号名称
        :param html_content: HTML内容
        :return: 公众号名称
        """
        try:
            print("🔍 开始提取公众号名称...")

            # 优先尝试提取 wx_follow_nickname 类的div中的内容
            nickname_pattern = r'<div[^>]*class="wx_follow_nickname"[^>]*>\s*([^<]+)\s*</div>'
            match = re.search(nickname_pattern, html_content)
            if match:
                account_name = match.group(1).strip()
                print(f"✅ 通过wx_follow_nickname找到公众号名称: {account_name}")
                return account_name

            # 尝试其他可能的模式
            name_patterns = [
                # 其他可能的公众号名称位置
                (r'<span[^>]*class="[^"]*profile_nickname[^"]*"[^>]*>([^<]+)</span>', "profile_nickname"),
                (r'<div[^>]*class="[^"]*account_nickname[^"]*"[^>]*>([^<]+)</div>', "account_nickname"),
                (r'<h1[^>]*class="[^"]*rich_media_title[^"]*"[^>]*>([^<]+)</h1>', "rich_media_title"),
                (r'var nickname = "([^"]+)"', "JavaScript变量nickname"),
                (r'"nickname":"([^"]+)"', "JSON中的nickname"),
                (r'<meta property="og:site_name" content="([^"]+)"', "og:site_name"),
            ]

            for pattern, description in name_patterns:
                match = re.search(pattern, html_content)
                if match:
                    account_name = match.group(1).strip()
                    print(f"✅ 通过{description}找到公众号名称: {account_name}")
                    return account_name

            print("❌ 未找到公众号名称")
            return "未找到公众号名称"

        except Exception as e:
            print(f"⚠️ 提取公众号名称失败: {e}")
            return "提取名称失败"

    def clean_html_content(self, html_content):
        """
        清理HTML内容，保留基本文本
        :param html_content: HTML内容
        :return: 清理后的文本
        """
        try:
            import re

            # 移除script和style标签
            html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
            html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)

            # 保留段落结构，将p标签替换为换行
            html_content = re.sub(r'<p[^>]*>', '\n', html_content)
            html_content = re.sub(r'</p>', '\n', html_content)

            # 保留换行标签
            html_content = re.sub(r'<br[^>]*>', '\n', html_content)

            # 移除其他HTML标签
            html_content = re.sub(r'<[^>]+>', '', html_content)

            # 清理多余的空白字符
            html_content = re.sub(r'\n\s*\n', '\n\n', html_content)
            html_content = html_content.strip()

            return html_content

        except Exception as e:
            print(f"⚠️ 清理HTML内容失败: {e}")
            return html_content

    def map_unit_name(self, gzh_name: str) -> str:
        """根据预加载字典把公众号名称映射成单位名称；缺失返回空串。"""
        if not gzh_name:
            return ''
        return self.gzh_unit_map.get(gzh_name.strip(), '')

    def batch_crawl_readnum(self, max_pages=200, articles_per_page=5, days_back=90):
        """
        批量抓取文章阅读量
        :param max_pages: 最大页数
        :param articles_per_page: 每页文章数
        :param days_back: 抓取多少天内的文章
        :return: 抓取结果列表
        """
        print(f"🚀 开始批量抓取阅读量数据")
        print(f"📋 参数: 最大{max_pages}页，每页{articles_per_page}篇，最近{days_back}个自然日 + 当天(到当前) 内文章")

        if not self.load_auth_info():
            print("❌ 认证信息加载失败，无法继续")
            return []

        # 验证Cookie有效性
        if not self.validate_cookie():
            print("❌ Cookie验证失败，请重新获取Cookie")
            return []

        # 初始化结果与时间窗口（自然日语义）
        # days_back = 1 => 昨日00:00:00 到 今天当前时间
        # days_back = 7 => 7天前的00:00:00 到 今天当前时间
        # 起始时间 = 今天00:00 - days_back 天
        # 结束时间 = 当前时刻
        all_results = []
        beijing_tz = timezone(timedelta(hours=8))
        now_bj = datetime.now(beijing_tz)
        today_start = now_bj.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = today_start - timedelta(days=days_back)
        print("🕒 时间窗口(自然日模式):")
        print(f"   当前北京时间: {now_bj.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   起始(含): {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} —— 从该日00:00:00开始")
        print(f"   结束(含): 当前时刻 (不等待当天结束)")

        for page in range(max_pages):
            print(f"\n{'='*50}")
            print(f"📄 处理第 {page+1}/{max_pages} 页")

            # 获取文章列表
            articles = self.get_article_list(begin_page=page, count=articles_per_page)

            if not articles:
                print("❌ 未获取到文章，停止抓取")
                break

            page_results = []
            outdated_count = 0

            for i, article in enumerate(articles):
                print(f"\n📖 处理文章 {i+1}/{len(articles)}: {article['title'][:30]}...")

                # 检查文章时间
                if article['create_time']:
                    try:
                        article_date = datetime.fromtimestamp(article['create_time'], beijing_tz)
                        if article_date < cutoff_date:
                            print(f"⏰ 文章时间 {article_date.strftime('%Y-%m-%d %H:%M:%S')} 早于窗口起始 {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}，跳过")
                            outdated_count += 1
                            continue
                    except Exception as _:
                        pass

                # 不再提前按标题跳过：后续统一 upsert (存在则更新阅读/点赞/评论/分享数)

                # 抓取文章内容和统计数据
                article_data = self.extract_article_content_and_stats(article['url'])

                if article_data:
                    # 检查是否遇到验证码
                    if article_data.get('error') == 'captcha_required':
                        print(f"🛑 遇到验证码，停止批量抓取")
                        print(f"💡 建议：手动完成验证后重新运行，或降低抓取频率")
                        break

                    # 检查是否为非文章页面
                    elif article_data.get('error') == 'not_article_page':
                        print(f"⚠️ 非文章页面，跳过")
                        continue

                    # 检测疑似key过期（阅读量=0），触发一次re-key并重试当前文章
                    elif article_data.get('error') == 'key_expired':
                        print("⚠️ 读取到阅读量为0，疑似x-wechat-key过期，尝试刷新key并重试…")
                        rekey_ok = self.refresh_wechat_key_for_article(article['url'])
                        if rekey_ok:
                            # 重试一次当前文章
                            time.sleep(random.randint(2, 4))
                            retry_data = self.extract_article_content_and_stats(article['url'])
                            if retry_data and retry_data.get('read_count', 0) > 0 and not retry_data.get('error'):
                                print("✅ 重试成功，已获取非零阅读量")
                                result = {
                                    **article,
                                    **retry_data,
                                    "pub_time": article_date.strftime("%Y-%m-%d %H:%M:%S") if article.get('create_time') else ""
                                }
                                
                                # 为内存数据添加单位名称（无论是否保存到数据库都需要）
                                gzh_name = result.get('account_name', '')
                                resolved_unit_name = ''
                                if gzh_name and not self.unit_name: # 如果没有预设unit_name，则尝试解析
                                    resolved_unit_name = self.map_unit_name(gzh_name)
                                    if resolved_unit_name:
                                        print(f"🔄(映射) 公众号 '{gzh_name}' -> 单位 '{resolved_unit_name}' (重试)")
                                        result['unit_name'] = resolved_unit_name
                                    else:
                                        print(f"⚠️(未映射) 公众号 '{gzh_name}' 未在对照表中找到，unit_name 留空")
                                        result['unit_name'] = ''
                                elif self.unit_name:
                                    # 如果有预设的unit_name，直接使用
                                    result['unit_name'] = self.unit_name
                                    resolved_unit_name = self.unit_name
                                else:
                                    result['unit_name'] = ''
                                
                                # 实时保存到数据库（与正常路径一致）
                                if self.save_to_db and self.db_manager:
                                    try:
                                        
                                        # 获取统计数据
                                        view_count = result.get('read_count', 0)
                                        like_count = result.get('like_count', 0)
                                        share_count = result.get('share_count', 0)
                                        old_like_count = result.get('old_like_count', 0)
                                        comment_count = result.get('comment_count', 0)
                                        
                                        # 根据统计数据设置analysis字段
                                        # 如果阅读量正确保存到数据库时设为0，如果阅读量为0但其他数不为0则设为-1
                                        if view_count > 0:
                                            analysis = 0  # 阅读量正常，数据有效
                                            print(f"🔍 数据分析: analysis=0 (阅读量{view_count}>0，数据正常)")
                                        elif view_count == 0 and (like_count > 0 or share_count > 0 or old_like_count > 0 or comment_count > 0):
                                            analysis = -1  # 阅读量为0但其他数据不为0，可能数据异常
                                            print(f"⚠️ 数据分析: analysis=-1 (阅读量=0但其他数据不为0: 喜欢{like_count}/点赞{old_like_count}/分享{share_count}/评论{comment_count})")
                                        else:
                                            analysis = 0  # 所有数据都为0，正常情况
                                            print(f"🔍 数据分析: analysis=0 (所有统计数据均为0，正常情况)")
                                        
                                        db_article_data = {
                                            'title': result.get('title', ''),
                                            'content': result.get('content', ''),
                                            'url': result.get('url', ''),
                                            'pub_time': result.get('pub_time', ''),
                                            'crawl_time': result.get('crawl_time', ''),
                                            'unit_name': resolved_unit_name or '',
                                            'view_count': view_count,
                                            'like_count': like_count,            # 喜欢量
                                            'share_count': share_count,          # 分享量
                                            'old_like_count': old_like_count,    # 历史点赞/点赞量
                                            'comment_count': comment_count,      # 评论量
                                            'analysis': analysis                 # 数据分析标志
                                        }
                                        
                                        status = self.db_manager.upsert_article(db_article_data)
                                        if status == 'inserted':
                                            print(f"💾(新增) 第{len(all_results)+1}篇: {result.get('title','Unknown')}")
                                        elif status == 'updated':
                                            print(f"🔄(更新) 第{len(all_results)+1}篇: {result.get('title','Unknown')} 已更新阅读/点赞/分享数")
                                        else:
                                            print(f"❌(失败) 第{len(all_results)+1}篇: {result.get('title','Unknown')}")
                                    except Exception as e:
                                        print(f"❌ 数据库保存出错: {e}")
                                else:
                                    # 尝试通过公众号名称解析单位名称
                                    gzh_name = result.get('account_name', '')
                                    if gzh_name and not self.unit_name: # 如果没有预设unit_name，则尝试解析
                                        resolved_unit_name = self.map_unit_name(gzh_name)
                                        if resolved_unit_name:
                                            print(f"🔄(映射) 公众号 '{gzh_name}' -> 单位 '{resolved_unit_name}' (内存)")
                                            result['unit_name'] = resolved_unit_name
                                        else:
                                            print(f"⚠️(未映射) 公众号 '{gzh_name}' 未在对照表中找到，unit_name 留空")
                                
                                page_results.append(result)
                                all_results.append(result)
                                print(f"✅ 完成 {len(all_results)} 篇文章")
                                # 文章间延迟逻辑保留
                            else:
                                print("❌ 重试后阅读量仍为0或失败，继续下篇")
                        else:
                            print("❌ 刷新key失败，继续下篇")
                        # 无论成败，进入下一篇
                        continue

                    # 正常的统计数据
                    else:
                        # 合并文章信息和统计数据
                        result = {
                            **article,
                            **article_data,
                            "pub_time": datetime.fromtimestamp(article['create_time'], beijing_tz).strftime("%Y-%m-%d %H:%M:%S") if article['create_time'] else ""
                        }

                        # 为内存数据添加单位名称（无论是否保存到数据库都需要，以便保存到文件时使用）
                        gzh_name = result.get('account_name', '')
                        resolved_unit_name = ''
                        if gzh_name and not self.unit_name: # 如果没有预设unit_name，则尝试解析
                            resolved_unit_name = self.map_unit_name(gzh_name)
                            if resolved_unit_name:
                                print(f"🔄(映射) 公众号 '{gzh_name}' -> 单位 '{resolved_unit_name}'")
                                result['unit_name'] = resolved_unit_name
                            else:
                                print(f"⚠️(未映射) 公众号 '{gzh_name}' 未在对照表中找到，unit_name 留空")
                                result['unit_name'] = ''
                        elif self.unit_name:
                            # 如果有预设的unit_name，直接使用
                            result['unit_name'] = self.unit_name
                            resolved_unit_name = self.unit_name
                        else:
                            result['unit_name'] = ''

                        # 实时保存到数据库
                        if self.save_to_db and self.db_manager:
                            try:
                                # 获取统计数据
                                view_count = result.get('read_count', 0)
                                like_count = result.get('like_count', 0)
                                share_count = result.get('share_count', 0)
                                old_like_count = result.get('old_like_count', 0)
                                comment_count = result.get('comment_count', 0)
                                
                                # 根据统计数据设置analysis字段
                                # 如果阅读量正确保存到数据库时设为0，如果阅读量为0但其他数不为0则设为-1
                                if view_count > 0:
                                    analysis = 0  # 阅读量正常，数据有效
                                    print(f"🔍 数据分析: analysis=0 (阅读量{view_count}>0，数据正常)")
                                elif view_count == 0 and (like_count > 0 or share_count > 0 or old_like_count > 0 or comment_count > 0):
                                    analysis = -1  # 阅读量为0但其他数据不为0，可能数据异常
                                    print(f"⚠️ 数据分析: analysis=-1 (阅读量=0但其他数据不为0: 喜欢{like_count}/点赞{old_like_count}/分享{share_count}/评论{comment_count})")
                                else:
                                    analysis = 0  # 所有数据都为0，正常情况
                                    print(f"🔍 数据分析: analysis=0 (所有统计数据均为0，正常情况)")
                                
                                db_article_data = {
                                    'title': result.get('title', ''),
                                    'content': result.get('content', ''),
                                    'url': result.get('url', ''),
                                    'pub_time': result.get('pub_time', ''),
                                    'crawl_time': result.get('crawl_time', ''),
                                    'unit_name': resolved_unit_name or '',
                                    'view_count': view_count,
                                    'like_count': like_count,            # 喜欢量
                                    'share_count': share_count,          # 分享量
                                    'old_like_count': old_like_count,    # 历史点赞/点赞量
                                    'comment_count': comment_count,      # 评论量
                                    'analysis': analysis                 # 数据分析标志
                                }

                                status = self.db_manager.upsert_article(db_article_data)
                                if status == 'inserted':
                                    print(f"💾(新增) 第{len(all_results)+1}篇: {result.get('title','Unknown')}")
                                elif status == 'updated':
                                    print(f"🔄(更新) 第{len(all_results)+1}篇: {result.get('title','Unknown')} 已更新阅读/点赞/分享数")
                                else:
                                    print(f"❌(失败) 第{len(all_results)+1}篇: {result.get('title','Unknown')}")
                            except Exception as e:
                                print(f"❌ 数据库保存出错: {e}")

                        page_results.append(result)
                        all_results.append(result)

                        print(f"✅ 完成 {len(all_results)} 篇文章")
                else:
                    print(f"❌ 统计数据获取失败")

                # 文章间延迟
                if i < len(articles) - 1:
                    low, high = self.article_delay_range if len(self.article_delay_range) == 2 else (10, 15)
                    delay = random.randint(low, high)
                    print(f"⏳ 文章间延迟 {delay} 秒...")
                    time.sleep(delay)

            print(f"📊 本页完成 {len(page_results)} 篇文章，超时 {outdated_count} 篇")

            # 如果本页大部分文章都超时，停止抓取
            if outdated_count > len(articles) * 0.7:
                print("🛑 大部分文章超出时间范围，停止抓取")
                break

            # 页面间延迟
            if page < max_pages - 1:
                low, high = self.page_delay_range if len(self.page_delay_range) == 2 else (10, 20)
                page_delay = random.randint(low, high)
                print(f"⏳ 页面间延迟 {page_delay} 秒...")
                time.sleep(page_delay)

        self.articles_data = all_results

        # 关闭数据库连接
        if self.db_manager:
            self.db_manager.disconnect()
            print("💾 数据库连接已关闭")

        print(f"\n🎉 批量抓取完成！共获取 {len(all_results)} 篇文章的统计数据")
        if self.save_to_db:
            print(f"💾 数据已实时保存到数据库")

        return all_results

    def save_to_excel(self, filename=None):
        """
        保存数据到Excel文件
        :param filename: 文件名，如果为None则自动生成
        :return: 保存的文件路径
        """
        if not self.articles_data:
            print("⚠️ 没有数据可保存")
            return None

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"./data/readnum_batch/readnum_batch_{timestamp}.xlsx"

        try:
            # 准备Excel数据 - 包含发布时间、公众号名称和单位名称
            excel_data = []
            for article in self.articles_data:
                # 获取单位名称：优先使用已有的unit_name，如果没有则通过公众号名称映射
                unit_name = article.get('unit_name', '')
                if not unit_name:
                    gzh_name = article.get('account_name', '')
                    if gzh_name:
                        unit_name = self.map_unit_name(gzh_name)
                
                excel_data.append({
                    '标题': article.get('title', ''),
                    '公众号名称': article.get('account_name', ''),
                    '单位名称': unit_name,
                    '发布时间': article.get('publish_time', '') or article.get('pub_time', ''),
                    '阅读量': article.get('read_count', 0),
                    '喜欢数': article.get('like_count', 0),
                    '点赞数': article.get('old_like_count', 0),
                    '分享数': article.get('share_count', 0),
                    '评论数': article.get('comment_count', 0),
                    '文章链接': article.get('url', ''),
                    '摘要': article.get('digest', ''),
                    '抓取时间': article.get('crawl_time', '')
                })

            # 创建DataFrame并保存
            df = pd.DataFrame(excel_data)

            # 确保目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            # 保存到Excel
            df.to_excel(filename, index=False, engine='openpyxl')

            print(f"📊 Excel数据已保存到: {filename}")
            print(f"📈 共保存 {len(excel_data)} 条记录")

            return filename

        except Exception as e:
            print(f"❌ 保存Excel文件失败: {e}")
            return None

    def save_to_json(self, filename=None):
        """
        保存数据到JSON文件
        :param filename: 文件名，如果为None则自动生成
        :return: 保存的文件路径
        """
        if not self.articles_data:
            print("⚠️ 没有数据可保存")
            return None

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"./data/readnum_batch/readnum_batch_{timestamp}.json"

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            # 准备JSON数据 - 去掉作者字段，确保包含单位名称
            json_data = []
            for article in self.articles_data:
                # 复制文章数据但去掉作者字段
                clean_article = {k: v for k, v in article.items() if k != 'author'}
                
                # 确保包含单位名称：优先使用已有的unit_name，如果没有则通过公众号名称映射
                if 'unit_name' not in clean_article or not clean_article.get('unit_name'):
                    gzh_name = clean_article.get('account_name', '')
                    if gzh_name:
                        unit_name = self.map_unit_name(gzh_name)
                        clean_article['unit_name'] = unit_name
                    else:
                        clean_article['unit_name'] = ''
                
                json_data.append(clean_article)

            # 保存到JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            print(f"💾 JSON数据已保存到: {filename}")
            print(f"📈 共保存 {len(self.articles_data)} 条记录")

            return filename

        except Exception as e:
            print(f"❌ 保存JSON文件失败: {e}")
            return None

    def generate_summary_report(self):
        """
        生成统计摘要报告
        :return: 摘要信息字典
        """
        if not self.articles_data:
            return None

        total_articles = len(self.articles_data)
        total_reads = sum(article.get('read_count', 0) for article in self.articles_data)
        total_likes = sum(article.get('like_count', 0) for article in self.articles_data)
        total_shares = sum(article.get('share_count', 0) for article in self.articles_data)

        avg_reads = total_reads / total_articles if total_articles > 0 else 0
        avg_likes = total_likes / total_articles if total_articles > 0 else 0
        avg_shares = total_shares / total_articles if total_articles > 0 else 0

        # 找出阅读量最高的文章
        top_article = max(self.articles_data, key=lambda x: x.get('read_count', 0))

        summary = {
            "total_articles": total_articles,
            "total_reads": total_reads,
            "total_likes": total_likes,
            "total_shares": total_shares,
            "avg_reads": round(avg_reads, 2),
            "avg_likes": round(avg_likes, 2),
            "avg_shares": round(avg_shares, 2),
            "top_article": {
                "title": top_article.get('title', ''),
                "read_count": top_article.get('read_count', 0),
                "like_count": top_article.get('like_count', 0),
                "url": top_article.get('url', '')
            },
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return summary

    def print_summary(self):
        """打印统计摘要"""
        summary = self.generate_summary_report()
        if not summary:
            print("⚠️ 没有数据可统计")
            return

        print(f"\n{'='*60}")
        print(f"📊 批量阅读量抓取统计摘要")
        print(f"{'='*60}")
        print(f"📖 总文章数: {summary['total_articles']}")
        print(f"👀 总阅读量: {summary['total_reads']:,}")
        print(f"👍 总点赞数: {summary['total_likes']:,}")
        print(f"📤 总分享数: {summary['total_shares']:,}")
        print(f"📊 平均阅读量: {summary['avg_reads']:,.2f}")
        print(f"📊 平均点赞数: {summary['avg_likes']:.2f}")
        print(f"📊 平均分享数: {summary['avg_shares']:.2f}")
        print(f"\n🏆 阅读量最高文章:")
        print(f"   标题: {summary['top_article']['title']}")
        print(f"   阅读量: {summary['top_article']['read_count']:,}")
        print(f"   点赞数: {summary['top_article']['like_count']:,}")
        print(f"\n⏰ 统计时间: {summary['crawl_time']}")
        print(f"{'='*60}")


def main():
    """主函数示例"""
    print("🚀 微信公众号批量阅读量抓取器")
    print("="*50)

    # 初始化爬虫
    spider = BatchReadnumSpider()

    try:
        # 批量抓取阅读量（最近7天，最多3页，每页5篇）
        results = spider.batch_crawl_readnum(max_pages=3, articles_per_page=5, days_back=1)

        if results:
            # 打印统计摘要
            spider.print_summary()

            # 保存数据
            excel_file = spider.save_to_excel()
            json_file = spider.save_to_json()

            print(f"\n✅ 抓取完成！")
            if excel_file:
                print(f"📊 Excel文件: {excel_file}")
            if json_file:
                print(f"💾 JSON文件: {json_file}")
        else:
            print("❌ 未获取到任何数据")

    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
