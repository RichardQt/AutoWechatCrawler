# 微信抓包 Addon
import re
from datetime import datetime
from mitmproxy import http
from pathlib import Path

class WechatCaptureAddon:
    def __init__(self):
        self.keys_file = Path("wechat_keys.txt")
        self.saved_urls = set()  # URL去重
        self.saved_cookies = set()  # Cookie去重
        self.init_keys_file()
        
    def init_keys_file(self):
        """初始化或追加到keys文件"""
        if not self.keys_file.exists():
            with open(self.keys_file, "w", encoding="utf-8") as f:
                f.write("=== 微信公众号Keys和URLs记录 ===\n")
                f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
    def request(self, flow: http.HTTPFlow) -> None:
        """拦截请求，提取微信相关的Cookie和URL"""
        request = flow.request
        # 拦截文章页或关键接口
        if self.is_wechat_article_url(request.pretty_url) or self.is_wechat_important_api(request.pretty_url):
            self.save_keys_and_url(request)
            
    def is_wechat_article_url(self, url: str) -> bool:
        """判断是否为公众号文章页链接"""
        pattern = r'^https?://mp\.weixin\.qq\.com/s\?.*__biz='
        return bool(re.match(pattern, url))

    def is_wechat_important_api(self, url: str) -> bool:
        """关键接口: mp/getappmsgext 等，用于携带 appmsg_token/cookie 等"""
        return bool(re.search(r'^https?://mp\.weixin\.qq\.com/mp/getappmsgext', url))
        
    def save_keys_and_url(self, request):
        """保存Cookie、URL和关键Headers"""
        # 过滤掉jsmonitor等监控请求
        if "jsmonitor" in request.pretty_url:
            return
            
        # URL去重检查
        if request.pretty_url in self.saved_urls:
            return
            
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 提取Cookie
        cookies_string = ""
        if request.cookies:
            cookie_parts = []
            key_cookies = ["wxuin", "appmsg_token", "pass_ticket", "wap_sid2"]
            
            for cookie_name, cookie_value in request.cookies.items():
                if any(key in cookie_name.lower() for key in key_cookies) or len(cookie_value) > 20:
                    cookie_parts.append(f"{cookie_name}={cookie_value}")
                    
            if cookie_parts:
                cookies_string = "; ".join(cookie_parts)
                
        # 提取关键请求头
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
                
        # 如果没有cookie或已记录，跳过
        if not cookies_string or cookies_string in self.saved_cookies:
            return
            
        # 添加到已保存集合
        self.saved_urls.add(request.pretty_url)
        self.saved_cookies.add(cookies_string)
        
        # 保存到文件
        with open(self.keys_file, "a", encoding="utf-8") as f:
            f.write(f"{'='*60}\n")
            f.write(f"time: {timestamp}\n")
            f.write(f"allurl: {request.pretty_url}\n")
            f.write(f"Cookies: {cookies_string}\n")
            
            if key_headers:
                f.write("Headers:\n")
                for header_name, header_value in key_headers.items():
                    f.write(f"  {header_name}: {header_value}\n")
                    
            f.write("\n")
            
        print(f"✅ 已捕获微信公众号文章: {request.pretty_url}")
        print(f"📝 数据已保存到: {self.keys_file.absolute()}")

addons = [WechatCaptureAddon()]
