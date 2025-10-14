# coding:utf-8
# database_manager.py
"""
数据库管理模块
用于将微信公众号文章数据实时插入到MySQL数据库中
"""

import pymysql
import logging
import random
import string
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import time

from src.database.database_config import get_table_config

class DatabaseManager:
    """数据库管理器，负责微信公众号文章数据的数据库操作

    2025-08 变更说明：
    按需求暂时停止保存 gzh_name 字段（数据库已删除该列）。
    为最小改动，仅在插入逻辑中移除 gzh_name，相关解析/回填方法保留但不再使用。
    若需恢复，只需恢复 insert SQL 中列及对应 insert_data 组装。"""
    
    def __init__(self, host='127.0.0.1', port=3306, user='root', password='root', database='faxuan', table_name: Optional[str] = None):
        """
        初始化数据库连接
        
        Args:
            host: 数据库主机地址
            port: 数据库端口
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.logger = logging.getLogger(__name__)

        # 读取表配置
        table_cfg = get_table_config()
        self.table_name = table_name or table_cfg.get('table_name', 'fx_article_records')
        self.crawl_channel_default = table_cfg.get('crawl_channel_default', '微信公众号')

        # 初始化数据库连接
        self.connect()
    
    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                autocommit=True,  # 自动提交
                cursorclass=pymysql.cursors.DictCursor
            )
            self.logger.info(f"✅ 数据库连接成功: {self.host}:{self.port}/{self.database}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.logger.info("数据库连接已关闭")
    
    def is_connected(self) -> bool:
        """检查数据库连接状态"""
        try:
            if self.connection:
                self.connection.ping(reconnect=True)
                return True
        except:
            return False
        return False
    
    def reconnect(self) -> bool:
        """重新连接数据库"""
        self.logger.info("尝试重新连接数据库...")
        self.disconnect()
        return self.connect()
    
    def generate_article_id(self, crawl_time: datetime) -> str:
        """
        生成文章ID
        格式：前12位为crawl_time时间(YYYYMMDDHHMM)，后4位为随机数
        
        Args:
            crawl_time: 爬取时间
            
        Returns:
            生成的文章ID
        """
        # 前12位：年月日时分
        time_part = crawl_time.strftime('%Y%m%d%H%M')
        
        # 后4位：随机数
        random_part = ''.join(random.choices(string.digits, k=4))
        
        return time_part + random_part
    
    def insert_article(self, article_data: Dict[str, Any]) -> bool:
        """
        插入单篇文章数据到数据库
        
        Args:
            article_data: 文章数据字典，包含以下字段：
                - title: 文章标题 (必填)
                - content: 文章内容 (可选)
                - url: 文章链接 (可选)
                - pub_time: 发布时间 (可选)
                - crawl_time: 爬取时间 (必填)
                - unit_name: 单位名称（原从 gzh_name 解析，现直接传入）
                - view_count: 阅读量 (可选)
                - like_count: 点赞数 (可选) -> 映射到数据库的 likes 字段
                - share_count: 分享数 (可选) -> 映射到数据库的 comments 字段
                
        Returns:
            插入成功返回True，失败返回False
        """
        if not self.is_connected():
            if not self.reconnect():
                return False

        # 允许外部实现 upsert；此处不再主动去重，调用者可先检查或直接使用 upsert_article
        # article_title = (article_data.get('title') or '').strip()

        try:
            # 准备数据
            current_time = datetime.now()
            crawl_time = article_data.get('crawl_time')
            
            # 如果crawl_time是字符串，转换为datetime对象
            if isinstance(crawl_time, str):
                try:
                    crawl_time = datetime.strptime(crawl_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    crawl_time = current_time
            elif not isinstance(crawl_time, datetime):
                crawl_time = current_time
            
            # 处理发布时间
            publish_time = article_data.get('pub_time')
            if isinstance(publish_time, str):
                try:
                    publish_time = datetime.strptime(publish_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    publish_time = None
            elif not isinstance(publish_time, datetime):
                publish_time = None
            
            # 生成文章ID
            article_id = self.generate_article_id(crawl_time)
            
            # 解析 unit_name：优先用传入 unit_name；否则用 gzh_name 去对照表查；查不到则留空（不再直接用公众号名称顶替）
            unit_name = (article_data.get('unit_name') or '').strip()
            if (not unit_name) and article_data.get('gzh_name'):
                resolved = self.resolve_unit_name(article_data.get('gzh_name'))
                if resolved:
                    unit_name = resolved
                else:
                    self.logger.debug(f"未在对照表中找到公众号 '{article_data.get('gzh_name')}' 对应单位，unit_name 留空以便后续补齐")

            # 计算 analysis 字段的值
            # 当阅读量为0且其余点赞量或者喜欢量有一个不为0时设为-1，其他时候均设为0
            view_count = article_data.get('view_count') or 0
            likes = article_data.get('like_count') or 0
            thumbs_count = article_data.get('old_like_count') or 0
            
            # 转换为数字进行比较
            try:
                view_count = int(view_count) if view_count else 0
                likes = int(likes) if likes else 0
                thumbs_count = int(str(thumbs_count).replace(',', '')) if thumbs_count else 0
            except (ValueError, TypeError):
                view_count = 0
                likes = 0
                thumbs_count = 0
            
            # 判断分析值：当阅读量为0且点赞量或喜欢量有一个不为0时设为-1，否则设为0
            if view_count == 0 and (likes > 0 or thumbs_count > 0):
                analysis_value = -1
            else:
                analysis_value = 0

            # 准备插入数据
            insert_data = {
                'crawl_time': crawl_time,
                'crawl_channel': self.crawl_channel_default,
                # gzh_name 字段已移除
                'unit_name': unit_name,
                'article_title': article_data.get('title', ''),
                'article_content': article_data.get('content', ''),
                'publish_time': publish_time,
                'view_count': article_data.get('view_count'),
                'likes': article_data.get('like_count'),                 # 喜欢量
                'share_count': article_data.get('share_count'),           # 分享量
                'thumbs_count': article_data.get('old_like_count'),       # 点赞量(历史点赞)
                'comments': article_data.get('comment_count'),            # 评论量
                'article_url': article_data.get('url', ''),
                'article_id': article_id,
                'create_time': current_time,
                'update_time': current_time,
                'analysis': analysis_value                                # 分析字段
            }

            # 已移除基于 gzh_name 的对照解析逻辑；若需恢复请调用 resolve_unit_name()
            
            # 构建SQL语句
            sql = f"""
            /* gzh_name 已删除，插入列同步调整 */
            INSERT INTO {self.table_name}
            (crawl_time, crawl_channel, unit_name, article_title, article_content,
             publish_time, view_count, likes, share_count, thumbs_count, comments, article_url, article_id, create_time, update_time, analysis)
            VALUES
            (%(crawl_time)s, %(crawl_channel)s, %(unit_name)s, %(article_title)s, %(article_content)s,
             %(publish_time)s, %(view_count)s, %(likes)s, %(share_count)s, %(thumbs_count)s, %(comments)s, %(article_url)s, %(article_id)s, %(create_time)s, %(update_time)s, %(analysis)s)
            """
            
            # 执行插入
            with self.connection.cursor() as cursor:
                cursor.execute(sql, insert_data)
            
            self.logger.info(f"✅ 文章插入成功: {article_data.get('title', 'Unknown')} (ID: {article_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 文章插入失败: {e}")
            self.logger.error(f"文章数据: {article_data}")
            return False
    
    def batch_insert_articles(self, articles_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        批量插入文章数据

        Args:
            articles_data: 文章数据列表

        Returns:
            包含统计信息的字典: {'success': 成功数量, 'duplicate': 重复数量, 'failed': 失败数量}
        """
        if not articles_data:
            self.logger.warning("没有文章数据需要插入")
            return {'success': 0, 'duplicate': 0, 'failed': 0}

        success_count = 0
        duplicate_count = 0
        failed_count = 0
        total_count = len(articles_data)

        self.logger.info(f"开始批量插入 {total_count} 篇文章...")

        for i, article_data in enumerate(articles_data, 1):
            try:
                article_title = article_data.get('title', 'Unknown')

                # 按标题去重
                if (article_data.get('title', '').strip() and 
                    self.check_article_title_exists(article_data.get('title', '').strip())):
                    duplicate_count += 1
                    self.logger.info(f"进度: {i}/{total_count} - 标题重复，跳过: {article_title}")
                    continue

                if self.insert_article(article_data):
                    success_count += 1
                    self.logger.info(f"进度: {i}/{total_count} - 成功插入文章: {article_title}")
                else:
                    failed_count += 1
                    self.logger.error(f"进度: {i}/{total_count} - 插入失败: {article_title}")

                # 添加小延迟避免数据库压力过大
                time.sleep(0.1)

            except Exception as e:
                failed_count += 1
                self.logger.error(f"批量插入第 {i} 篇文章时出错: {e}")

        result = {'success': success_count, 'duplicate': duplicate_count, 'failed': failed_count}
        self.logger.info(f"批量插入完成: 成功 {success_count} 篇，重复 {duplicate_count} 篇，失败 {failed_count} 篇")
        return result

    def backfill_unit_name_from_contrast(self, contrast_table: str = 'fx_unit_gzh_contrast') -> int:
        """
        使用对照表根据 gzh_name 回填/更新 unit_name。

        仅更新当前表中 unit_name 为空或空串的记录。

        Args:
            contrast_table: 对照表表名，默认 'fx_unit_gzh_contrast'

        Returns:
            受影响的行数（估计值，受 autocommit/驱动实现影响）
        """
        if not self.is_connected():
            if not self.reconnect():
                return 0

        try:
            sql = f"""
            UPDATE {self.table_name} ar
            LEFT JOIN {contrast_table} c ON ar.gzh_name = c.gzh_name
            SET ar.unit_name = COALESCE(c.unit_name, ar.unit_name)
            WHERE (ar.unit_name IS NULL OR ar.unit_name = '') AND c.unit_name IS NOT NULL
            """
            with self.connection.cursor() as cursor:
                affected = cursor.execute(sql)
            self.logger.info(f"✅ 单位名称回填完成，受影响行数: {affected}")
            return affected or 0
        except Exception as e:
            self.logger.error(f"❌ 回填单位名称失败: {e}")
            return 0
    
    def check_article_exists(self, article_url: str) -> bool:
        """
        检查文章是否已存在（根据URL判断）

        Args:
            article_url: 文章URL

        Returns:
            存在返回True，不存在返回False
        """
        if not self.is_connected():
            if not self.reconnect():
                return False

        try:
            sql = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE article_url = %s"
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (article_url,))
                result = cursor.fetchone()
                return result['count'] > 0
        except Exception as e:
            self.logger.error(f"检查文章是否存在时出错: {e}")
            return False

    # ===================== 新增：更新 & Upsert 支持 =====================
    def update_article_stats(self, article_title: str, article_data: Dict[str, Any]) -> bool:
        """根据文章标题更新统计数据 / 内容等字段（若存在）。

        说明：
            - 以 article_title 作为匹配条件（现有表以标题近似唯一，沿用既有逻辑）。
            - 更新字段：view_count, likes, comments（阅读/点赞/评论），以及 article_content（可覆盖）
              article_url（若传入非空）、unit_name（若传入非空）、publish_time（仅当提供且非空时覆盖），update_time
            - 若需改为按 URL 匹配，可新增对应方法。
        """
        if not article_title:
            return False
        if not self.is_connected():
            if not self.reconnect():
                return False
        try:
            current_time = datetime.now()

            # 处理发布时间
            publish_time = article_data.get('pub_time') or article_data.get('publish_time')
            if isinstance(publish_time, str) and publish_time:
                try:
                    publish_time_dt = datetime.strptime(publish_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    publish_time_dt = None
            elif isinstance(publish_time, datetime):
                publish_time_dt = publish_time
            else:
                publish_time_dt = None

            # 计算 analysis 字段的值
            # 当阅读量为0且其余点赞量或者喜欢量有一个不为0时设为-1，其他时候均设为0
            view_count = article_data.get('view_count') or 0
            likes = article_data.get('like_count') or 0
            thumbs_count = article_data.get('old_like_count') or 0
            
            # 转换为数字进行比较
            try:
                view_count = int(view_count) if view_count else 0
                likes = int(likes) if likes else 0
                thumbs_count = int(str(thumbs_count).replace(',', '')) if thumbs_count else 0
            except (ValueError, TypeError):
                view_count = 0
                likes = 0
                thumbs_count = 0
            
            # 判断分析值：当阅读量为0且点赞量或喜欢量有一个不为0时设为-1，否则设为0
            if view_count == 0 and (likes > 0 or thumbs_count > 0):
                analysis_value = -1
            else:
                analysis_value = 0

            sql = f"""
            UPDATE {self.table_name}
            SET
                article_content = %(article_content)s,
                view_count = %(view_count)s,
                likes = %(likes)s,
                share_count = %(share_count)s,
                thumbs_count = %(thumbs_count)s,
                comments = %(comments)s,
                article_url = CASE WHEN %(article_url)s IS NOT NULL AND %(article_url)s <> '' THEN %(article_url)s ELSE article_url END,
                unit_name = CASE WHEN %(unit_name)s IS NOT NULL AND %(unit_name)s <> '' THEN %(unit_name)s ELSE unit_name END,
                publish_time = CASE WHEN %(publish_time)s IS NOT NULL THEN %(publish_time)s ELSE publish_time END,
                update_time = %(update_time)s,
                analysis = %(analysis)s
            WHERE article_title = %(article_title)s
            """

            # 解析 unit_name：更新时若未显式提供 unit_name 且给了 gzh_name，则尝试解析；解析不到则不覆盖原值
            upd_unit_name = (article_data.get('unit_name') or '').strip()
            if (not upd_unit_name) and article_data.get('gzh_name'):
                resolved = self.resolve_unit_name(article_data.get('gzh_name'))
                if resolved:
                    upd_unit_name = resolved
                else:
                    # 置空让 SQL CASE 不覆盖
                    upd_unit_name = ''

            params = {
                'article_content': article_data.get('content', ''),
                'view_count': article_data.get('view_count'),
                'likes': article_data.get('like_count'),
                'share_count': article_data.get('share_count'),
                'thumbs_count': article_data.get('old_like_count'),
                'comments': article_data.get('comment_count'),
                'article_url': article_data.get('url', ''),
                'unit_name': upd_unit_name,
                'publish_time': publish_time_dt,
                'update_time': current_time,
                'article_title': article_title,
                'analysis': analysis_value
            }

            with self.connection.cursor() as cursor:
                affected = cursor.execute(sql, params)
            if affected:
                self.logger.info(f"🔄 已更新文章统计: {article_title}")
                return True
            else:
                self.logger.warning(f"ℹ️ 更新未影响行（可能不存在）: {article_title}")
                return False
        except Exception as e:
            self.logger.error(f"❌ 更新文章统计失败: {e}")
            return False

    def upsert_article(self, article_data: Dict[str, Any]) -> str:
        """插入或更新文章。

        返回值:
            'inserted'  - 新插入
            'updated'   - 已存在并更新
            'failed'    - 失败
        """
        title = (article_data.get('title') or '').strip()
        if not title:
            return 'failed'
        try:
            if self.check_article_title_exists(title):
                ok = self.update_article_stats(title, article_data)
                return 'updated' if ok else 'failed'
            else:
                ok = self.insert_article(article_data)
                return 'inserted' if ok else 'failed'
        except Exception as e:
            self.logger.error(f"❌ upsert 失败: {e}")
            return 'failed'

    def check_article_title_exists(self, article_title: str) -> bool:
        """
        检查文章标题是否已存在（用于去重）

        Args:
            article_title: 文章标题

        Returns:
            存在返回True，不存在返回False
        """
        if not self.is_connected():
            if not self.reconnect():
                return False

        try:
            sql = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE article_title = %s"
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (article_title,))
                result = cursor.fetchone()
                return result['count'] > 0
        except Exception as e:
            self.logger.error(f"检查文章标题是否存在时出错: {e}")
            return False
    
    def get_articles_count(self) -> int:
        """
        获取数据库中文章总数
        
        Returns:
            文章总数
        """
        if not self.is_connected():
            if not self.reconnect():
                return 0
        
        try:
            sql = f"SELECT COUNT(*) as count FROM {self.table_name}"
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchone()
                return result['count']
        except Exception as e:
            self.logger.error(f"获取文章总数时出错: {e}")
            return 0
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()

    def resolve_unit_name(self, gzh_name: str, contrast_table: str = 'fx_unit_gzh_contrast') -> Optional[str]:
        """
        根据 gzh_name 从对照表获取单位名称 unit_name。

        Args:
            gzh_name: 公众号名称
            contrast_table: 对照表表名

        Returns:
            匹配到的单位名称，未匹配返回 None
        """
        if not gzh_name:
            return None
        if not self.is_connected():
            if not self.reconnect():
                return None
        try:
            sql = f"SELECT unit_name FROM {contrast_table} WHERE gzh_name = %s LIMIT 1"
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (gzh_name,))
                row = cursor.fetchone()
                return (row or {}).get('unit_name') if row else None
        except Exception as e:
            self.logger.warning(f"对照表解析单位名称失败: {e}")
            return None
