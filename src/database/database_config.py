# coding:utf-8
# database_config.py
"""
数据库配置文件
用于管理数据库连接参数和相关配置
"""

import sys
import os

# Add the project root directory to the path so we can import from config
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(project_root, '..'))

from config.config_manager import get_database_config as get_db_config, get_table_config as get_tbl_config, get_article_id_config as get_art_id_config, get_db_operation_config as get_db_op_config

def get_database_config():
    """获取数据库配置"""
    return get_db_config()

def get_table_config():
    """获取表配置"""
    return get_tbl_config()

def get_article_id_config():
    """获取文章ID配置"""
    return get_art_id_config()

def get_db_operation_config():
    """获取数据库操作配置"""
    return get_db_op_config()

def validate_database_config(config):
    """
    验证数据库配置
    
    Args:
        config: 数据库配置字典
        
    Returns:
        tuple: (is_valid, error_message)
    """
    required_keys = ['host', 'port', 'user', 'password', 'database']
    
    for key in required_keys:
        if key not in config:
            return False, f"缺少必需的配置项: {key}"
        
        if not config[key]:
            return False, f"配置项 {key} 不能为空"
    
    # 验证端口号
    try:
        port = int(config['port'])
        if port <= 0 or port > 65535:
            return False, "端口号必须在1-65535之间"
    except (ValueError, TypeError):
        return False, "端口号必须是有效的数字"
    
    return True, "配置验证通过"
