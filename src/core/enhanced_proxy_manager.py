#!/usr/bin/env python3
"""
增强代理管理器 - 专门解决微信公众号访问的代理问题
包含SSL证书安装、代理绕过设置、微信特定配置等
"""

import subprocess
import time
import winreg
import logging
import requests
import os
import shutil
import threading
import socket
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import yaml

# 兼容性处理
try:
    WindowsError
except NameError:
    WindowsError = OSError

class EnhancedProxyManager:
    """增强代理管理器，专门处理微信公众号访问问题"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.proxy_port = 8080
        self.original_proxy_settings = {}
        self.mitmproxy_cert_path = None

        # 加载配置文件
        self.config = self._load_config(config_path)

        # 代理池相关属性（优先读取 proxy.pool，兼容旧字段 proxy_pool）
        _proxy_root = self.config.get('proxy') or {}
        pool_cfg = (_proxy_root.get('pool') or self.config.get('proxy_pool') or {})

        self.qg_proxy_key = pool_cfg.get('qg_key', '')
        self.qg_proxy_url = pool_cfg.get('qg_url', 'http://share.proxy.qg.net/get')
        self.enabled = pool_cfg.get('enabled', True)
        self.ip_lifetime = pool_cfg.get('ip_lifetime', 60)
        self.refresh_buffer = pool_cfg.get('refresh_buffer', 10)
        self.max_retries = pool_cfg.get('max_retries', 3)
        self.retry_delay = pool_cfg.get('retry_delay', 5)
        self.request_timeout = pool_cfg.get('request_timeout', 10)
        # 额外请求参数（可选）
        self.extra_params = pool_cfg.get('extra_params', {}) if isinstance(pool_cfg.get('extra_params', {}), dict) else {}
        # 连续失败自动回退阈值（单位：轮/次 _get_new_proxy 整体失败）
        self.fallback_after_failures = pool_cfg.get('fallback_after_failures', 3)
        self.consecutive_failures = 0

        # 短效IP管理
        self.upstream_proxy = None  # 当前使用的上游代理
        self.proxy_expiry_time = None  # 当前代理的过期时间
        self.proxy_lock = threading.Lock()  # 线程锁，防止并发获取代理
        self.last_proxy_refresh = None  # 上次代理刷新时间
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.logger.info(f"✅ 配置文件加载成功: {config_path}")
                return config
        except Exception as e:
            self.logger.error(f"❌ 配置文件加载失败: {e}")
            return {}
    
    def _is_proxy_valid(self) -> bool:
        """检查当前代理是否有效（未过期）"""
        if not self.enabled:
            self.logger.info("[代理池] 代理池已禁用")
            return False
        
        if not self.proxy_expiry_time:
            self.logger.info("[代理池] 未设置代理过期时间，认为无效")
            return False
        
        current_time = datetime.now()
        buffer_time = self.proxy_expiry_time - timedelta(seconds=self.refresh_buffer)
        
        if current_time >= buffer_time:
            self.logger.info(f"[代理池] 代理即将过期或已过期")
            self.logger.info(f"[代理池] 当前时间: {current_time}")
            self.logger.info(f"[代理池] 缓冲过期时间: {buffer_time}")
            self.logger.info(f"[代理池] 最终过期时间: {self.proxy_expiry_time}")
            return False
        else:
            self.logger.info(f"[代理池] 当前代理仍然有效")
            self.logger.info(f"[代理池] 代理地址: {self.upstream_proxy}")
            self.logger.info(f"[代理池] 缓冲过期时间: {buffer_time}")
            self.logger.info(f"[代理池] 最终过期时间: {self.proxy_expiry_time}")
            return True
    
    def _refresh_proxy_if_needed(self) -> bool:
        """如果需要则刷新代理IP"""
        if not self.enabled:
            self.logger.info("[代理池] 代理池未启用")
            return False
        
        with self.proxy_lock:
            if self._is_proxy_valid():
                self.logger.debug(f"[代理池] 当前代理仍然有效: {self.upstream_proxy}")
                return True
            
            self.logger.info("=" * 60)
            self.logger.info("[代理池] ===== 开始刷新代理IP =====")
            self.logger.info(f"[代理池] 原代理地址: {self.upstream_proxy}")
            self.logger.info(f"[代理池] 原过期时间: {self.proxy_expiry_time}")
            self.logger.info(f"[代理池] 当前时间: {datetime.now()}")
            self.logger.info("=" * 60)
            return self._get_new_proxy()
    
    def _get_new_proxy(self) -> bool:
        """获取新的代理IP"""
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"[代理池] 正在尝试获取新代理IP (尝试 {attempt + 1}/{self.max_retries})")
                self.logger.info(f"[代理池] 🌐 代理服务商: qg.net")
                self.logger.info(f"[代理池] 🔗 请求地址: {self.qg_proxy_url}")
                
                params = {
                    "key": self.qg_proxy_key,
                    "num": 1,
                    # 青果建议不同账号/会话使用不同IP，默认开启去重
                    "distinct": "true",
                }
                # 允许通过配置注入/覆盖请求参数
                if self.extra_params:
                    try:
                        params.update(self.extra_params)
                    except Exception:
                        pass

                # 打码后打印参数以避免泄露密钥
                masked_params = dict(params)
                if 'key' in masked_params and masked_params['key']:
                    k = str(masked_params['key'])
                    masked_params['key'] = (k[:2] + "****" + k[-2:]) if len(k) >= 4 else "****"
                self.logger.info(f"[代理池] 🔑 请求参数: {masked_params}")
                self.logger.info(f"[代理池] ⏱️  请求超时: {self.request_timeout}秒")
                
                response = requests.get(self.qg_proxy_url, params=params, timeout=self.request_timeout)
                response.raise_for_status()
                result = response.json()
                
                self.logger.debug(f"[代理池] API原始响应结果：{result}")
                
                if result.get("code") == 'SUCCESS' and result.get("data"):
                    data = result.get("data")
                    proxy_item = None
                    # 兼容多种返回结构
                    if isinstance(data, dict) and isinstance(data.get('ips'), list) and data['ips']:
                        proxy_item = data['ips'][0]
                    elif isinstance(data, list) and data:
                        proxy_item = data[0]
                    elif isinstance(data, dict):
                        proxy_item = data

                    server = None
                    exit_ip = None
                    deadline = None
                    if isinstance(proxy_item, dict):
                        server = proxy_item.get('server')
                        exit_ip = proxy_item.get('proxy_ip') or proxy_item.get('ip')
                        deadline = proxy_item.get('deadline')

                    # 优先使用 server (host:port) 作为上游代理地址；exit_ip 用于日志展示
                    if server:
                        old_proxy = self.upstream_proxy  # 记录旧IP用于对比
                        self.upstream_proxy = f"http://{server}"
                        self.proxy_expiry_time = datetime.now() + timedelta(seconds=self.ip_lifetime)
                        self.last_proxy_refresh = datetime.now()
                        
                        # 详细日志输出 - 包含IP和地址信息
                        self.logger.info("=" * 60)
                        self.logger.info("[代理池] 🎉 代理IP获取成功 =====")
                        self.logger.info(f"[代理池] 🌐 代理服务商: qg.net")
                        if exit_ip:
                            self.logger.info(f"[代理池] 📍 出口IP: {exit_ip}")
                        self.logger.info(f"[代理池] 🔗 上游代理服务地址: {server}")
                        if deadline:
                            self.logger.info(f"[代理池] 🕒 服务端截止时间: {deadline}")
                        self.logger.info(f"[代理池] 🔗 完整代理地址: {self.upstream_proxy}")
                        self.logger.info(f"[代理池] ⏰ IP存活时间: {self.ip_lifetime}秒")
                        self.logger.info(f"[代理池] 📅 过期时间: {self.proxy_expiry_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        self.logger.info(f"[代理池] ⚡ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        if old_proxy:
                            # 提取旧IP地址信息
                            if old_proxy.startswith('http://'):
                                old_ip_address = old_proxy[7:]
                            elif old_proxy.startswith('https://'):
                                old_ip_address = old_proxy[8:]
                            else:
                                old_ip_address = old_proxy
                            self.logger.info(f"[代理池] 🔄 上一个代理IP: {old_ip_address}")
                            self.logger.info(f"[代理池] 🔄 上一个代理地址: {old_proxy}")
                        self.logger.info(f"[代理池] 📊 获取时间: {self.last_proxy_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
                        self.logger.info(f"[代理池] 🎯 可用于访问微信公众号文章")
                        self.logger.info("=" * 60)
                        # 成功则清零连续失败计数
                        self.consecutive_failures = 0
                        return True
                    else:
                        self.logger.error(f"[代理池] ❌ 获取代理失败: 返回中缺少 'server' (host:port) 字段")
                        self.logger.error(f"[代理池] 📋 返回数据内容: {result}")
                        self.logger.error(f"[代理池] 🔍 请检查API响应格式")
                else:
                    error_msg = result.get('msg', '未知错误')
                    error_code = result.get('code', 'UNKNOWN')
                    self.logger.error(f"[代理池] ❌ 获取代理IP失败: {error_msg}")
                    self.logger.error(f"[代理池] 🔢 错误代码: {error_code}")
                    self.logger.error(f"[代理池] 🌐 代理服务地址: {self.qg_proxy_url}")
                    self.logger.error(f"[代理池] 🔑 可能原因: API密钥无效或余额不足")
                
                # 如果失败，等待重试延迟
                if attempt < self.max_retries - 1:
                    self.logger.info(f"[代理池] ⏳ 等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"[代理池] ❌ 请求代理IP异常 (尝试 {attempt + 1}/{self.max_retries})")
                self.logger.error(f"[代理池] 🔗 请求地址: {self.qg_proxy_url}")
                self.logger.error(f"[代理池] ❗ 异常信息: {type(e).__name__}: {e}")
                self.logger.error(f"[代理池] 🔍 可能原因: 网络连接问题或代理服务不可用")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"[代理池] ⏳ 等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
            except ValueError as e:
                self.logger.error(f"[代理池] ❌ 解析代理IP响应失败")
                self.logger.error(f"[代理池] ❗ 异常信息: {type(e).__name__}: {e}")
                self.logger.error(f"[代理池] 🔍 可能原因: API响应格式错误，非有效JSON")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"[代理池] ⏳ 等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
        
        self.logger.error(f"[代理池] ❌ 经过 {self.max_retries} 次尝试后仍无法获取代理IP")
        self.logger.error(f"[代理池] 🔗 代理池地址: {self.qg_proxy_url}")
        self.logger.error(f"[代理池] 🔑 代理密钥: {self.qg_proxy_key[:4]}...{self.qg_proxy_key[-4:]}")
        self.logger.error(f"[代理池] 🛑 建议检查: 1.网络连接 2.API密钥 3.账户余额")
        # 记录一轮失败并根据阈值自动回退
        try:
            self.consecutive_failures += 1
        except Exception:
            self.consecutive_failures = 1
        if self.consecutive_failures >= self.fallback_after_failures:
            self.enabled = False
            self.logger.error(f"[代理池] 🔁 连续失败 {self.consecutive_failures} 轮，自动禁用代理池并回退到传统直连模式")
        return False
    
    def get_current_proxy(self) -> Optional[str]:
        """获取当前有效的代理IP，如果无效则尝试刷新"""
        if not self.enabled:
            self.logger.info("[代理池] 代理池未启用，返回None")
            return None
        
        self.logger.info("[代理池] ===== 请求获取当前代理IP =====")
        self.logger.info(f"[代理池] 代理池状态: {'启用' if self.enabled else '禁用'}")
        self.logger.info(f"[代理池] 当前代理: {self.upstream_proxy}")
        self.logger.info(f"[代理池] 过期时间: {self.proxy_expiry_time}")
        self.logger.info(f"[代理池] 代理池服务商: qg.net")
        self.logger.info(f"[代理池] 代理池地址: {self.qg_proxy_url}")
        self.logger.info(f"[代理池] IP存活时间: {self.ip_lifetime}秒")
        
        if not self._refresh_proxy_if_needed():
            self.logger.warning("[代理池] ❌ 无法获取有效代理IP")
            self.logger.warning("[代理池] 请检查代理池配置和网络连接")
            return None
        
        # 提取IP地址信息用于详细日志
        if self.upstream_proxy:
            if self.upstream_proxy.startswith('http://'):
                proxy_ip = self.upstream_proxy[7:]  # 移除 http:// 前缀
            elif self.upstream_proxy.startswith('https://'):
                proxy_ip = self.upstream_proxy[8:]  # 移除 https:// 前缀
            else:
                proxy_ip = self.upstream_proxy
            
            self.logger.info("[代理池] ===== 成功获取代理IP详情 =====")
            self.logger.info(f"[代理池] 🌐 代理服务商: qg.net")
            self.logger.info(f"[代理池] 📍 代理IP地址: {proxy_ip}")
            self.logger.info(f"[代理_pool] 🔗 完整代理地址: {self.upstream_proxy}")
            self.logger.info(f"[代理池] ⏰ IP过期时间: {self.proxy_expiry_time}")
            self.logger.info(f"[代理池] 📊 IP剩余存活: {(self.proxy_expiry_time - datetime.now()).seconds}秒")
            self.logger.info("[代理池] ===== 代理IP信息输出完成 =====")
        else:
            self.logger.warning("[代理池] ⚠️ 获取到的代理IP为空")
        
        return self.upstream_proxy
        
    def setup_wechat_proxy_config(self) -> bool:
        """设置专门针对微信的代理配置"""
        try:
            self.logger.info("🔧 开始设置微信专用代理配置...")
            
            # 1. 安装mitmproxy证书
            if not self.install_mitmproxy_certificate():
                self.logger.warning("⚠️ mitmproxy证书安装失败，可能影响HTTPS访问")
            
            # 2. 设置代理绕过列表
            self.setup_proxy_bypass()
            
            # 3. 配置系统代理
            self.setup_system_proxy_with_bypass()
            
            self.logger.info("✅ 微信专用代理配置完成")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 设置微信代理配置失败: {e}")
            return False
    
    def install_mitmproxy_certificate(self) -> bool:
        """安装mitmproxy的SSL证书到系统信任存储"""
        try:
            # 查找mitmproxy证书文件
            possible_cert_paths = [
                os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.crt"),
                os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem"),
                "./mitmproxy-ca-cert.crt",
                "./mitmproxy-ca-cert.pem"
            ]
            
            cert_path = None
            for path in possible_cert_paths:
                if os.path.exists(path):
                    cert_path = path
                    break
            
            if not cert_path:
                self.logger.warning("未找到mitmproxy证书文件，尝试生成...")
                # 尝试启动mitmproxy生成证书
                self.generate_mitmproxy_certificate()
                
                # 再次查找
                for path in possible_cert_paths:
                    if os.path.exists(path):
                        cert_path = path
                        break
            
            if not cert_path:
                self.logger.error("无法找到或生成mitmproxy证书")
                return False
            
            self.mitmproxy_cert_path = cert_path
            self.logger.info(f"找到mitmproxy证书: {cert_path}")
            
            # 安装证书到Windows证书存储
            return self.install_certificate_to_windows_store(cert_path)
            
        except Exception as e:
            self.logger.error(f"安装mitmproxy证书失败: {e}")
            return False
    
    def generate_mitmproxy_certificate(self):
        """生成mitmproxy证书"""
        try:
            self.logger.info("正在生成mitmproxy证书...")
            # 启动mitmdump一小段时间来生成证书
            process = subprocess.Popen(
                ['mitmdump', '--listen-port', '8081'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 等待2秒让证书生成
            time.sleep(2)
            process.terminate()
            process.wait(timeout=5)
            
            self.logger.info("mitmproxy证书生成完成")
            
        except Exception as e:
            self.logger.warning(f"生成mitmproxy证书时出错: {e}")
    
    def install_certificate_to_windows_store(self, cert_path: str) -> bool:
        """将证书安装到Windows证书存储"""
        try:
            self.logger.info("正在安装证书到Windows证书存储...")
            
            # 使用certlm.msc或certutil命令安装证书
            cmd = [
                'certutil', '-addstore', '-user', 'Root', cert_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.info("✅ 证书已成功安装到系统信任存储")
                return True
            else:
                self.logger.warning(f"证书安装可能失败: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"安装证书到Windows存储失败: {e}")
            return False
    
    def start_enhanced_mitmproxy(self) -> subprocess.Popen:
        """启动增强配置的mitmproxy，支持短效IP自动轮换"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("[代理池] 🚀 启动增强 mitmproxy 代理服务 =====")
            self.logger.info("=" * 60)
            
            # 在启动前获取上游代理
            current_proxy = self.get_current_proxy()

            # 构建mitmproxy启动命令，添加更多兼容性选项
            cmd = [
                'mitmdump',
                '-s', 'cookie_extractor.py',
                '--listen-port', str(self.proxy_port),
                '--ssl-insecure',  # 忽略上游SSL错误
                '--set', 'confdir=~/.mitmproxy',  # 指定配置目录
                '--set', 'ssl_insecure=true',  # 允许不安全的SSL连接
                '--set', 'upstream_cert=false',  # 不验证上游证书
                '--anticache',  # 禁用缓存，确保获取最新内容
                '--anticomp'   # 禁用压缩，便于内容分析
            ]

            # 如果成功获取到上游代理，则添加到命令中
            if current_proxy:
                # 提取IP地址用于显示
                if current_proxy.startswith('http://'):
                    proxy_ip = current_proxy[7:]
                elif current_proxy.startswith('https://'):
                    proxy_ip = current_proxy[8:]
                else:
                    proxy_ip = current_proxy
                
                self.logger.info(f"[代理池] 🔗 将使用上游代理: {current_proxy}")
                self.logger.info(f"[代理池] 📍 上游代理IP: {proxy_ip}")
                cmd.extend(['--mode', f'upstream:{current_proxy}'])
                self.logger.info(f"[代理池] ⚙️ 代理模式参数: --mode upstream:{current_proxy}")
                self.logger.info(f"[代理池] 🌐 所有流量将通过: {proxy_ip}")
            else:
                self.logger.warning("[代理池] ⚠️ 未能获取上游代理，将不使用代理运行")
                self.logger.info("[代理池] 🌍 mitmproxy 将以直连模式运行")

            self.logger.info("[代理池] ===== mitmproxy 启动配置详情 =====")
            self.logger.info(f"[代理池] 🔧 完整启动命令: {' '.join(cmd)}")
            self.logger.info(f"[代理池] 🎯 本地监听端口: {self.proxy_port}")
            self.logger.info(f"[代理_pool] 📝 Cookie提取脚本: cookie_extractor.py")
            self.logger.info(f"[代理池] 🔒 SSL安全配置: insecure模式 (忽略证书错误)")
            self.logger.info(f"[代理池] 🚫 缓存控制: 禁用缓存和压缩")
            self.logger.info(f"[代理池] 📊 流量流向: 本地:{self.proxy_port} -> 上游:{current_proxy if current_proxy else '直连'}")
            self.logger.info("=" * 60)
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.logger.info(f"[代理池] ✅ mitmproxy 进程已启动 (PID: {process.pid})")
            self.logger.info(f"[代理池] 🔄 可用于捕获微信认证Cookie")
            self.logger.info(f"[代理池] 🌐 本地代理地址: http://127.0.0.1:{self.proxy_port}")
            if current_proxy:
                self.logger.info(f"[代理池] 🌐 上游代理地址: {current_proxy}")
            self.logger.info("[代理池] ===== mitmproxy 启动完成 =====")
            self.logger.info("=" * 60)
            
            return process
            
        except Exception as e:
            self.logger.error(f"[代理池] ❌ 启动增强 mitmproxy 失败: {e}")
            self.logger.error(f"[代理池] ❗ 异常类型: {type(e).__name__}")
            self.logger.error(f"[代理池] 🔍 建议检查: 1.mitmproxy是否安装 2.端口是否被占用")
            raise
    
    def setup_proxy_bypass(self):
        """设置代理绕过列表，避免某些域名走代理"""
        try:
            # 设置不走代理的域名列表
            bypass_list = [
                "localhost",
                "127.0.0.1",
                "*.local",
                "10.*",
                "172.16.*",
                "172.17.*",
                "172.18.*",
                "172.19.*",
                "172.20.*",
                "172.21.*",
                "172.22.*",
                "172.23.*",
                "172.24.*",
                "172.25.*",
                "172.26.*",
                "172.27.*",
                "172.28.*",
                "172.29.*",
                "172.30.*",
                "172.31.*",
                "192.168.*",
                # 添加一些可能导致问题的域名
                "*.microsoft.com",
                "*.windows.com",
                "*.msftconnecttest.com"
            ]
            
            bypass_string = ";".join(bypass_list)
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0, winreg.KEY_SET_VALUE
            )
            
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, bypass_string)
            winreg.CloseKey(key)
            
            self.logger.info("✅ 代理绕过列表已设置")
            
        except Exception as e:
            self.logger.error(f"设置代理绕过列表失败: {e}")
    
    def setup_system_proxy_with_bypass(self):
        """设置系统代理，包含绕过配置"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0, winreg.KEY_SET_VALUE
            )
            
            # 设置代理服务器
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{self.proxy_port}")
            
            # 启用代理
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            
            winreg.CloseKey(key)
            
            self.logger.info(f"✅ 系统代理已设置为 127.0.0.1:{self.proxy_port}")
            
        except Exception as e:
            self.logger.error(f"设置系统代理失败: {e}")
    
    def start_enhanced_mitmproxy(self) -> subprocess.Popen:
        """启动增强配置的mitmproxy"""
        try:
            # 在启动前获取上游代理（按配置与代理池状态）
            current_proxy = self.get_current_proxy()

            # 构建mitmproxy启动命令，添加更多兼容性选项
            cmd = [
                'mitmdump',
                '-s', 'cookie_extractor.py',
                '--listen-port', str(self.proxy_port),
                '--ssl-insecure',  # 忽略上游SSL错误
                '--set', 'confdir=~/.mitmproxy',  # 指定配置目录
                '--set', 'ssl_insecure=true',  # 允许不安全的SSL连接
                '--set', 'upstream_cert=false',  # 不验证上游证书
                '--anticache',  # 禁用缓存，确保获取最新内容
                '--anticomp'   # 禁用压缩，便于内容分析
            ]

            # 如果成功获取到上游代理，则添加到命令中
            if current_proxy:
                self.logger.info(f"🔗 将使用上游代理: {current_proxy}")
                cmd.extend(['--mode', f'upstream:{current_proxy}'])
            else:
                self.logger.warning("⚠️ 未能获取上游代理，将不使用代理运行")

            self.logger.info(f"启动增强mitmproxy: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return process
            
        except Exception as e:
            self.logger.error(f"启动增强mitmproxy失败: {e}")
            raise
    
    def test_wechat_connectivity(self) -> bool:
        """测试微信公众号连接性，验证短效IP功能"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("[代理池] 🔍 开始测试微信连接性 =====")
            self.logger.info("[代理池] 🎯 验证代理IP是否可正常访问微信服务")
            self.logger.info("=" * 60)
            
            test_urls = [
                "https://mp.weixin.qq.com",
                "https://mp.weixin.qq.com/mp/profile_ext?action=home"
            ]
            
            # 确保我们有有效的代理
            current_proxy = self.get_current_proxy()
            if current_proxy:
                # 提取IP地址用于显示
                if current_proxy.startswith('http://'):
                    proxy_ip = current_proxy[7:]
                elif current_proxy.startswith('https://'):
                    proxy_ip = current_proxy[8:]
                else:
                    proxy_ip = current_proxy
                
                self.logger.info(f"[代理池] ✅ 使用代理测试连接")
                self.logger.info(f"[代理池] 📍 上游代理IP: {proxy_ip}")
                self.logger.info(f"[代理池] 🔗 完整代理地址: {current_proxy}")
            else:
                self.logger.warning("[代理池] ⚠️ 没有有效代理，将直接连接测试")
                self.logger.info(f"[代理池] 🌍 将以直连模式测试微信访问")
            
            proxies = {
                'http': f'http://127.0.0.1:{self.proxy_port}',
                'https': f'http://127.0.0.1:{self.proxy_port}'
            }
            
            self.logger.info(f"[代理池] 🔄 本地代理地址: http://127.0.0.1:{self.proxy_port}")
            self.logger.info(f"[代理池] 🌐 上游代理状态: {current_proxy if current_proxy else '直连模式'}")
            
            for i, url in enumerate(test_urls, 1):
                try:
                    self.logger.info(f"[代理池] ===== 🔗 测试连接 {i}/{len(test_urls)} =====")
                    self.logger.info(f"[代理池] 📝 测试URL: {url}")
                    self.logger.info(f"[代理池] 🔄 本地代理端口: 127.0.0.1:{self.proxy_port}")
                    self.logger.info(f"[代理池] 🌍 最终目标地址: {current_proxy if current_proxy else '直连访问微信服务器'}")
                    
                    start_time = time.time()
                    response = requests.get(
                        url, 
                        proxies=proxies, 
                        timeout=10,
                        verify=False  # 忽略SSL验证
                    )
                    end_time = time.time()
                    response_time = round((end_time - start_time) * 1000, 2)
                    
                    if response.status_code == 200:
                        self.logger.info(f"[代理池] ✅ {url} 连接成功")
                        self.logger.info(f"[代理池] 📊 响应状态码: {response.status_code}")
                        self.logger.info(f"[代理池] ⏱️ 响应时间: {response_time}ms")
                        if current_proxy:
                            self.logger.info(f"[代理池] 🎉 代理 {proxy_ip} 可以正常访问微信服务")
                        self.logger.info(f"[代理池] ✅ 微信连接性测试通过")
                        self.logger.info("=" * 60)
                        return True
                    else:
                        self.logger.warning(f"[代理池] ⚠️ {url} 连接异常")
                        self.logger.warning(f"[代理池] 📊 响应状态码: {response.status_code}")
                        self.logger.warning(f"[代理池] ⏱️ 响应时间: {response_time}ms")
                        
                except requests.exceptions.Timeout as e:
                    self.logger.warning(f"[代理池] ⏰ {url} 连接超时: {e}")
                    self.logger.warning(f"[代理池] 🔍 可能原因: 代理IP响应太慢或网络不稳定")
                except requests.exceptions.ConnectionError as e:
                    self.logger.warning(f"[代理池] 🔌 {url} 连接错误: {e}")
                    self.logger.warning(f"[代理_pool] 🔍 可能原因: 代理IP失效或网络中断")
                except Exception as e:
                    self.logger.warning(f"[代理池] ❌ {url} 连接失败: {type(e).__name__}: {e}")
            
            self.logger.warning("[代理池] ❌ 所有测试地址连接失败")
            if current_proxy:
                self.logger.warning(f"[代理池] 🔍 代理IP {proxy_ip} 可能无法访问微信服务")
                self.logger.warning(f"[代理池] 💡 建议更换代理IP或检查网络配置")
            self.logger.info("=" * 60)
            return False
            
        except Exception as e:
            self.logger.error(f"[代理池] ❌ 测试微信连接性失败: {type(e).__name__}: {e}")
            return False
    
    def cleanup_enhanced_proxy(self):
        """清理增强代理设置"""
        try:
            self.logger.info("🧹 开始清理增强代理设置...")
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0, winreg.KEY_SET_VALUE
            )
            
            # 禁用代理
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            
            # 清空代理服务器
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "")
            
            # 清空代理绕过列表
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "")
            
            winreg.CloseKey(key)
            
            self.logger.info("✅ 增强代理设置已清理")
            
        except Exception as e:
            self.logger.error(f"清理增强代理设置失败: {e}")

    def is_system_proxy_enabled(self) -> bool:
        """检查系统代理是否启用"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                               0, winreg.KEY_READ)
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            winreg.CloseKey(key)
            return proxy_enable == 1
        except Exception:
            return False

    def get_system_proxy_config(self) -> dict:
        """获取当前系统代理配置"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                               0, winreg.KEY_READ)
            try:
                proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            except WindowsError:
                proxy_enable = 0
            try:
                proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except WindowsError:
                proxy_server = ""
            winreg.CloseKey(key)
            return {
                'enable': proxy_enable == 1,
                'server': proxy_server
            }
        except Exception as e:
            self.logger.error(f"获取代理配置失败: {e}")
            return {'enable': False, 'server': ""}

    def backup_proxy_settings(self):
        """备份原始代理设置"""
        self.original_proxy_settings = self.get_system_proxy_config()
        self.logger.info(f"已备份原始代理设置: {self.original_proxy_settings}")

    def restore_proxy_settings(self):
        """恢复原始代理设置"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                               0, winreg.KEY_SET_VALUE)
            
            if self.original_proxy_settings.get('enable', False):
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, 
                                self.original_proxy_settings.get('server', ''))
            else:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, '')
            
            winreg.CloseKey(key)
            self.logger.info("已恢复原始代理设置")
        except Exception as e:
            self.logger.error(f"恢复代理设置失败: {e}")

    def validate_and_fix_network(self) -> bool:
        """验证网络连接正常"""
        try:
            # 测试不使用代理是否能连接外网，使用多个备选网站
            test_urls = [
                'https://www.baidu.com',
                'http://www.baidu.com',
                'https://www.qq.com'
            ]

            for url in test_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        self.logger.info(f"✅ 网络连接正常（无代理）- 测试网站: {url}")
                        return True
                except Exception as e:
                    self.logger.debug(f"网络测试失败 {url}: {e}")
                    continue

            self.logger.error("❌ 网络连接异常: 所有测试网站均无法访问")
            return False
        except Exception as e:
            self.logger.error(f"❌ 网络连接验证异常: {e}")
            return False

    def reset_network_state(self) -> bool:
        """重置网络状态到干净状态 - 增强版本"""
        self.logger.info("=== 开始重置网络状态 ===")
        
        # 1. 延迟结束代理进程，避免重叠操作
        try:
            self.logger.info("🔍 正在检查并结束现有代理进程...")
            # 先检查是否真的需要结束进程
            process_list = subprocess.run(['tasklist', '/fi', 'imagename eq mitmdump.exe'], 
                                        capture_output=True, text=True, timeout=3)
            if 'mitmdump.exe' in process_list.stdout.lower():
                self.logger.info("检测到运行中的mitmdump进程，执行结束操作...")
                self.kill_mitmproxy_processes()
                time.sleep(1)  # 给系统一点时间清理
            else:
                self.logger.info("未发现运行中的mitmdump进程，跳过进程结束步骤")
                
        except Exception as e:
            self.logger.warning(f"⚠️ 检查代理进程时出错: {e}，继续执行下一步")
            time.sleep(1)  # 给系统一点时间
        
        # 2. 安全关闭代理设置
        operation_success = True
        try:
            self.logger.info("🔧 正在关闭系统代理设置...")
            self.cleanup_enhanced_proxy()
        except Exception as e:
            self.logger.warning(f"⚠️ 关闭代理设置时发生错误: {e}")
            # 这个错误不那么关键，继续执行
        
        # 3. 谨慎验证网络连接（减少重试，降低超时风险）
        self.logger.info("🔗 正在验证网络连接...")
        max_retries = 2  # 减少重试次数
        
        for attempt in range(max_retries):
            try:
                proxy_enabled = self.is_system_proxy_enabled()
                network_ok = self.validate_and_fix_network()
                
                if not proxy_enabled and network_ok:
                    self.logger.info("✅ 网络状态重置验证完成")
                    return True
                
                self.logger.info(f"验证中: 代理状态={proxy_enabled}, 网络状态={network_ok}")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 第{attempt + 1}次网络检查时出错: {e}")
                # 网络检查失败不是程序终止的理由
                time.sleep(1)  # 简短延迟
            
            if attempt < max_retries - 1:
                self.logger.info(f"🔄 简要重试检查 {attempt + 1}/{max_retries}")
            
        self.logger.info("ℹ️ 网络重置流程已完成，代理清理已执行")
        return True  # 即使有网络访问问题，也允许程序继续

    def is_proxy_working(self, timeout: int = 5) -> bool:
        """检查代理服务器是否正常工作"""
        try:
            proxies = {
                'http': f'http://127.0.0.1:{self.proxy_port}',
                'https': f'http://127.0.0.1:{self.proxy_port}'
            }

            # 使用多个备选网站进行测试，提高成功率
            test_urls = [
                'http://www.baidu.com',      # 国内稳定网站
                'http://www.qq.com',         # 备选网站1
                'https://www.baidu.com',     # HTTPS测试
            ]

            for url in test_urls:
                try:
                    response = requests.get(url, proxies=proxies, timeout=timeout)
                    if response.status_code == 200:
                        self.logger.debug(f"代理测试成功: {url}")
                        return True
                except Exception as e:
                    self.logger.debug(f"代理测试失败 {url}: {e}")
                    continue

            return False
        except Exception as e:
            self.logger.debug(f"代理测试异常: {e}")
            return False

    def wait_for_proxy_ready(self, max_wait: int = 30) -> bool:
        """等待代理服务启动完成"""
        start_time = time.time()
        self.logger.info("等待代理服务启动...")

        # 首先等待端口开始监听
        port_ready = False
        while time.time() - start_time < 10:  # 最多等待10秒端口监听
            if self.is_port_listening():
                self.logger.info(f"✅ 端口 {self.proxy_port} 已开始监听")
                port_ready = True
                break
            time.sleep(1)

        if not port_ready:
            self.logger.error(f"❌ 端口 {self.proxy_port} 在10秒内未开始监听")
            return False

        # 然后测试代理功能
        while time.time() - start_time < max_wait:
            if self.is_proxy_working(timeout=3):
                self.logger.info("✅ 代理服务已启动并正常工作")
                return True
            elapsed = int(time.time() - start_time)
            self.logger.debug(f"代理功能测试中... ({elapsed}s/{max_wait}s)")
            time.sleep(2)

        self.logger.error(f"❌ 代理服务启动超时 ({max_wait}秒)")
        return False

    def is_port_listening(self, port: int = None) -> bool:
        """检查端口是否在监听"""
        if port is None:
            port = self.proxy_port
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except Exception:
            return False



