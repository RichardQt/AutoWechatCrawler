#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一代理管理器 - 提供传统代理和代理池的统一接口
根据配置自动选择使用哪种代理模式
"""

import subprocess
import logging
from typing import Optional, Dict, Any
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.config_manager import get_proxy_config

# 导入两种代理管理器
from .proxy_manager import ProxyManager as LegacyProxyManager
from ..core.enhanced_proxy_manager import EnhancedProxyManager


class UnifiedProxyManager:
    """
    统一代理管理器 - 根据配置动态选择代理模式
    """
    
    def __init__(self):
        """
        初始化统一代理管理器
        """
        self.logger = logging.getLogger(__name__)
        
        # 获取代理配置
        self.proxy_config = get_proxy_config()
        self.proxy_mode = self.proxy_config.get('mode', 'legacy')
        
        # 根据模式选择具体的代理管理器
        self.proxy_manager = None
        self._initialize_proxy_manager()
        
        self.logger.info(f"统一代理管理器已初始化，当前模式: {self.proxy_mode}")
    
    def _initialize_proxy_manager(self):
        """根据配置初始化具体的代理管理器"""
        if self.proxy_mode == 'pool':
            # 使用代理池模式
            pool_config = self.proxy_config.get('pool', {})
            if pool_config.get('enabled', True):
                self.logger.info("初始化代理池模式...")
                # 构建配置文件路径
                config_path = os.path.join(project_root, 'config', 'config.yaml')
                self.proxy_manager = EnhancedProxyManager(config_path)
                self.logger.info("✅ 代理池模式初始化成功")
            else:
                self.logger.warning("代理池模式被禁用，回退到传统模式")
                self._initialize_legacy_proxy()
        elif self.proxy_mode == 'legacy':
            # 使用传统模式
            self._initialize_legacy_proxy()
        else:
            self.logger.warning(f"未知的代理模式: {self.proxy_mode}，回退到传统模式")
            self._initialize_legacy_proxy()
    
    def _initialize_legacy_proxy(self):
        """初始化传统代理管理器"""
        self.logger.info("初始化传统代理模式...")
        legacy_config = self.proxy_config.get('legacy', {})
        
        # 创建传统代理管理器
        self.proxy_manager = LegacyProxyManager()
        
        # 设置代理端口（如果配置中指定了）
        port = legacy_config.get('port', 8080)
        self.proxy_manager.proxy_port = port
        
        self.logger.info(f"✅ 传统代理模式初始化成功，端口: {port}")
        self.proxy_mode = 'legacy'  # 更新模式标记
    
    def is_proxy_working(self, timeout: int = 5) -> bool:
        """
        检查代理服务器是否正常工作
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 代理是否正常工作
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        return self.proxy_manager.is_proxy_working(timeout)
    
    def is_system_proxy_enabled(self) -> bool:
        """
        检查系统代理是否启用
        
        Returns:
            bool: 系统代理是否启用
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        return self.proxy_manager.is_system_proxy_enabled()
    
    def get_system_proxy_config(self) -> dict:
        """
        获取当前系统代理配置
        
        Returns:
            dict: 系统代理配置
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return {'enable': False, 'server': ""}
        
        return self.proxy_manager.get_system_proxy_config()
    
    def backup_proxy_settings(self):
        """备份原始代理设置"""
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return
        
        self.proxy_manager.backup_proxy_settings()
    
    def restore_proxy_settings(self):
        """恢复原始代理设置"""
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return
        
        self.proxy_manager.restore_proxy_settings()
    
    def enable_proxy(self, port: int = None) -> bool:
        """
        启用代理
        
        Args:
            port: 代理端口，如果为None则使用配置中的端口
            
        Returns:
            bool: 启用是否成功
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        # 如果没有指定端口，使用配置中的端口
        if port is None:
            if self.proxy_mode == 'legacy':
                port = self.proxy_config.get('legacy', {}).get('port', 8080)
            else:
                port = 8080  # 默认端口
        
        self.logger.info(f"正在启用代理，端口: {port}...")
        return self.proxy_manager.enable_proxy(port)
    
    def disable_proxy(self) -> bool:
        """
        禁用代理并验证
        
        Returns:
            bool: 禁用是否成功
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        self.logger.info("正在禁用代理...")
        return self.proxy_manager.disable_proxy()
    
    def is_port_listening(self, port: int = None) -> bool:
        """
        检查端口是否在监听
        
        Args:
            port: 端口号，如果为None则使用默认端口
            
        Returns:
            bool: 端口是否在监听
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        return self.proxy_manager.is_port_listening(port)
    
    def wait_for_proxy_ready(self, max_wait: int = 30) -> bool:
        """
        等待代理服务启动完成
        
        Args:
            max_wait: 最大等待时间（秒）
            
        Returns:
            bool: 代理是否成功启动
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        return self.proxy_manager.wait_for_proxy_ready(max_wait)
    
    def kill_mitmproxy_processes(self):
        """强制停止所有mitmproxy相关进程"""
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return
        
        self.proxy_manager.kill_mitmproxy_processes()
    
    def validate_and_fix_network(self) -> bool:
        """
        验证网络连接正常
        
        Returns:
            bool: 网络是否正常
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        return self.proxy_manager.validate_and_fix_network()
    
    def reset_network_state(self) -> bool:
        """
        重置网络状态到干净状态
        
        Returns:
            bool: 重置是否成功
        """
        if not self.proxy_manager:
            self.logger.warning("代理管理器未初始化")
            return False
        
        return self.proxy_manager.reset_network_state()
    
    def test_wechat_connectivity(self) -> bool:
        """
        测试微信连接性（仅代理池模式支持）
        
        Returns:
            bool: 微信连接是否正常
        """
        if hasattr(self.proxy_manager, 'test_wechat_connectivity'):
            return self.proxy_manager.test_wechat_connectivity()
        else:
            self.logger.info("传统代理模式不支持微信连接性测试")
            return True  # 传统模式默认返回成功
    
    def get_current_proxy(self) -> Optional[str]:
        """
        获取当前代理（仅代理池模式支持）
        
        Returns:
            str: 当前代理地址，传统模式返回None
        """
        if hasattr(self.proxy_manager, 'get_current_proxy'):
            return self.proxy_manager.get_current_proxy()
        else:
            self.logger.info("传统代理模式不提供代理地址获取")
            return None
    
    def start_enhanced_mitmproxy(self, upstream_proxy: str = None) -> Optional[subprocess.Popen]:
        """
        启动增强版mitmproxy（仅代理池模式支持）
        
        Args:
            upstream_proxy: 上游代理地址
            
        Returns:
            subprocess.Popen: mitmproxy进程对象，传统模式返回None
        """
        if hasattr(self.proxy_manager, 'start_enhanced_mitmproxy'):
            return self.proxy_manager.start_enhanced_mitmproxy()
        else:
            self.logger.info("传统代理模式不支持增强版mitmproxy，使用标准启动方式")
            # 传统模式的标准启动方式
            port = self.proxy_config.get('legacy', {}).get('port', 8080)
            cmd = [
                'mitmdump',
                '-s', 'cookie_extractor.py',
                '--listen-port', str(port),
                '--ssl-insecure',
                '--anticache',
                '--anticomp'
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.logger.info(f"✅ 传统 mitmproxy 已启动 (PID: {process.pid})")
            return process
    
    def get_proxy_mode(self) -> str:
        """
        获取当前代理模式
        
        Returns:
            str: 代理模式 ('legacy' 或 'pool')
        """
        return self.proxy_mode
    
    def get_proxy_info(self) -> Dict[str, Any]:
        """
        获取代理信息摘要
        
        Returns:
            dict: 代理信息摘要
        """
        info = {
            'mode': self.proxy_mode,
            'system_proxy_enabled': self.is_system_proxy_enabled(),
            'proxy_working': self.is_proxy_working()
        }
        
        if self.proxy_mode == 'pool':
            current_proxy = self.get_current_proxy()
            info['current_proxy'] = current_proxy
            if current_proxy:
                info['proxy_enabled'] = True
            else:
                info['proxy_enabled'] = False
        else:
            info['proxy_enabled'] = info['system_proxy_enabled']
        
        return info
    
    def setup_proxy_config(self) -> bool:
        """
        设置代理配置
        
        Returns:
            bool: 设置是否成功
        """
        try:
            if self.proxy_mode == 'pool':
                # 代理池模式 - 设置微信专用代理配置
                if hasattr(self.proxy_manager, 'setup_wechat_proxy_config'):
                    return self.proxy_manager.setup_wechat_proxy_config()
                else:
                    self.logger.warning("代理池模式不支持 setup_wechat_proxy_config 方法")
                    return False
            else:
                # 传统模式 - 启用代理
                port = self.proxy_config.get('legacy', {}).get('port', 8080)
                return self.enable_proxy(port)
        except Exception as e:
            self.logger.error(f"设置代理配置失败: {e}")
            return False
    
    def cleanup_proxy_settings(self):
        """清理代理设置"""
        try:
            if self.proxy_mode == 'pool':
                # 代理池模式 - 清理增强代理设置
                if hasattr(self.proxy_manager, 'cleanup_enhanced_proxy'):
                    self.proxy_manager.cleanup_enhanced_proxy()
            else:
                # 传统模式 - 禁用代理
                self.disable_proxy()
        except Exception as e:
            self.logger.error(f"清理代理设置失败: {e}")
    
    def log_proxy_info(self):
        """记录当前代理信息"""
        info = self.get_proxy_info()
        self.logger.info("=" * 60)
        self.logger.info("📊 当前代理配置信息 =====")
        self.logger.info(f"🔧 代理模式: {info['mode']}")
        self.logger.info(f"✅ 系统代理启用: {info['system_proxy_enabled']}")
        self.logger.info(f"🔧 代理工作状态: {info['proxy_working']}")
        self.logger.info(f"🌐 代理功能启用: {info['proxy_enabled']}")
        
        if info.get('current_proxy'):
            self.logger.info(f"🔗 上游代理: {info['current_proxy']}")
        
        self.logger.info("=" * 60)
    
    def __repr__(self):
        """返回代理管理器的字符串表示"""
        return f"UnifiedProxyManager(mode={self.proxy_mode}, manager={type(self.proxy_manager).__name__})"


def create_unified_proxy_manager() -> UnifiedProxyManager:
    """
    创建统一代理管理器实例
    
    Returns:
        UnifiedProxyManager: 统一代理管理器实例
    """
    return UnifiedProxyManager()