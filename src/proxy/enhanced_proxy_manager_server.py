#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows Server 增强版代理管理器
专门解决Windows Server环境下的代理和抓包问题
"""

import subprocess
import time
import winreg
import logging
import socket
import os
import sys
import ctypes
import json
import psutil
from typing import Optional, Dict, Any
from pathlib import Path

class WindowsServerProxyManager:
    """Windows Server环境专用代理管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.proxy_port = 8080
        self.mitmproxy_process = None
        self.original_proxy_settings = {}
        self.is_windows_server = self._detect_windows_server()
        
        # Windows Server特定配置
        if self.is_windows_server:
            self.logger.info("检测到Windows Server环境，启用特殊配置")
            self._configure_for_windows_server()
    
    def _detect_windows_server(self) -> bool:
        """检测是否为Windows Server环境"""
        try:
            import platform
            version = platform.version()
            release = platform.release()
            
            # Windows Server通常包含"Server"字样
            is_server = "Server" in release or "Server" in version
            
            # 也可以通过注册表检测
            if not is_server:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                       r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                                       0, winreg.KEY_READ)
                    product_name, _ = winreg.QueryValueEx(key, "ProductName")
                    winreg.CloseKey(key)
                    is_server = "Server" in str(product_name)
                except:
                    pass
            
            return is_server
        except:
            return False
    
    def _configure_for_windows_server(self):
        """Windows Server特殊配置"""
        try:
            # 1. 确保以管理员权限运行
            if not self._is_admin():
                self.logger.warning("⚠️ 未以管理员权限运行，某些功能可能受限")
            
            # 2. 配置Windows防火墙规则
            self._configure_firewall()
            
            # 3. 配置证书策略
            self._configure_certificate_policy()
            
        except Exception as e:
            self.logger.error(f"Windows Server配置失败: {e}")
    
    def _is_admin(self) -> bool:
        """检查是否有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def _configure_firewall(self):
        """配置Windows防火墙规则"""
        try:
            # 添加防火墙规则允许mitmproxy
            rules = [
                f'netsh advfirewall firewall add rule name="mitmproxy-in-{self.proxy_port}" dir=in action=allow protocol=TCP localport={self.proxy_port}',
                f'netsh advfirewall firewall add rule name="mitmproxy-out-{self.proxy_port}" dir=out action=allow protocol=TCP localport={self.proxy_port}',
                'netsh advfirewall firewall add rule name="mitmproxy-app" dir=in action=allow program="mitmdump.exe"',
                'netsh advfirewall firewall add rule name="mitmproxy-app" dir=out action=allow program="mitmdump.exe"'
            ]
            
            for rule in rules:
                try:
                    subprocess.run(rule, shell=True, capture_output=True, text=True)
                    self.logger.debug(f"防火墙规则已添加: {rule}")
                except:
                    pass
                    
        except Exception as e:
            self.logger.warning(f"配置防火墙规则失败: {e}")
    
    def _configure_certificate_policy(self):
        """配置证书策略"""
        try:
            # Windows Server可能需要特殊的证书安装方式
            mitmproxy_cert_path = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.cer"
            
            if not mitmproxy_cert_path.exists():
                # 先运行一次mitmdump生成证书
                self.logger.info("生成mitmproxy证书...")
                subprocess.run(["mitmdump", "--help"], capture_output=True)
                time.sleep(2)
            
            if mitmproxy_cert_path.exists():
                # 使用PowerShell导入证书到受信任的根证书颁发机构
                ps_script = f'''
                $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2("{mitmproxy_cert_path}")
                $store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "LocalMachine")
                $store.Open("ReadWrite")
                $store.Add($cert)
                $store.Close()
                '''
                
                try:
                    subprocess.run(["powershell", "-Command", ps_script], 
                                 capture_output=True, text=True, check=True)
                    self.logger.info("✅ mitmproxy证书已安装到系统信任存储")
                except subprocess.CalledProcessError as e:
                    # 如果LocalMachine失败，尝试CurrentUser
                    ps_script_user = ps_script.replace('"LocalMachine"', '"CurrentUser"')
                    subprocess.run(["powershell", "-Command", ps_script_user], 
                                 capture_output=True, text=True)
                    self.logger.info("✅ mitmproxy证书已安装到用户信任存储")
                    
        except Exception as e:
            self.logger.warning(f"证书配置失败: {e}")
    
    def start_mitmproxy_server(self, cookie_extractor_path: str = None) -> Optional[subprocess.Popen]:
        """启动mitmproxy服务器（Windows Server优化版）"""
        try:
            # 查找cookie_extractor.py
            if not cookie_extractor_path:
                current_dir = Path(__file__).parent
                cookie_extractor_path = current_dir / "cookie_extractor_server.py"
                
                # 如果不存在，创建一个
                if not cookie_extractor_path.exists():
                    self._create_cookie_extractor(cookie_extractor_path)
            
            # 构建mitmproxy命令
            cmd = [
                'mitmdump',
                '-s', str(cookie_extractor_path),
                '--listen-host', '0.0.0.0',  # 监听所有接口
                '--listen-port', str(self.proxy_port),
                '--ssl-insecure',
                '--set', 'confdir=~/.mitmproxy',
                '--set', 'stream_large_bodies=1m',  # 限制大文件流
                '--set', 'keep_host_header=true',
                '--set', 'ssl_version_client=all',
                '--set', 'ssl_version_server=all',
                '--anticache',
                '--anticomp'
            ]
            
            # Windows Server特定环境变量
            env = os.environ.copy()
            env['MITMPROXY_CONFDIR'] = str(Path.home() / ".mitmproxy")
            
            # 创建进程（Windows Server需要特殊的创建标志）
            if sys.platform == 'win32':
                CREATE_NO_WINDOW = 0x08000000
                self.mitmproxy_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    creationflags=CREATE_NO_WINDOW
                )
            else:
                self.mitmproxy_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env
                )
            
            self.logger.info(f"✅ mitmproxy已启动 (PID: {self.mitmproxy_process.pid})")
            
            # 等待端口就绪
            if self.wait_for_port_ready():
                return self.mitmproxy_process
            else:
                self.logger.error("mitmproxy端口未就绪")
                self.stop_mitmproxy_server()
                return None
                
        except Exception as e:
            self.logger.error(f"启动mitmproxy失败: {e}")
            return None
    
    def _create_cookie_extractor(self, path: Path):
        """创建优化的Cookie提取器脚本"""
        content = '''import json
import re
from datetime import datetime
from mitmproxy import http
import logging
import threading
import time

class WechatCookieExtractorServer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.saved_cookies = {}
        self.lock = threading.Lock()
        self.last_save_time = 0
        
    def request(self, flow: http.HTTPFlow) -> None:
        """拦截请求，提取微信相关的Cookie"""
        request = flow.request
        
        # 仅拦截微信公众号文章链接
        if not self.is_wechat_article_url(request.pretty_url):
            return
            
        # 提取Cookie和Headers
        cookies_dict = {}
        headers_dict = {}
        
        # 提取所有Cookie
        if request.cookies:
            for name, value in request.cookies.items():
                cookies_dict[name] = value
        
        # 提取关键Headers
        important_headers = [
            'x-wechat-key', 'x-wechat-uin', 'exportkey',
            'user-agent', 'referer'
        ]
        
        for header_name in important_headers:
            if header_name in request.headers:
                headers_dict[header_name] = request.headers[header_name]
        
        # 解析URL获取biz
        biz_match = re.search(r"__biz=([^&]+)", request.pretty_url)
        biz = biz_match.group(1) if biz_match else None
        
        if biz and cookies_dict:
            with self.lock:
                self.saved_cookies[biz] = {
                    'url': request.pretty_url,
                    'cookies': cookies_dict,
                    'headers': headers_dict,
                    'timestamp': datetime.now().isoformat(),
                    'biz': biz
                }
                
                # 定期保存到数据库（通过临时文件）
                current_time = time.time()
                if current_time - self.last_save_time > 5:  # 每5秒保存一次
                    self.save_to_temp_file()
                    self.last_save_time = current_time
                
                self.logger.info(f"✅ 已捕获Cookie: {biz}")
    
    def is_wechat_article_url(self, url: str) -> bool:
        """判断是否为微信公众号文章链接"""
        pattern = r'^https?://mp\\.weixin\\.qq\\.com/s\\?.*__biz='
        return bool(re.match(pattern, url))
    
    def save_to_temp_file(self):
        """保存到临时文件供主程序读取"""
        try:
            import tempfile
            temp_file = tempfile.gettempdir() + '/wechat_cookies_temp.json'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_cookies, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存临时文件失败: {e}")

addons = [WechatCookieExtractorServer()]
'''
        path.write_text(content, encoding='utf-8')
    
    def wait_for_port_ready(self, timeout: int = 10) -> bool:
        """等待端口就绪"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_port_listening(self.proxy_port):
                self.logger.info(f"✅ 端口 {self.proxy_port} 已就绪")
                return True
            time.sleep(1)
        return False
    
    def is_port_listening(self, port: int) -> bool:
        """检查端口是否在监听"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def enable_system_proxy(self) -> bool:
        """启用系统代理（Windows Server优化）"""
        try:
            # 使用注册表和netsh双重设置
            # 1. 注册表设置
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                               0, winreg.KEY_SET_VALUE)
            
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{self.proxy_port}")
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.0.0.1;<local>")
            winreg.CloseKey(key)
            
            # 2. 使用netsh设置（Windows Server可能需要）
            subprocess.run(f'netsh winhttp set proxy 127.0.0.1:{self.proxy_port}', 
                         shell=True, capture_output=True)
            
            # 3. 刷新系统设置
            subprocess.run('ipconfig /flushdns', shell=True, capture_output=True)
            
            self.logger.info(f"✅ 系统代理已设置为 127.0.0.1:{self.proxy_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"设置系统代理失败: {e}")
            return False
    
    def disable_system_proxy(self) -> bool:
        """禁用系统代理"""
        try:
            # 1. 注册表设置
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                               0, winreg.KEY_SET_VALUE)
            
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "")
            winreg.CloseKey(key)
            
            # 2. 清除netsh代理
            subprocess.run('netsh winhttp reset proxy', shell=True, capture_output=True)
            
            self.logger.info("✅ 系统代理已禁用")
            return True
            
        except Exception as e:
            self.logger.error(f"禁用系统代理失败: {e}")
            return False
    
    def stop_mitmproxy_server(self):
        """停止mitmproxy服务器"""
        try:
            if self.mitmproxy_process:
                # 温和终止
                self.mitmproxy_process.terminate()
                try:
                    self.mitmproxy_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 强制终止
                    self.mitmproxy_process.kill()
                
                self.logger.info("✅ mitmproxy已停止")
                self.mitmproxy_process = None
            
            # 清理所有mitmdump进程
            self.kill_all_mitmproxy_processes()
            
        except Exception as e:
            self.logger.error(f"停止mitmproxy失败: {e}")
    
    def kill_all_mitmproxy_processes(self):
        """强制停止所有mitmproxy相关进程"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] in ['mitmdump.exe', 'mitmproxy.exe', 'mitmweb.exe']:
                    try:
                        proc.kill()
                        self.logger.info(f"已终止进程: {proc.info['name']} (PID: {proc.info['pid']})")
                    except:
                        pass
        except Exception as e:
            self.logger.warning(f"清理进程失败: {e}")
    
    def get_captured_cookies(self) -> Dict[str, Any]:
        """获取捕获的Cookie数据"""
        try:
            import tempfile
            temp_file = tempfile.gettempdir() + '/wechat_cookies_temp.json'
            
            if os.path.exists(temp_file):
                with open(temp_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
            
        except Exception as e:
            self.logger.error(f"读取Cookie数据失败: {e}")
            return {}
    
    def cleanup(self):
        """清理资源"""
        self.stop_mitmproxy_server()
        self.disable_system_proxy()
        
        # 清理临时文件
        try:
            import tempfile
            temp_file = tempfile.gettempdir() + '/wechat_cookies_temp.json'
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    manager = WindowsServerProxyManager()
    
    # 启动代理
    if manager.start_mitmproxy_server():
        manager.enable_system_proxy()
        
        print("代理已启动，请在微信中打开公众号文章...")
        print("按Ctrl+C停止...")
        
        try:
            while True:
                time.sleep(5)
                cookies = manager.get_captured_cookies()
                if cookies:
                    print(f"已捕获 {len(cookies)} 个公众号的Cookie")
        except KeyboardInterrupt:
            pass
        finally:
            manager.cleanup()