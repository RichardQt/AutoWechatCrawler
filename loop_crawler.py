# coding:utf-8
"""
loop_crawler.py

按循环模式运行：
1) 每轮开始重置 fx_account_status（保留补偿追踪字段）
2) 若 fx_compensation_history 有 PENDING，则优先对这些账号执行补偿爬取
3) 否则使用 target_articles.xlsx 全量爬取
4) 任务结束后：
   - 全量成功：清除 fx_crawl_exception 并将其标记 RESOLVED
   - 部分失败：失败账号写入 fx_account_status（EXCEPTION/FAILED）并记录到 fx_compensation_history（PENDING）

支持 Ctrl+C 退出；轮次之间可设置短暂 sleep。
"""
import os
import sys
import time
import logging
from datetime import datetime
import traceback
import argparse

# 路径与环境
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.database.account_status_manager import AccountStatusManager
from src.database.database_manager import DatabaseManager
from src.database.database_config import get_database_config


class LoopCrawler:
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self.logger = self._setup_logger()
        self.is_test_mode = False  # 标记是否为测试模式
        
        # 初始化数据库
        self.logger.info("正在初始化数据库连接...")
        try:
            self.db_manager = DatabaseManager(**get_database_config())
            if not self.db_manager.is_connected():
                if not self.db_manager.reconnect():
                    raise RuntimeError("数据库连接失败")
            self.status = AccountStatusManager(self.db_manager)
            self.logger.info("✅ 数据库连接成功")
        except Exception as e:
            self.logger.error(f"❌ 数据库初始化失败: {e}")
            raise
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志器，仅输出到控制台"""
        logger = logging.getLogger('LoopCrawler')
        logger.setLevel(logging.INFO)
        logger.propagate = False  # 避免重复输出
        
        # 清理旧的同名logger处理器，避免重复与跨次运行累积
        for h in list(logger.handlers):
            logger.removeHandler(h)
        
        # 控制台输出 - 始终启用，确保终端有输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        print(f"[控制台] 日志系统已初始化")
        
        return logger
    
    def _get_python_executable(self) -> str:
        """获取正确的Python可执行文件路径"""
        # 优先使用环境变量中指定的Python路径
        env_python = os.environ.get('WECHAT_SPIDER_PYTHON')
        if env_python and os.path.exists(env_python):
            return env_python
        
        # 尝试使用项目特定的虚拟环境
        possible_paths = [
            r"D:\mynj\mynj_env\Scripts\python.exe",  # 项目虚拟环境
            r"C:\Python39\python.exe",
            r"C:\Python38\python.exe",
            r"C:\Python37\python.exe",
            sys.executable  # 当前Python
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"找到Python: {path}")
                # 测试是否能导入必要的模块
                try:
                    import subprocess
                    result = subprocess.run(
                        [path, "-c", "import pymysql, pandas, yaml"],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return path
                except Exception:
                    continue
        
        # 如果都不行，使用当前的Python
        self.logger.warning(f"未找到合适的Python环境，使用当前: {sys.executable}")
        return sys.executable

    def run_one_round(self, dry_run: bool = False, full_excel_path: str = None):
        """
        执行一轮爬取
        1) 重置fx_account_status状态（保留补偿追踪）
        2) 若fx_compensation_history有PENDING，优先补偿爬取
        3) 全量爬取target_articles.xlsx（或指定的excel）
        4) 成功则写入fx_crawl_exception，失败则记录到fx_compensation_history
        """
        print("="*60)
        print("🔄 开始新一轮爬取循环")
        print("="*60)
        self.logger.info("="*60)
        self.logger.info("🔄 开始新一轮爬取循环")
        self.logger.info("="*60)
        
        # 1) 重置状态（保留补偿追踪）
        try:
            self.logger.info("📝 步骤1: 重置所有账户状态为PENDING...")
            self.status.reset_all_accounts_to_pending()
            self.logger.info("✅ 账户状态重置完成")
        except Exception:
            self.logger.error("❌ 重置账户状态失败", exc_info=True)

        # 2) 读取补偿待处理账号
        try:
            self.logger.info("🔍 步骤2: 检查补偿历史表...")
            pending = self.status.get_pending_compensation_accounts() or []
            if pending:
                self.logger.info(f"📋 发现 {len(pending)} 个待补偿账号")
            else:
                self.logger.info("✅ 无待补偿账号")
        except Exception:
            self.logger.error("❌ 获取待补偿账号失败", exc_info=True)
            pending = []
        
        # 根据文件名判断是否为测试模式
        excel_basename = os.path.basename(full_excel_path or 'target_articles.xlsx')
        self.is_test_mode = 'test' in excel_basename.lower()
        mode_str = "🧪 测试模式" if self.is_test_mode else "🎯 正式模式"
        print(f"📊 本轮参数: {mode_str} excel={excel_basename}, 待补偿数量={len(pending)}")
        self.logger.info(f"📊 本轮参数: dry_run={dry_run}, excel={full_excel_path or 'target_articles.xlsx'}, 待补偿数量={len(pending)}")

        # 构建命令
        project_root = PROJECT_ROOT
        # 使用main.py作为主程序入口，而不是直接调用src/core/main_enhanced.py
        crawler_script = os.path.join(project_root, "main.py")

        # 3) 补偿爬取（如果有待补偿账号）
        if pending:
            self.logger.info("="*40)
            self.logger.info(f"🔧 步骤3: 执行补偿爬取 ({len(pending)} 个账号)")
            self.logger.info("="*40)
            if dry_run:
                # 干跑：直接标记补偿完成
                for r in pending:
                    try:
                        self.status.mark_compensation_completed(r["account_id"])
                        self.logger.info(f"✅ [干跑] 标记补偿完成: {r['account_name']}")
                    except Exception:
                        self.logger.warning(f"⚠️ 标记补偿完成失败: {r}")
            else:
                # 写临时excel并调用实际流程
                import pandas as pd
                temp_dir = os.path.join(project_root, "data", "temp")
                os.makedirs(temp_dir, exist_ok=True)
                temp_excel = os.path.join(temp_dir, f"comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
                # 关键修复：补偿Excel必须包含可用URL。此处使用 account_id 作为URL（设计上即为URL）。
                df = pd.DataFrame([
                    {"公众号名称": r["account_name"], "文章链接": r.get("account_id", ""), "备注": "补偿爬取"}
                    for r in pending
                ])
                df.to_excel(temp_excel, index=False)
                self.logger.info(f"📄 已创建补偿Excel: {temp_excel}")

                # 移除无效参数 --auto（main_enhanced 不支持），仅传 --excel
                # 尝试使用项目指定的Python环境
                python_exe = self._get_python_executable()
                cmd = [python_exe, crawler_script, "--excel", temp_excel]
                self.logger.info(f"使用Python: {python_exe}")
                self._run_cmd(cmd, cwd=project_root, mode="compensation", attempted_accounts=pending)
                try:
                    os.remove(temp_excel)
                    self.logger.debug(f"🗑️ 已删除临时文件: {temp_excel}")
                except Exception:
                    pass
        else:
            self.logger.info("⏭️ 步骤3: 跳过补偿爬取（无待补偿账号）")

        # 4) 全量爬取
        self.logger.info("="*40)
        self.logger.info("📚 步骤4: 执行全量爬取")
        self.logger.info("="*40)
        
        # 确定目标Excel文件
        if full_excel_path and os.path.isabs(full_excel_path):
            target_excel = full_excel_path
        elif full_excel_path:
            target_excel = os.path.join(project_root, full_excel_path)
        else:
            target_excel = os.path.join(project_root, "target_articles.xlsx")
        
        # 检查文件是否存在
        if not os.path.exists(target_excel):
            self.logger.error(f"❌ Excel文件不存在: {target_excel}")
            return

        print(f"📋 目标Excel: {os.path.basename(target_excel)}")
        self.logger.info(f"📋 目标Excel: {os.path.relpath(target_excel, project_root)}")
        
        if dry_run:
            # 干跑：直接记录成功完成
            self.logger.info("[干跑模式] 模拟全量爬取...")
            try:
                self.status.resolve_crawl_exception("dry-run full run success")
                self.logger.info("✅ [干跑] 已记录到fx_crawl_exception")
            except Exception:
                self.logger.error("❌ [干跑] 标记成功失败", exc_info=True)
        else:
            # 移除无效参数 --auto（main_enhanced 不支持），仅传 --excel
            python_exe = self._get_python_executable()
            cmd = [python_exe, crawler_script, "--excel", target_excel]
            self.logger.info(f"使用Python: {python_exe}")
            # 从 full 的 Excel 收集账号ID与名称，供成功性判断
            attempted = []
            try:
                import pandas as pd
                df_full = pd.read_excel(target_excel)
                self.logger.info(f"📊 Excel包含 {len(df_full)} 行数据")
                
                url_col = '文章链接' if '文章链接' in df_full.columns else ('url' if 'url' in df_full.columns else None)
                name_col = '公众号名称' if '公众号名称' in df_full.columns else ('name' if 'name' in df_full.columns else None)
                
                if url_col:
                    for idx, row in df_full.iterrows():
                        url = str(row.get(url_col, '') or '').strip()
                        if url and 'mp.weixin.qq.com' in url:
                            attempted.append({
                                'account_id': url,
                                'account_name': str(row.get(name_col, f'公众号_{idx+1}') or '')
                            })
                    self.logger.info(f"📋 识别到 {len(attempted)} 个有效公众号URL")
                else:
                    self.logger.warning("⚠️ Excel中未找到'文章链接'或'url'列")
            except Exception as e:
                self.logger.warning(f"⚠️ 读取Excel失败: {e}", exc_info=True)
            
            self.logger.info("🚀 开始执行全量爬取...")
            self._run_cmd(cmd, cwd=project_root, mode="full", attempted_accounts=attempted)

    def _run_cmd(self, cmd, cwd, mode: str, attempted_accounts=None):
        """执行爬虫命令并处理结果"""
        import subprocess
        self.logger.info("🖥️ 执行命令: " + " ".join(cmd))
        
        # 记录更多调试信息
        self.logger.debug(f"工作目录: {cwd}")
        self.logger.debug(f"模式: {mode}")
        
        # 检查脚本文件是否存在
        script_path = cmd[1] if len(cmd) > 1 else None
        if script_path and not os.path.exists(script_path):
            self.logger.error(f"❌ 脚本文件不存在: {script_path}")
            return
        
        try:
            # 输出即将执行的完整命令，便于调试
            self.logger.info(f"执行路径: {cmd[0]}")
            self.logger.info(f"脚本文件: {script_path}")
            # 确保子进程以UTF-8输出，避免中文日志乱码
            env = os.environ.copy()
            env.setdefault('PYTHONIOENCODING', 'utf-8')
            env.setdefault('CHCP', '65001')  # 对某些场景有帮助
            
            # 关键改动：不再捕获子进程输出，直接继承父进程控制台，确保 main.py 的日志实时显示
            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                timeout=24*3600,
            )
            
            # 如需额外调试，可在上方实时输出中查看 main.py 的日志
            if result.returncode == 0:
                self.logger.info(f"✅ {mode}模式命令执行成功 (返回码: 0)")
                
                if mode == "full":
                    # 判断全量是否全部成功（基于 attempted_accounts 在 fx_account_status 的状态）
                    all_ok = self._is_full_success(attempted_accounts)
                    if all_ok:
                        print("🎉 全量爬取完全成功！")
                        # 仅在正式模式（target_articles.xlsx）下写入fx_crawl_exception
                        if not self.is_test_mode:
                            self.status.resolve_crawl_exception("full run success")
                            self.logger.info("🎉 全量爬取完全成功！已记录到fx_crawl_exception")
                        else:
                            self.logger.info("🎉 测试模式全量爬取完全成功！（不写入fx_crawl_exception）")
                    else:
                        print("⚠️ 全量爬取部分失败")
                        # 仅在正式模式下记录失败
                        if not self.is_test_mode:
                            # 部分失败：记录失败账号到fx_compensation_history
                            self.status.record_current_failures_to_compensation()
                            # 标记当日未完成，便于外部观测
                            try:
                                self.status.mark_crawl_unfinished("partial failure")
                            except Exception:
                                self.logger.debug("标记unfinished失败，忽略", exc_info=True)
                            self.logger.warning("⚠️ 全量爬取部分失败，失败账号已记录到fx_compensation_history")
                        else:
                            self.logger.warning("⚠️ 测试模式全量爬取部分失败（不记录到补偿历史）")
                else:
                    # 补偿成功：逐个标记完成（仅本次尝试的账号）
                    success_count = 0
                    for r in (attempted_accounts or []):
                        if self.status.mark_compensation_completed(r["account_id"]):
                            success_count += 1
                    self.logger.info(f"✅ 补偿爬取完成，{success_count}/{len(attempted_accounts or [])}个账号标记成功")
            else:
                # 失败时不再尝试收集输出片段，提示用户查看上方实时日志
                self.logger.error(f"❌ {mode}模式命令执行失败 (返回码: {result.returncode}) — 详细日志见上方实时输出")
                if mode == "full":
                    # 全量失败：记录到补偿历史
                    self.status.record_current_failures_to_compensation()
                    try:
                        self.status.mark_crawl_unfinished("subprocess nonzero exit")
                    except Exception:
                        self.logger.debug("标记unfinished失败，忽略", exc_info=True)
                    self.logger.error(f"❌ 全量爬取失败，失败账号已记录到fx_compensation_history")
                else:
                    # 补偿失败：标记失败（仅本次尝试的账号）
                    for r in (attempted_accounts or []):
                        self.status.mark_compensation_failed(r["account_id"], "subprocess failed; see console")
                    self.logger.error("❌ 补偿爬取失败（详见上方实时输出）")
        except subprocess.TimeoutExpired:
            if mode == "full":
                # 超时：仅记录补偿
                self.status.record_current_failures_to_compensation()
                try:
                    self.status.mark_crawl_unfinished("timeout")
                except Exception:
                    self.logger.debug("标记unfinished失败，忽略", exc_info=True)
            else:
                for r in (attempted_accounts or []):
                    self.status.mark_compensation_failed(r["account_id"], "timeout")
            self.logger.error(f"{mode} 执行超时")
        except Exception as e:
            if mode == "full":
                # 异常：仅记录补偿
                self.status.record_current_failures_to_compensation()
                try:
                    self.status.mark_crawl_unfinished("exception")
                except Exception:
                    self.logger.debug("标记unfinished失败，忽略", exc_info=True)
            else:
                for r in (attempted_accounts or []):
                    self.status.mark_compensation_failed(r["account_id"], str(e)[:200])
            self.logger.error(f"{mode} 执行异常: {e}")

    def _is_full_success(self, attempted_accounts) -> bool:
        """
        判断本轮 full 跑是否所有账号都 COMPLETED。
        依赖 fx_account_status 表。attempted_accounts 为 [{account_id, account_name}, ...]
        """
        if not attempted_accounts:
            return False
        try:
            ids = [r.get("account_id") for r in attempted_accounts if r.get("account_id")]
            if not ids:
                return False
            placeholders = ",".join(["%s"] * len(ids))
            sql = f"SELECT account_id, status FROM fx_account_status WHERE account_id IN ({placeholders})"
            with self.db_manager.connection.cursor() as cursor:
                cursor.execute(sql, ids)
                rows = cursor.fetchall() or []
            if not rows:
                return False
            # 所有账号状态均为 COMPLETED 则视为成功
            for row in rows:
                if (row.get("status") or "").upper() != "COMPLETED":
                    return False
            return True
        except Exception:
            self.logger.warning("判断全量成功失败", exc_info=True)
            return False

    def loop(self, full_excel_path: str = None):
        """循环执行爬取"""
        self.logger.info("="*60)
        self.logger.info("🔄 启动循环爬取模式")
        self.logger.info(f"📋 工作流程: 重置状态 -> 补偿爬取 -> 全量爬取")
        self.logger.info(f"⏱️ 循环间隔: {self.interval_seconds}秒")
        self.logger.info(f"📄 目标Excel: {full_excel_path or 'target_articles.xlsx'}")
        self.logger.info("="*60)
        
        round_num = 0
        while True:
            round_num += 1
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"🔄 第 {round_num} 轮爬取开始")
            self.logger.info(f"{'='*60}")
            
            start = time.time()
            try:
                self.run_one_round(full_excel_path=full_excel_path)
            except KeyboardInterrupt:
                self.logger.info("\n⛔ 收到中断信号，退出循环")
                break
            except Exception as e:
                self.logger.error(f"❌ 第 {round_num} 轮执行异常: {e}\n{traceback.format_exc()}")
            
            # 计算间隔时间
            elapsed = time.time() - start
            print(f"⏱️ 第 {round_num} 轮耗时: {elapsed:.1f}秒")
            self.logger.info(f"⏱️ 第 {round_num} 轮耗时: {elapsed:.1f}秒")
            
            # 测试模式不等待，直接退出
            if self.is_test_mode:
                print("🧪 测试模式完成，不进入下一轮")
                break
            
            sleep_time = max(0, self.interval_seconds - int(elapsed))
            if sleep_time > 0:
                print(f"💤 等待 {sleep_time} 秒后开始下一轮...")
                self.logger.info(f"💤 等待 {sleep_time} 秒后开始下一轮...")
                time.sleep(sleep_time)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="微信公众号循环爬取控制器")
    parser.add_argument("--once", action="store_true", help="只运行一轮后退出")
    parser.add_argument("--dry-run", action="store_true", help="干跑模式：跳过调用实际爬虫子进程")
    parser.add_argument("--interval", type=int, default=None, help="循环间隔(秒)，默认60秒")
    parser.add_argument("--excel", type=str, default=None, help="指定Excel文件路径（如test1.xlsx），默认使用target_articles.xlsx")
    parser.add_argument("--no-log-file", action="store_true", help="不保存日志到文件，仅输出到控制台", default=True)  # 默认不记录日志文件
    args = parser.parse_args()

    # 设置根日志器（用于其他模块）
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 默认每轮间隔 60s，可通过参数或环境变量 LOOP_INTERVAL_SECONDS 调整
    if args.interval is not None:
        interval = args.interval
    else:
        try:
            interval = int(os.getenv("LOOP_INTERVAL_SECONDS", "60"))
        except ValueError:
            interval = 60
    
    print("\n" + "="*60)
    print("🤖 微信公众号循环爬取控制器")
    print("="*60)
    print(f"📋 模式: {'单轮' if args.once else '循环'}")
    print(f"📄 Excel: {args.excel or 'target_articles.xlsx'}")
    print(f"⏱️  间隔: {interval}秒")
    print(f"🧵 干跑: {args.dry_run}")
    # 所有日志仅在控制台输出
    print(f"💾 日志: 仅控制台输出")
    print("="*60)
    
    # 检查Excel文件是否存在
    excel_path = args.excel or "target_articles.xlsx"
    if not os.path.isabs(excel_path):
        excel_path = os.path.join(PROJECT_ROOT, excel_path)
    
    if not os.path.exists(excel_path):
        print(f"\n❌ 错误: Excel文件不存在: {excel_path}")
        print("请确保文件存在后再运行")
        sys.exit(1)
    else:
        print(f"✅ Excel文件存在: {os.path.basename(excel_path)}")
    
    print("\n🚀 启动中...\n")
    
    try:
        runner = LoopCrawler(interval_seconds=interval)
        
        if args.once:
            print(f"\n▶️  执行单轮爬取...\n")
            runner.run_one_round(dry_run=args.dry_run, full_excel_path=args.excel)
            # 根据是否为测试模式输出不同提示
            if runner.is_test_mode:
                print(f"\n✅ 测试公众号爬取完成\n")
            else:
                print(f"\n✅ 单轮爬取完成\n")
        else:
            print(f"\n▶️  开始循环爬取（按 Ctrl+C 停止）...\n")
            runner.loop(full_excel_path=args.excel)
    except KeyboardInterrupt:
        print("\n\n⛔ 用户中断，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 程序异常: {e}")
        logging.error("程序异常", exc_info=True)
        sys.exit(1)
