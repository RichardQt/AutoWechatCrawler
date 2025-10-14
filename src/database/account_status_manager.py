# coding:utf-8
# account_status_manager.py
"""
公众号状态管理模块
用于管理fx_account_status表的操作
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from src.database.database_manager import DatabaseManager
from datetime import datetime


class AccountStatusManager:
    """公众号状态管理器，负责fx_account_status表的数据库操作"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化状态管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def initialize_account_status(self, account_id: str, account_name: str) -> bool:
        """
        初始化公众号状态记录
        
        Args:
            account_id: 公众号标识
            account_name: 公众号名称
            
        Returns:
            初始化成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            # 检查记录是否已存在
            sql_check = "SELECT COUNT(*) as count FROM fx_account_status WHERE account_id = %s"
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql_check, (account_id,))
                result = cursor.fetchone()
                if result['count'] > 0:
                    self.logger.info(f"公众号 {account_name}({account_id}) 状态记录已存在")
                    return True
            
            # 插入新记录
            current_time = datetime.now()
            sql_insert = """
            INSERT INTO fx_account_status 
            (account_id, account_name, status, last_update_time, retry_count, create_time, update_time)
            VALUES
            (%(account_id)s, %(account_name)s, %(status)s, %(last_update_time)s, %(retry_count)s, %(create_time)s, %(update_time)s)
            """
            
            insert_data = {
                'account_id': account_id,
                'account_name': account_name,
                'status': 'PENDING',
                'last_update_time': current_time,
                'retry_count': 0,
                'create_time': current_time,
                'update_time': current_time
            }
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql_insert, insert_data)
            
            self.logger.info(f"✅ 公众号 {account_name}({account_id}) 状态记录初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 公众号 {account_name}({account_id}) 状态记录初始化失败: {e}")
            return False
    
    def update_account_status(self, account_id: str, status: str, exception_msg: Optional[str] = None) -> bool:
        """
        更新公众号状态
        
        Args:
            account_id: 公众号标识
            status: 状态 (PENDING/PROCESSING/COMPLETED/EXCEPTION/RETRYING)
            exception_msg: 异常信息（可选）
            
        Returns:
            更新成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            sql = """
            UPDATE fx_account_status 
            SET status = %(status)s, last_update_time = %(last_update_time)s, update_time = %(update_time)s
            """
            
            params = {
                'status': status,
                'last_update_time': current_time,
                'update_time': current_time,
                'account_id': account_id
            }
            
            # 如果有异常信息，也更新异常信息字段
            if exception_msg is not None:
                sql += ", last_exception_msg = %(exception_msg)s"
                params['exception_msg'] = exception_msg
            
            sql += " WHERE account_id = %(account_id)s"
            
            with self.db_manager.connection.cursor() as cursor:
                affected = cursor.execute(sql, params)
            
            if affected:
                self.logger.info(f"✅ 公众号 {account_id} 状态更新为 {status}")
                return True
            else:
                self.logger.warning(f"⚠️ 公众号 {account_id} 状态更新未影响任何记录")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 公众号 {account_id} 状态更新失败: {e}")
            return False
    
    def increment_retry_count(self, account_id: str) -> bool:
        """
        增加公众号重试次数
        
        Args:
            account_id: 公众号标识
            
        Returns:
            更新成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            sql = """
            UPDATE fx_account_status 
            SET retry_count = retry_count + 1, update_time = %s
            WHERE account_id = %s
            """
            
            with self.db_manager.connection.cursor() as cursor:
                affected = cursor.execute(sql, (current_time, account_id))
            
            if affected:
                self.logger.info(f"✅ 公众号 {account_id} 重试次数增加")
                return True
            else:
                self.logger.warning(f"⚠️ 公众号 {account_id} 重试次数增加未影响任何记录")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 公众号 {account_id} 重试次数增加失败: {e}")
            return False
    
    def set_next_retry_time(self, account_id: str, retry_time: datetime) -> bool:
        """
        设置下次重试时间
        
        Args:
            account_id: 公众号标识
            retry_time: 下次重试时间
            
        Returns:
            设置成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            sql = """
            UPDATE fx_account_status 
            SET next_retry_time = %s, update_time = %s
            WHERE account_id = %s
            """
            
            with self.db_manager.connection.cursor() as cursor:
                affected = cursor.execute(sql, (retry_time, current_time, account_id))
            
            if affected:
                self.logger.info(f"✅ 公众号 {account_id} 下次重试时间设置为 {retry_time}")
                return True
            else:
                self.logger.warning(f"⚠️ 公众号 {account_id} 下次重试时间设置未影响任何记录")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 公众号 {account_id} 下次重试时间设置失败: {e}")
            return False
    
    def reset_account_for_retry(self, account_id: str, exception_msg: Optional[str] = None) -> bool:
        """
        重置公众号状态为重试状态
        
        Args:
            account_id: 公众号标识
            exception_msg: 异常信息（可选）
            
        Returns:
            重置成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            # 增加重试次数并设置状态为RETRYING
            current_time = datetime.now()
            next_retry_time = current_time + timedelta(minutes=5)  # 默认5分钟后重试
            
            sql = """
            UPDATE fx_account_status 
            SET status = 'RETRYING', retry_count = retry_count + 1, 
                last_update_time = %s, next_retry_time = %s, update_time = %s
            """
            
            params = [current_time, next_retry_time, current_time, account_id]
            
            # 如果有异常信息，也更新异常信息字段
            if exception_msg is not None:
                sql += ", last_exception_msg = %s"
                params.insert(3, exception_msg)
            
            sql += " WHERE account_id = %s"
            
            with self.db_manager.connection.cursor() as cursor:
                affected = cursor.execute(sql, params)
            
            if affected:
                self.logger.info(f"✅ 公众号 {account_id} 已重置为重试状态，下次重试时间: {next_retry_time}")
                return True
            else:
                self.logger.warning(f"⚠️ 公众号 {account_id} 重试状态重置未影响任何记录")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 公众号 {account_id} 重试状态重置失败: {e}")
            return False
    
    def get_account_status(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        获取公众号状态
        
        Args:
            account_id: 公众号标识
            
        Returns:
            状态信息字典，失败返回None
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return None

        try:
            sql = "SELECT * FROM fx_account_status WHERE account_id = %s"
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql, (account_id,))
                result = cursor.fetchone()
            
            return dict(result) if result else None
                
        except Exception as e:
            self.logger.error(f"❌ 获取公众号 {account_id} 状态失败: {e}")
            return None
    
    def get_all_accounts_by_status(self, status: str) -> Optional[list]:
        """
        获取指定状态的所有公众号
        
        Args:
            status: 状态
            
        Returns:
            公众号列表，失败返回None
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return None

        try:
            sql = "SELECT * FROM fx_account_status WHERE status = %s"
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql, (status,))
                results = cursor.fetchall()
            
            return [dict(row) for row in results] if results else []
                
        except Exception as e:
            self.logger.error(f"❌ 获取状态为 {status} 的公众号列表失败: {e}")
            return None
    
    def record_crawl_exception(self, exception_msg: str) -> bool:
        """按新语义：不再向 fx_crawl_exception 写入异常，仅记录到补偿/状态表；此处作 no-op。"""
        self.logger.debug("record_crawl_exception 已按新语义禁用，忽略写入 fx_crawl_exception")
        return True

    def resolve_crawl_exception(self, note: str = None) -> bool:
        """记录一次循环完成到 fx_crawl_exception（status='finished'）。"""
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            with self.db_manager.connection.cursor() as cursor:
                # 每循环一次插入新记录
                insert_sql = (
                    "INSERT INTO fx_crawl_exception (finished_date, status, create_time, update_time) "
                    "VALUES (%s, 'finished', %s, %s)"
                )
                cursor.execute(insert_sql, (current_time, current_time, current_time))
            self.logger.info("✅ 已记录循环完成（finished）")
            return True
        except Exception as e:
            self.logger.error(f"❌ 记录循环完成失败: {e}")
            return False

    def mark_crawl_unfinished(self, note: str = None) -> bool:
        """记录一次循环未完成状态到 fx_crawl_exception（status='unfinished'）。
        每循环一次插入新记录，不再按日期去重。
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            with self.db_manager.connection.cursor() as cursor:
                insert_sql = (
                    "INSERT INTO fx_crawl_exception (finished_date, status, create_time, update_time) "
                    "VALUES (%s, 'unfinished', %s, %s)"
                )
                cursor.execute(insert_sql, (current_time, current_time, current_time))
            self.logger.info("✅ 已记录循环未完成状态（unfinished）")
            return True
        except Exception as e:
            self.logger.error(f"❌ 记录循环未完成状态失败: {e}")
            return False

    def get_pending_compensation_accounts(self, limit: int = 0) -> Optional[list]:
        """
        从 fx_compensation_history 中获取待补偿（PENDING）的账号列表。
        返回字段至少包含 account_id, account_name。
        Args:
            limit: 限制返回数量，0 表示不限制
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return None

        try:
            # 使用 GROUP BY 获取每个账户一条汇总记录，并按最早失败日期与最近更新时间排序
            base_sql = (
                "SELECT account_id, account_name, MIN(failed_date) AS first_failed_date, "
                "MAX(update_time) AS last_update "
                "FROM fx_compensation_history "
                "WHERE compensation_status = 'PENDING' "
                "GROUP BY account_id, account_name "
                "ORDER BY first_failed_date ASC, last_update DESC"
            )
            if limit and limit > 0:
                sql = base_sql + " LIMIT %s"
                params = (limit,)
            else:
                sql = base_sql
                params = None

            with self.db_manager.connection.cursor() as cursor:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                results = cursor.fetchall()

            # 仅返回账号标识与名称，其余汇总字段可用于调试
            return [
                {"account_id": row["account_id"], "account_name": row["account_name"]}
                for row in results
            ] if results else []
        except Exception as e:
            self.logger.error(f"❌ 获取待补偿账号失败: {e}")
            return None
    
    def clear_crawl_exception(self) -> bool:
        """按新语义：不再清空完成记录，函数改为 no-op。"""
        self.logger.debug("clear_crawl_exception 已按新语义禁用，不执行删除")
        return True
    
    def get_failed_accounts(self) -> Optional[list]:
        """
        获取需要补偿的失败账户（优化版 - 支持补偿追踪）
        
        Returns:
            失败账户列表，失败返回None
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return None

        try:
            # 优化查询：同时检查当前异常状态和补偿优先级
            sql = """
            SELECT account_id, account_name, status, 
                   COALESCE(last_exception_msg, failed_reason_backup) as last_error,
                   last_update_time, retry_count, compensation_priority,
                   last_failed_date, consecutive_failures
            FROM fx_account_status 
            WHERE (
                status IN ('EXCEPTION', 'FAILED')  -- 当前异常状态
                OR (
                    compensation_priority > 0  -- 需要补偿
                    AND last_failed_date >= CURDATE() - INTERVAL 2 DAY  -- 最近2天失败的
                )
            )
            ORDER BY 
                compensation_priority DESC,  -- 优先级高的优先
                consecutive_failures DESC,   -- 连续失败次数多的优先
                last_update_time DESC        -- 最新失败的优先
            """
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
            
            return [dict(row) for row in results] if results else []
                
        except Exception as e:
            self.logger.error(f"❌ 获取失败账户列表失败: {e}")
            return None
    
    def get_incomplete_accounts(self, days_threshold: int = 7) -> Optional[list]:
        """
        获取数据不完整的账户（最近少数据或爬取异常）
        
        Args:
            days_threshold: 天数阈值，检查最近N天的数据
            
        Returns:
            不完整账户列表，失败返回None
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return None

        try:
            from datetime import timedelta
            
            # 找出最近N天活跃但数据量异常少的账户
            # 这里使用一个简单的逻辑：状态异常或者重试次数过高的账户
            threshold_date = datetime.now() - timedelta(days=days_threshold)
            
            sql = """
            SELECT account_id, account_name, status, retry_count, 
                   last_update_time, 
                   (SELECT COUNT(*) FROM fx_article_records_new_2 
                    WHERE article_id LIKE CONCAT(account_id, '%%') 
                    AND create_time >= %s) as article_count
            FROM fx_account_status 
            WHERE (status IN ('EXCEPTION', 'FAILED', 'RETRYING') 
                   OR retry_count > 3)
              AND last_update_time >= %s
            ORDER BY article_count ASC, last_update_time DESC
            """
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql, (threshold_date, threshold_date))
                results = cursor.fetchall()
            
            return [dict(row) for row in results] if results else []
                
        except Exception as e:
            self.logger.error(f"❌ 获取不完整账户列表失败: {e}")
            return None
    
    def mark_compensation_completed(self, account_id: str) -> bool:
        """
        标记账户补偿完成
        
        Args:
            account_id: 账户ID
            
        Returns:
            标记成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            current_date = current_time.date()
            
            # 更新账户状态表
            update_account_sql = """
            UPDATE fx_account_status 
            SET compensation_priority = 0,
                consecutive_failures = 0,
                last_update_time = %s,
                update_time = %s
            WHERE account_id = %s
            """
            
            # 更新补偿历史表
            update_history_sql = """
            UPDATE fx_compensation_history 
            SET compensation_status = 'COMPLETED',
                compensation_date = %s,
                update_time = %s
            WHERE account_id = %s 
              AND compensation_status = 'PENDING'
              AND failed_date >= CURDATE() - INTERVAL 7 DAY
            """
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(update_account_sql, (current_time, current_time, account_id))
                cursor.execute(update_history_sql, (current_date, current_time, account_id))
            
            self.logger.info(f"✅ 账户 {account_id} 补偿已标记完成")
            return True
                
        except Exception as e:
            self.logger.error(f"❌ 标记账户 {account_id} 补偿完成失败: {e}")
            return False

    def mark_compensation_failed(self, account_id: str, reason: str = None) -> bool:
        """
        将补偿状态标记为 FAILED（最近7天的 pending 记录）。
        如果不存在 PENDING 记录则插入一条当日失败记录。
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            current_date = current_time.date()

            with self.db_manager.connection.cursor() as cursor:
                update_sql = (
                    "UPDATE fx_compensation_history "
                    "SET compensation_status = 'FAILED', update_time = %s, failure_reason = COALESCE(%s, failure_reason) "
                    "WHERE account_id = %s AND compensation_status = 'PENDING' "
                    "AND failed_date >= CURDATE() - INTERVAL 7 DAY"
                )
                affected = cursor.execute(update_sql, (current_time, reason, account_id))

                if affected == 0:
                    # 插入一条失败记录
                    insert_sql = (
                        "INSERT INTO fx_compensation_history (account_id, account_name, failed_date, failure_reason, compensation_status, create_time, update_time) "
                        "SELECT s.account_id, s.account_name, %s, %s, 'FAILED', %s, %s "
                        "FROM fx_account_status s WHERE s.account_id = %s"
                    )
                    cursor.execute(insert_sql, (current_date, reason, current_time, current_time, account_id))

            self.logger.info(f"✅ 账户 {account_id} 已标记补偿失败")
            return True
        except Exception as e:
            self.logger.error(f"❌ 标记账户 {account_id} 补偿失败失败: {e}")
            return False

    
    def update_last_crawl_time(self, account_id: str) -> bool:
        """
        更新账户最后爬取时间
        
        Args:
            account_id: 账户ID
            
        Returns:
            更新成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            sql = """
            UPDATE fx_account_status 
            SET last_update_time = %s, update_time = %s, status = 'ACTIVE'
            WHERE account_id = %s
            """
            
            with self.db_manager.connection.cursor() as cursor:
                affected = cursor.execute(sql, (current_time, current_time, account_id))
            
            if affected:
                self.logger.info(f"✅ 账户 {account_id} 最后爬取时间已更新")
                return True
            else:
                self.logger.warning(f"⚠️ 账户 {account_id} 最后爬取时间更新未影响任何记录")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 更新账户 {account_id} 最后爬取时间失败: {e}")
            return False
    
    def reset_all_accounts_to_pending(self) -> bool:
        """
        优化的账户状态重置（保留补偿追踪信息）
        
        Returns:
            重置成功返回True，失败返回False
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return False

        try:
            current_time = datetime.now()
            current_date = current_time.date()
            
            # 第一步：记录失败账户到补偿历史表
            self._record_failed_accounts_for_compensation(current_date)
            
            # 第二步：智能重置 - 保留补偿追踪信息
            # 分两步执行：先标记补偿信息，再重置状态
            
            # 步骤2a: 先更新补偿追踪信息（基于当前状态）
            update_compensation_sql = """
            UPDATE fx_account_status 
            SET 
                failed_reason_backup = CASE 
                    WHEN status IN ('EXCEPTION', 'FAILED') AND last_exception_msg IS NOT NULL 
                    THEN last_exception_msg 
                    ELSE failed_reason_backup 
                END,
                last_failed_date = CASE 
                    WHEN status IN ('EXCEPTION', 'FAILED') AND (last_failed_date IS NULL OR last_failed_date < %s) THEN %s
                    ELSE last_failed_date 
                END,
                compensation_priority = CASE 
                    WHEN status IN ('EXCEPTION', 'FAILED') THEN 1
                    WHEN status = 'RETRYING' THEN 1
                    ELSE compensation_priority 
                END,
                consecutive_failures = CASE 
                    WHEN status IN ('EXCEPTION', 'FAILED') AND (last_failed_date IS NULL OR last_failed_date < %s) THEN COALESCE(consecutive_failures, 0) + 1
                    WHEN status = 'COMPLETED' THEN 0
                    ELSE consecutive_failures 
                END
            WHERE status IN ('EXCEPTION', 'FAILED', 'RETRYING')
            """
            
            # 步骤2b: 再重置状态并清理临时信息
            reset_status_sql = """
            UPDATE fx_account_status 
            SET 
                status = 'PENDING',
                last_update_time = %s, 
                update_time = %s,
                last_exception_msg = NULL,
                next_retry_time = NULL
            WHERE status != 'PENDING'
            """
            
            with self.db_manager.connection.cursor() as cursor:
                # 执行补偿信息更新
                compensation_affected = cursor.execute(update_compensation_sql, (current_date, current_date, current_date))
                # 执行状态重置
                status_affected = cursor.execute(reset_status_sql, (current_time, current_time))
            
            total_affected = compensation_affected + status_affected
            if total_affected > 0:
                self.logger.info(f"✅ 已智能重置账户状态，保留补偿追踪信息")
                self.logger.info(f"   补偿信息更新: {compensation_affected} 个账户")
                self.logger.info(f"   状态重置: {status_affected} 个账户")
                return True
            else:
                self.logger.info("ℹ️ 所有账户状态已为PENDING，无需重置")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 重置账户状态失败: {e}")
            return False
    
    def _record_failed_accounts_for_compensation(self, current_date) -> bool:
        """
        记录失败账户到补偿历史表
        
        Args:
            current_date: 当前日期
            
        Returns:
            记录成功返回True，失败返回False
        """
        try:
            # 查询当前失败的账户
            select_sql = """
            SELECT account_id, account_name, last_exception_msg, status
            FROM fx_account_status 
            WHERE status IN ('EXCEPTION', 'FAILED')
            """
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(select_sql)
                failed_accounts = cursor.fetchall()
                
                if not failed_accounts:
                    self.logger.info("ℹ️ 没有失败账户需要记录到补偿历史")
                    return True
                
                # 批量插入到补偿历史表
                insert_sql = """
                INSERT INTO fx_compensation_history 
                (account_id, account_name, failed_date, failure_reason, compensation_status)
                VALUES (%s, %s, %s, %s, 'PENDING')
                ON DUPLICATE KEY UPDATE 
                    failure_reason = VALUES(failure_reason),
                    update_time = CURRENT_TIMESTAMP
                """
                
                insert_data = []
                for account in failed_accounts:
                    insert_data.append((
                        account['account_id'],
                        account['account_name'], 
                        current_date,
                        account['last_exception_msg'] or f"状态异常: {account['status']}"
                    ))
                
                cursor.executemany(insert_sql, insert_data)
                self.logger.info(f"✅ 已记录 {len(failed_accounts)} 个失败账户到补偿历史表")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 记录失败账户到补偿历史表失败: {e}")
            return False

    def record_current_failures_to_compensation(self) -> bool:
        """
        将当前 fx_account_status 中状态为 EXCEPTION/FAILED 的账号记录到 fx_compensation_history。
        使用当天日期作为 failed_date；存在则更新 failure_reason 与 update_time。
        """
        return self._record_failed_accounts_for_compensation(datetime.now().date())
    
    def get_accounts_summary(self) -> dict:
        """
        获取账户状态统计摘要
        
        Returns:
            状态统计字典，失败返回空字典
        """
        if not self.db_manager.is_connected():
            if not self.db_manager.reconnect():
                return {}

        try:
            sql = """
            SELECT status, COUNT(*) as count 
            FROM fx_account_status 
            GROUP BY status
            ORDER BY status
            """
            
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
            
            summary = {}
            total = 0
            for row in results:
                status = row['status']
                count = row['count']
                summary[status] = count
                total += count
            
            summary['TOTAL'] = total
            return summary
                
        except Exception as e:
            self.logger.error(f"❌ 获取账户状态统计失败: {e}")
            return {}