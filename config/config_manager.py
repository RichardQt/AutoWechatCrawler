# coding:utf-8
# config_manager.py
"""
配置管理模块
用于加载和管理YAML配置文件
"""

import os
import yaml
from typing import Dict, Any, Optional

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为项目根目录下的config/config.yaml
        """
        if config_path is None:
            # 1) 环境变量优先
            env_path = os.environ.get('WECHAT_SPIDER_CONFIG')
            if env_path and os.path.isfile(env_path):
                self.config_path = env_path
            else:
                # 2) 以当前文件所在 config 目录上一级为项目根（正确做法）
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                candidate = os.path.join(project_root, 'config', 'config.yaml')
                if os.path.isfile(candidate):
                    self.config_path = candidate
                else:
                    # 3) 回退到当前工作目录尝试
                    cwd_candidate = os.path.join(os.getcwd(), 'config', 'config.yaml')
                    self.config_path = cwd_candidate if os.path.isfile(cwd_candidate) else candidate
        else:
            self.config_path = config_path
            
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config or {}
        except FileNotFoundError:
            print(f"配置文件未找到: {self.config_path}")
            print("已尝试以下路径顺序：")
            print(f"  1) 环境变量 WECHAT_SPIDER_CONFIG 指定路径")
            print(f"  2) {os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml'))}")
            print(f"  3) {os.path.join(os.getcwd(), 'config', 'config.yaml')}")
            print("可设置环境变量: set WECHAT_SPIDER_CONFIG=绝对路径/config.yaml 来显式指定。")
            return {}
        except yaml.YAMLError as e:
            print(f"配置文件格式错误: {e}")
            return {}
        except Exception as e:
            print(f"加载配置文件时出错: {e}")
            return {}
    
    def get(self, key_path: str, default=None):
        """
        获取配置项的值
        
        Args:
            key_path: 配置项路径，使用点号分隔，如 'database.host'
            default: 默认值
            
        Returns:
            配置项的值或默认值
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_database_config(self) -> Dict[str, Any]:
        """
        获取数据库配置
        
        Returns:
            数据库配置字典
        """
        return {
            'host': self.get('database.host', '127.0.0.1'),
            'port': self.get('database.port', 3306),
            'user': self.get('database.user', 'root'),
            'password': self.get('database.password', ''),
            'database': self.get('database.database', 'faxuan')
        }
    
    def get_table_config(self) -> Dict[str, Any]:
        """
        获取表配置
        Returns:
            表配置字典
        """
        return {
            'table_name': self.get('database.table_name', 'fx_article_records_new'),
            'crawl_channel_default': self.get('database.crawl_channel_default', '微信公众号')
        }
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """
        获取爬虫配置
        
        Returns:
            爬虫配置字典
        """
        return {
            'days_back': self.get('crawler.days_back', 90),
            'max_pages': self.get('crawler.max_pages', 200),
            'articles_per_page': self.get('crawler.articles_per_page', 5),
            'refresh_count': self.get('crawler.refresh_count', 3),
            'refresh_delay': self.get('crawler.refresh_delay', 3.0),
            'min_interval': self.get('crawler.min_interval', 3),
            'max_retries': self.get('crawler.max_retries', 3),
            'timeout': self.get('crawler.timeout', 30),
            'account_delay': self.get('crawler.account_delay', 15),
            'cookie_wait_timeout': self.get('crawler.cookie_wait_timeout', 120),
            'article_delay_range': self.get('crawler.article_delay_range', [10, 15]),
            'page_delay_range': self.get('crawler.page_delay_range', [10, 20]),
            'min_rekey_interval_sec': self.get('crawler.min_rekey_interval_sec', 1500),
            'excel_file': self.get('crawler.excel_file', 'target_articles.xlsx')
        }
    
    def get_article_id_config(self) -> Dict[str, Any]:
        """
        获取文章ID配置
        
        Returns:
            文章ID配置字典
        """
        return {
            'time_format': self.get('article_id.time_format', '%Y%m%d%H%M'),
            'random_digits': self.get('article_id.random_digits', 4)
        }
    
    def get_db_operation_config(self) -> Dict[str, Any]:
        """
        获取数据库操作配置
        
        Returns:
            数据库操作配置字典
        """
        return {
            'auto_reconnect': self.get('db_operation.auto_reconnect', True),
            'connection_timeout': self.get('db_operation.connection_timeout', 30),
            'batch_insert_delay': self.get('db_operation.batch_insert_delay', 0.1),
            'max_retry_times': self.get('db_operation.max_retry_times', 3)
        }
    
    def get_ui_automation_config(self) -> Dict[str, Any]:
        """
        获取UI自动化配置
        
        Returns:
            UI自动化配置字典
        """
        return {
            'search_timeout': self.get('ui_automation.search_timeout', 15),
            'click_retry_count': self.get('ui_automation.click_retry_count', 3),
            'wait_after_click': self.get('ui_automation.wait_after_click', 2),
            'max_recursion_depth': self.get('ui_automation.max_recursion_depth', 5)
        }
    
    def get_proxy_config(self) -> Dict[str, Any]:
        """
        获取代理配置
        
        Returns:
            代理配置字典
        """
        return {
            'mode': self.get('proxy.mode', 'legacy'),
            'legacy': {
                'port': self.get('proxy.legacy.port', 8080),
                'server': self.get('proxy.legacy.server', ''),
                'timeout': self.get('proxy.legacy.timeout', 30),
                'verify_proxy': self.get('proxy.legacy.verify_proxy', True)
            },
            'pool': {
                'qg_url': self.get('proxy.pool.qg_url', 'http://share.proxy.qg.net/get'),
                'qg_key': self.get('proxy.pool.qg_key', ''),
                'ip_lifetime': self.get('proxy.pool.ip_lifetime', 60),
                'refresh_buffer': self.get('proxy.pool.refresh_buffer', 10),
                'max_retries': self.get('proxy.pool.max_retries', 3),
                'retry_delay': self.get('proxy.pool.retry_delay', 5),
                'request_timeout': self.get('proxy.pool.request_timeout', 10),
                'enabled': self.get('proxy.pool.enabled', True)
            }
        }

# 全局配置管理器实例
config_manager = ConfigManager()

# 便捷函数
def get_config(key_path: str, default=None):
    """获取配置项"""
    return config_manager.get(key_path, default)

def get_database_config():
    """获取数据库配置"""
    return config_manager.get_database_config()

def get_table_config():
    """获取表配置"""
    return config_manager.get_table_config()

def get_crawler_config():
    """获取爬虫配置"""
    return config_manager.get_crawler_config()

def get_article_id_config():
    """获取文章ID配置"""
    return config_manager.get_article_id_config()

def get_db_operation_config():
    """获取数据库操作配置"""
    return config_manager.get_db_operation_config()

def get_ui_automation_config():
    """获取UI自动化配置"""
    return config_manager.get_ui_automation_config()

def get_proxy_config():
    """获取代理配置"""
    return config_manager.get_proxy_config()