#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进版Cookie读取器 - 直接保存到数据库
解决Cookie解析错误，移除本地文件依赖
"""

import subprocess
import time
import logging
import json
import re
import os
import threading
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

# 添加项目路径
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.database.database_manager import DatabaseManager
from src.proxy.enhanced_proxy_manager_server import WindowsServerProxyManager

class ReadCookieDB:
    """改进版Cookie读取器 - 直接保存到数据库"""
    
    def __init__(self, db_config=None, use_windows_server_mode=True):
        """
        初始化Cookie读取器
        
        Args:
            db_config: 数据库配置
            use_windows_server_mode: 是否使用Windows Server优化模式
        """
        self.logger = logging.getLogger(__name__)
        
        # 数据库连接
        self.db_manager = DatabaseManager(**(db_config or {}))
        
        # 使用Windows Server优化的代理管理器
        if use_windows_server_mode:
            self.proxy_manager = WindowsServerProxyManager()
        else:
            from src.proxy.proxy_manager import ProxyManager
            self.proxy_manager = ProxyManager()
        
        self.mitmproxy_process = None
        self.cookies_cache = {}  # 内存中的Cookie缓存
        self.capture_thread = None
        self.stop_capture = threading.Event()
        
        # Cookie解析配置
        self.cookie_patterns = {
            'appmsg_token': r'appmsg_token=([^;]+)',
            'pass_ticket': r'pass_ticket=([^&;]+)',
            'wxuin': r'wxuin=(\d+)',
            'uin': r'uin=([^;]+)',
            'key': r'key=([^;]+)',
            'data_bizuin': r'data_bizuin=(\d+)',
            'data_ticket': r'data_ticket=([^;]+)',
            'wap_sid2': r'wap_sid2=([^;]+)',
            'uuid': r'uuid=([^;]+)',
            'wxuin': r'wxuin=([^;]+)',
            'ua_id': r'ua_id=([^;]+)',
            'pgv_pvi': r'pgv_pvi=([^;]+)',
            'pgv_si': r'pgv_si=([^;]+)'
        }
    
    def start_cookie_extractor(self) -> bool:
        """启动Cookie提取器"""
        try:
            self.logger.info("🚀 启动Cookie提取器（数据库版）...")
            
            # 创建mitmproxy脚本
            script_path = self._create_mitm_script()
            
            # 启动mitmproxy
            if isinstance(self.proxy_manager, WindowsServerProxyManager):
                self.mitmproxy_process = self.proxy_manager.start_mitmproxy_server(script_path)
            else:
                self.mitmproxy_process = self._start_standard_mitmproxy(script_path)
            
            if not self.mitmproxy_process:
                self.logger.error("❌ mitmproxy启动失败")
                return False
            
            # 启用系统代理
            if isinstance(self.proxy_manager, WindowsServerProxyManager):
                self.proxy_manager.enable_system_proxy()
            else:
                self.proxy_manager.enable_proxy(8080)
            
            # 启动Cookie捕获线程
            self.stop_capture.clear()
            self.capture_thread = threading.Thread(target=self._capture_cookies_thread)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            self.logger.info("✅ Cookie提取器启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 启动Cookie提取器失败: {e}")
            return False
    
    def _create_mitm_script(self) -> Path:
        """创建mitmproxy脚本"""
        script_dir = Path(__file__).parent / "temp"
        script_dir.mkdir(exist_ok=True)
        script_path = script_dir / "cookie_extractor_db.py"
        
        script_content = '''import json
import re
import logging
from datetime import datetime
from mitmproxy import http

class WechatCookieExtractorDB:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.captured_data = {}
        
    def request(self, flow: http.HTTPFlow) -> None:
        """拦截请求，提取微信Cookie和参数"""
        request = flow.request
        
        # 判断是否为微信公众号请求
        if not self._is_wechat_request(request.pretty_url):
            return
        
        # 提取URL参数
        url_params = self._extract_url_params(request.pretty_url)
        
        # 提取Cookie
        cookies = self._extract_cookies(request)
        
        # 提取Headers
        headers = self._extract_headers(request)
        
        # 合并数据
        if url_params.get('__biz'):
            biz = url_params['__biz']
            self.captured_data[biz] = {
                'url': request.pretty_url,
                'url_params': url_params,
                'cookies': cookies,
                'headers': headers,
                'timestamp': datetime.now().isoformat(),
                'host': request.pretty_host
            }
            
            # 保存到临时文件供主程序读取
            self._save_to_temp_file()
            
            self.logger.info(f"✅ 捕获微信Cookie: {biz}")
    
    def _is_wechat_request(self, url: str) -> bool:
        """判断是否为微信请求"""
        patterns = [
            r'mp\\.weixin\\.qq\\.com/s\\?',
            r'mp\\.weixin\\.qq\\.com/mp/getappmsgext',
            r'mp\\.weixin\\.qq\\.com/mp/appmsg_comment'
        ]
        return any(re.search(pattern, url) for pattern in patterns)
    
    def _extract_url_params(self, url: str) -> dict:
        """提取URL参数"""
        params = {}
        
        # 提取常见参数
        patterns = {
            '__biz': r'__biz=([^&]+)',
            'mid': r'mid=([^&]+)',
            'idx': r'idx=([^&]+)',
            'sn': r'sn=([^&]+)',
            'chksm': r'chksm=([^&]+)',
            'key': r'key=([^&]+)',
            'pass_ticket': r'pass_ticket=([^&]+)',
            'appmsg_token': r'appmsg_token=([^&]+)',
            'uin': r'uin=([^&]+)',
            'wxuin': r'wxuin=([^&]+)'
        }
        
        for name, pattern in patterns.items():
            match = re.search(pattern, url)
            if match:
                params[name] = match.group(1)
        
        return params
    
    def _extract_cookies(self, request) -> dict:
        """提取所有Cookie"""
        cookies = {}
        
        # 从Cookie头提取
        if 'Cookie' in request.headers:
            cookie_str = request.headers['Cookie']
            # 解析Cookie字符串
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
        
        # 从request.cookies提取
        if request.cookies:
            for name, value in request.cookies.items():
                cookies[name] = value
        
        return cookies
    
    def _extract_headers(self, request) -> dict:
        """提取关键Headers"""
        important_headers = [
            'User-Agent', 'X-Wechat-Key', 'X-Wechat-Uin',
            'Exportkey', 'Referer', 'Accept', 'Accept-Language'
        ]
        
        headers = {}
        for header in important_headers:
            if header in request.headers:
                headers[header] = request.headers[header]
            # 处理大小写不敏感
            elif header.lower() in request.headers:
                headers[header] = request.headers[header.lower()]
        
        return headers
    
    def _save_to_temp_file(self):
        """保存到临时文件"""
        try:
            import tempfile
            temp_file = tempfile.gettempdir() + '/wechat_cookies_db.json'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.captured_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存临时文件失败: {e}")

addons = [WechatCookieExtractorDB()]
'''
        
        script_path.write_text(script_content, encoding='utf-8')
        return script_path
    
    def _start_standard_mitmproxy(self, script_path: Path) -> subprocess.Popen:
        """启动标准mitmproxy"""
        cmd = [
            'mitmdump',
            '-s', str(script_path),
            '--listen-port', '8080',
            '--ssl-insecure',
            '--set', 'stream_large_bodies=1m',
            '--anticache',
            '--anticomp'
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        return process
    
    def _capture_cookies_thread(self):
        """Cookie捕获线程"""
        import tempfile
        temp_file = tempfile.gettempdir() + '/wechat_cookies_db.json'
        
        while not self.stop_capture.is_set():
            try:
                # 检查临时文件
                if os.path.exists(temp_file):
                    with open(temp_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 处理新捕获的Cookie
                    for biz, cookie_data in data.items():
                        if biz not in self.cookies_cache:
                            self.cookies_cache[biz] = cookie_data
                            
                            # 解析并保存到数据库
                            self._save_cookie_to_db(cookie_data)
                            
                            self.logger.info(f"📝 已保存Cookie到数据库: {biz}")
                
            except Exception as e:
                self.logger.debug(f"读取临时文件: {e}")
            
            time.sleep(2)
    
    def _save_cookie_to_db(self, cookie_data: dict):
        """保存Cookie到数据库"""
        try:
            # 提取关键信息
            url = cookie_data.get('url', '')
            cookies = cookie_data.get('cookies', {})
            url_params = cookie_data.get('url_params', {})
            headers = cookie_data.get('headers', {})
            
            # 合并所有认证信息
            auth_info = {
                'biz': url_params.get('__biz', ''),
                'appmsg_token': url_params.get('appmsg_token') or cookies.get('appmsg_token', ''),
                'pass_ticket': url_params.get('pass_ticket') or cookies.get('pass_ticket', ''),
                'wxuin': cookies.get('wxuin', ''),
                'uin': cookies.get('uin', ''),
                'key': url_params.get('key') or cookies.get('key', ''),
                'cookie': '; '.join([f"{k}={v}" for k, v in cookies.items()]),
                'user_agent': headers.get('User-Agent', ''),
                'url': url,
                'capture_time': datetime.now()
            }
            
            # 保存到数据库（需要根据您的数据库结构调整）
            # 这里假设有一个专门存储Cookie的表
            success = self._insert_cookie_record(auth_info)
            
            if success:
                self.logger.info(f"✅ Cookie已保存到数据库: {auth_info['biz']}")
            else:
                self.logger.error(f"❌ Cookie保存到数据库失败: {auth_info['biz']}")
                
        except Exception as e:
            self.logger.error(f"保存Cookie到数据库出错: {e}")
    
    def _insert_cookie_record(self, auth_info: dict) -> bool:
        """插入Cookie记录到数据库"""
        try:
            # 这里需要根据您的实际数据库表结构调整
            # 示例：保存到一个cookie_records表
            sql = """
            INSERT INTO wechat_cookies (
                biz, appmsg_token, pass_ticket, wxuin, uin, 
                cookie_key, full_cookie, user_agent, url, capture_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                appmsg_token = VALUES(appmsg_token),
                pass_ticket = VALUES(pass_ticket),
                wxuin = VALUES(wxuin),
                uin = VALUES(uin),
                cookie_key = VALUES(cookie_key),
                full_cookie = VALUES(full_cookie),
                user_agent = VALUES(user_agent),
                url = VALUES(url),
                capture_time = VALUES(capture_time)
            """
            
            params = (
                auth_info['biz'],
                auth_info['appmsg_token'],
                auth_info['pass_ticket'],
                auth_info['wxuin'],
                auth_info['uin'],
                auth_info['key'],
                auth_info['cookie'],
                auth_info['user_agent'],
                auth_info['url'],
                auth_info['capture_time']
            )
            
            # 执行SQL（这里假设db_manager有execute方法）
            # 实际使用时需要根据您的DatabaseManager类调整
            cursor = self.db_manager.connection.cursor()
            cursor.execute(sql, params)
            self.db_manager.connection.commit()
            cursor.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"数据库插入失败: {e}")
            return False
    
    def get_latest_cookies(self, biz: str = None) -> Optional[Dict[str, Any]]:
        """获取最新的Cookie信息"""
        try:
            if biz and biz in self.cookies_cache:
                return self._parse_auth_info(self.cookies_cache[biz])
            elif self.cookies_cache:
                # 返回最新的一个
                latest_biz = list(self.cookies_cache.keys())[-1]
                return self._parse_auth_info(self.cookies_cache[latest_biz])
            
            # 如果内存中没有，尝试从数据库读取
            return self._get_cookie_from_db(biz)
            
        except Exception as e:
            self.logger.error(f"获取Cookie失败: {e}")
            return None
    
    def _parse_auth_info(self, cookie_data: dict) -> dict:
        """解析认证信息"""
        cookies = cookie_data.get('cookies', {})
        url_params = cookie_data.get('url_params', {})
        
        # 构建Cookie字符串
        cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
        
        return {
            'biz': url_params.get('__biz', ''),
            'appmsg_token': url_params.get('appmsg_token') or cookies.get('appmsg_token', ''),
            'pass_ticket': url_params.get('pass_ticket') or cookies.get('pass_ticket', ''),
            'cookie': cookie_str,
            'wxuin': cookies.get('wxuin', ''),
            'uin': cookies.get('uin', ''),
            'key': url_params.get('key') or cookies.get('key', '')
        }
    
    def _get_cookie_from_db(self, biz: str = None) -> Optional[Dict[str, Any]]:
        """从数据库获取Cookie"""
        try:
            sql = """
            SELECT biz, appmsg_token, pass_ticket, wxuin, uin, 
                   cookie_key, full_cookie, user_agent, url
            FROM wechat_cookies
            """
            
            if biz:
                sql += " WHERE biz = %s"
                params = (biz,)
            else:
                sql += " ORDER BY capture_time DESC LIMIT 1"
                params = None
            
            cursor = self.db_manager.connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return {
                    'biz': result[0],
                    'appmsg_token': result[1],
                    'pass_ticket': result[2],
                    'wxuin': result[3],
                    'uin': result[4],
                    'key': result[5],
                    'cookie': result[6]
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"从数据库读取Cookie失败: {e}")
            return None
    
    def stop_cookie_extractor(self):
        """停止Cookie提取器"""
        try:
            self.logger.info("🛑 正在停止Cookie提取器...")
            
            # 停止捕获线程
            self.stop_capture.set()
            if self.capture_thread:
                self.capture_thread.join(timeout=5)
            
            # 停止mitmproxy
            if isinstance(self.proxy_manager, WindowsServerProxyManager):
                self.proxy_manager.cleanup()
            else:
                if self.mitmproxy_process:
                    self.mitmproxy_process.terminate()
                    try:
                        self.mitmproxy_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.mitmproxy_process.kill()
                
                self.proxy_manager.disable_proxy()
            
            # 清理临时文件
            import tempfile
            temp_file = tempfile.gettempdir() + '/wechat_cookies_db.json'
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            self.logger.info("✅ Cookie提取器已停止")
            
        except Exception as e:
            self.logger.error(f"停止Cookie提取器失败: {e}")
    
    def validate_cookie(self, auth_info: dict) -> bool:
        """验证Cookie是否有效"""
        try:
            import requests
            
            # 构建测试URL
            test_url = "https://mp.weixin.qq.com/mp/getappmsgext"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Cookie': auth_info.get('cookie', '')
            }
            
            params = {
                '__biz': auth_info.get('biz', ''),
                'appmsg_token': auth_info.get('appmsg_token', ''),
                'x5': '0'
            }
            
            response = requests.get(test_url, headers=headers, params=params, timeout=10)
            
            # 检查响应
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'appmsgstat' in data:
                        return True
                except:
                    pass
            
            return False
            
        except Exception as e:
            self.logger.error(f"验证Cookie失败: {e}")
            return False


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 创建Cookie读取器
    reader = ReadCookieDB()
    
    # 启动提取器
    if reader.start_cookie_extractor():
        print("Cookie提取器已启动，请在微信中打开公众号文章...")
        
        try:
            # 等待Cookie
            for _ in range(60):
                time.sleep(2)
                cookies = reader.get_latest_cookies()
                if cookies:
                    print(f"✅ 获取到Cookie: {cookies['biz']}")
                    
                    # 验证Cookie
                    if reader.validate_cookie(cookies):
                        print("✅ Cookie验证成功")
                    else:
                        print("❌ Cookie验证失败")
                    break
        finally:
            reader.stop_cookie_extractor()