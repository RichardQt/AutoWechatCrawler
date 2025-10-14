import json
import re
import winreg
import atexit
import time
import threading
import os
from datetime import datetime
from mitmproxy import http

class WechatCookieExtractor:
    def __init__(self):
        self.keys_file = "wechat_keys.txt"
        self.saved_urls = set()  # 用于URL去重的集合
        self.saved_cookies = set()  # 用于Cookie去重的集合
        self.proxy_enabled = False
        # 允许通过环境变量控制监听端口，默认为 8080
        try:
            self.port = int(os.environ.get('MITM_PORT', '8080'))
        except Exception:
            self.port = 8080
        self.init_keys_file()

        # 立即尝试设置代理，但使用重试机制
        self.setup_proxy_with_retry()

        # 注册程序退出时的清理函数
        atexit.register(self.cleanup_proxy)

    def init_keys_file(self):
        """初始化keys文件"""
        with open(self.keys_file, "w", encoding="utf-8") as f:
            f.write("=== 微信公众号Keys和URLs记录 ===\n")
            f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    def setup_proxy_with_retry(self):
        """立即设置代理，使用重试机制确保成功"""
        print("🚀 正在设置系统代理...")

        # 立即尝试设置代理
        if self.set_system_proxy():
            print("✅ 系统代理设置成功")
            return True

        # 如果失败，启动后台重试机制
        print("⚠️ 初次代理设置失败，启动后台重试...")
        retry_timer = threading.Timer(2.0, self.retry_proxy_setup)
        retry_timer.start()
        return False

    def retry_proxy_setup(self):
        """后台重试代理设置"""
        print("🔄 重试设置系统代理...")
        max_retries = 10

        for attempt in range(max_retries):
            if self.is_proxy_port_ready():
                print(f"✅ mitmproxy端口已就绪 (重试 {attempt + 1} 次)")
                if self.set_system_proxy():
                    print("✅ 代理重试设置成功")
                    return True
            time.sleep(2)

        print("⚠️ 代理重试设置失败，但继续运行...")
        return False

    def is_proxy_port_ready(self):
        """检查代理端口是否可用"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', self.port))
            sock.close()
            return result == 0
        except:
            return False

    def set_system_proxy(self):
        """设置系统代理为127.0.0.1:8080"""
        try:
            # 打开注册表项
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                               0, winreg.KEY_SET_VALUE)

            # 设置代理服务器
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{self.port}")

            # 启用代理
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)

            # 关闭注册表项
            winreg.CloseKey(key)

            self.proxy_enabled = True
            print(f"✅ 系统代理已设置为 127.0.0.1:{self.port}")
            return True

        except Exception as e:
            print(f"❌ 设置系统代理失败: {e}")
            return False
    
    def tls_clienthello(self, data):
        """处理TLS握手，忽略非微信域名的证书错误"""
        # 只对微信相关域名进行SSL拦截
        wechat_domains = [
            "mp.weixin.qq.com",
        ]
        
        # 如果不是微信域名，不进行SSL拦截
        if not any(domain in str(data.context.server.address) for domain in wechat_domains):
            return
        
    def request(self, flow: http.HTTPFlow) -> None:
        """拦截请求，提取微信相关的Cookie和URL"""
        request = flow.request
        
        # 仅处理 mp.weixin.qq.com 的请求
        if "mp.weixin.qq.com" not in request.pretty_host:
            return
        
        # 文章页或关键接口请求
        if self.is_wechat_article_url(request.pretty_url) or self.is_wechat_important_api(request.pretty_url):
            self.save_keys_and_url(request)
    
    def is_wechat_article_url(self, url: str) -> bool:
        """精确判断是否为微信公众号文章链接"""
        # 微信公众号文章URL格式：https://mp.weixin.qq.com/s?__biz=xxx&mid=xxx&sn=xxx
        pattern = r'^https?://mp\.weixin\.qq\.com/s\?.*__biz='
        return bool(re.match(pattern, url))

    def is_wechat_important_api(self, url: str) -> bool:
        """关键接口: mp/getappmsgext 等，用于携带 appmsg_token/cookie 等"""
        return bool(re.search(r'^https?://mp\.weixin\.qq\.com/mp/getappmsgext', url))
    
    def is_wechat_request(self, request) -> bool:
        """判断是否为微信公众号相关请求"""
        wechat_domains = [
            "mp.weixin.qq.com",
        ]
        
        return any(domain in request.pretty_host for domain in wechat_domains)
    
    def save_keys_and_url(self, request):
        """保存Cookie、URL和关键Headers到统一文件，避免重复记录"""
        # 过滤掉jsmonitor等监控请求
        if "jsmonitor" in request.pretty_url:
            return

        # URL去重检查
        if request.pretty_url in self.saved_urls:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 提取并合并所有关键Cookie为一行
        cookies_string = ""
        if request.cookies:
            cookie_parts = []
            key_cookies = ["session_key", "uin", "skey", "p_skey", "wxuin", "data_bizuin", "appmsg_token", "pass_ticket", "wap_sid2"]

            for cookie_name, cookie_value in request.cookies.items():
                if any(key in cookie_name.lower() for key in key_cookies) or len(cookie_value) > 20:
                    cookie_parts.append(f"{cookie_name}={cookie_value}")

            if cookie_parts:
                cookies_string = "; ".join(cookie_parts)

        # 提取关键的请求头参数（参考spider_readnum.py中的成功实现）
        key_headers = {}
        important_headers = [
            'x-wechat-key', 'x-wechat-uin', 'exportkey',
            'user-agent', 'accept', 'accept-language',
            'cache-control', 'sec-fetch-site', 'sec-fetch-mode',
            'sec-fetch-dest', 'priority'
        ]

        for header_name in important_headers:
            if header_name in request.headers:
                key_headers[header_name] = request.headers[header_name]

        # 如果没有cookie或cookie已经记录过，则不保存
        if not cookies_string or cookies_string in self.saved_cookies:
            return

        # 添加到已保存的集合中
        self.saved_urls.add(request.pretty_url)
        self.saved_cookies.add(cookies_string)

        with open(self.keys_file, "a", encoding="utf-8") as f:
            f.write(f"{'='*60}\n")
            f.write(f"time: {timestamp}\n")
            f.write(f"allurl: {request.pretty_url}\n")
            f.write(f"Cookies: {cookies_string}\n")

            # 保存关键的请求头参数
            if key_headers:
                f.write("Headers:\n")
                for header_name, header_value in key_headers.items():
                    f.write(f"  {header_name}: {header_value}\n")

            f.write("\n")

        # 仅在成功保存时打印简洁信息并自动关闭代理
        print(f"✅ 已保存微信公众号文章Cookie: {request.pretty_url}")
        print("🎯 Cookie抓取成功，准备自动关闭代理...")

        # 延迟关闭代理，确保数据保存完成
        cleanup_timer = threading.Timer(2.0, self.auto_cleanup_after_success)
        cleanup_timer.start()

    def auto_cleanup_after_success(self):
        """抓取成功后自动清理代理"""
        print("🧹 自动清理代理设置...")
        self.cleanup_proxy()
        print("✅ 代理已关闭，可以开始爬取阅读量数据")

    def cleanup_proxy(self):
        """清理系统代理设置"""
        if not self.proxy_enabled:
            return

        try:
            # 打开注册表项
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                               0, winreg.KEY_SET_VALUE)

            # 禁用代理
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)

            # 清空代理服务器设置
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "")

            # 关闭注册表项
            winreg.CloseKey(key)

            self.proxy_enabled = False
            print("✅ 系统代理已关闭")

        except Exception as e:
            print(f"❌ 关闭系统代理失败: {e}")

# 创建实例供mitmproxy使用
addons = [WechatCookieExtractor()]