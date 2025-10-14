# automated_crawler.py
"""
全新的全自动化爬虫控制器 - 支持多公众号
"""
import logging
import time
import os
import json
import pandas as pd

from src.proxy.read_cookie import ReadCookie
from src.crawler.batch_readnum_spider import BatchReadnumSpider
from src.ui.excel_auto_crawler import ExcelAutoCrawler
from src.database.database_manager import DatabaseManager
from src.database.account_status_manager import AccountStatusManager
from src.database.database_config import get_database_config
from src.ui.wechat_browser_automation import WeChatBrowserAutomation, UI_AUTOMATION_AVAILABLE
from config.config_manager import get_crawler_config

class AutomatedCrawler:
    """
    协调整个自动化流程的控制器 - 支持多公众号:
    1. 从Excel读取所有公众号链接
    2. 对每个公众号执行完整的抓取流程:
       - 启动 mitmproxy 抓取器 (会自动设置代理)
       - 运行 UI 自动化打开微信文章以触发抓取
       - 等待并验证 Cookie 是否成功抓取
       - 停止 mitmproxy 抓取器 (会自动关闭代理)
       - 使用获取到的 Cookie 运行批量爬虫
    3. 汇总所有公众号的抓取结果
    """
    def __init__(self, excel_path="target_articles.xlsx", save_to_db=True, db_config=None, crawler_config=None):
        self.logger = logging.getLogger()
        # 若未显式传入 excel_path 则使用配置中的 excel_file
        cfg_excel = (crawler_config or get_crawler_config()).get('excel_file', 'target_articles.xlsx')
        self.excel_path = excel_path if excel_path != "target_articles.xlsx" else cfg_excel
        # 配置
        self.crawler_config = crawler_config or get_crawler_config()
        self.cookie_wait_timeout = self.crawler_config.get('cookie_wait_timeout', 120)
        self.account_delay = self.crawler_config.get('account_delay', 15)
        self.days_back = self.crawler_config.get('days_back', 90)
        self.max_pages = self.crawler_config.get('max_pages', 200)
        self.articles_per_page = self.crawler_config.get('articles_per_page', 5)
        
        # 窗口管理配置
        ui_config = self.crawler_config.get('ui_automation', {})
        self.auto_close_browser_windows = ui_config.get('auto_close_browser_windows', True)
        self.close_windows_between_accounts = ui_config.get('close_windows_between_accounts', True)
        # 数据库
        self.save_to_db = save_to_db
        self.db_config = db_config or get_database_config()
        self.db_manager = None
        self.account_status_manager = None
        if self.save_to_db:
            try:
                self.db_manager = DatabaseManager(**self.db_config)
                self.account_status_manager = AccountStatusManager(self.db_manager)
                count = self.db_manager.get_articles_count()
                self.logger.info(f"✅ 数据库连接成功！当前有 {count} 篇文章")
            except Exception as e:
                self.logger.error(f"❌ 数据库连接失败: {e}")
                self.logger.warning("⚠️ 将只保存到文件，不保存到数据库")
                self.save_to_db = False

    def _get_all_target_urls_from_excel(self) -> list:
        """
        从Excel文件中读取所有有效的公众号链接
        :return: 包含所有有效链接和公众号名称的列表
        """
        self.logger.info(f"正在从 {self.excel_path} 读取所有目标URL...")
        if not os.path.exists(self.excel_path):
            self.logger.error(f"Excel文件未找到: {self.excel_path}")
            return []

        try:
            df = pd.read_excel(self.excel_path)
            url_column = '文章链接' if '文章链接' in df.columns else 'url'
            name_column = '公众号名称' if '公众号名称' in df.columns else 'name'

            if url_column not in df.columns:
                self.logger.error("Excel中未找到 '文章链接' 或 'url' 列。")
                return []

            valid_targets = []
            for index, row in df.iterrows():
                url = row[url_column]
                name = row.get(name_column, f"公众号_{index+1}") if name_column in df.columns else f"公众号_{index+1}"

                if pd.notna(url) and 'mp.weixin.qq.com' in str(url):
                    valid_targets.append({
                        'name': str(name),
                        'url': str(url),
                        'index': index + 1
                    })
                    self.logger.info(f"找到有效目标 {index+1}: {name} - {str(url)[:50]}...")

            self.logger.info(f"共找到 {len(valid_targets)} 个有效的公众号目标")
            return valid_targets

        except Exception as e:
            self.logger.error(f"读取Excel文件失败: {e}")
            return []

    def run(self):
        """执行完整的多公众号自动化流程"""
        self.logger.info("="*80)
        self.logger.info("🚀 多公众号全新自动化流程启动 🚀")
        self.logger.info("="*80)

        # 获取所有目标公众号
        all_targets = self._get_all_target_urls_from_excel()
        if not all_targets:
            self.logger.error("❌ 未找到任何有效的公众号链接，流程中止。")
            return False

        # 初始化所有公众号的状态
        if self.account_status_manager:
            for target in all_targets:
                # 使用URL作为account_id，公众号名称作为account_name
                self.account_status_manager.initialize_account_status(target['url'], target['name'])

        self.logger.info(f"📋 共找到 {len(all_targets)} 个公众号，开始逐个处理...")

        # 用于存储所有公众号的抓取结果
        all_results = []
        successful_count = 0
        failed_count = 0

        try:
            for i, target in enumerate(all_targets, 1):
                self.logger.info("="*60)
                self.logger.info(f"📍 处理第 {i}/{len(all_targets)} 个公众号: {target['name']}")
                self.logger.info("="*60)

                # 在处理新公众号前，关闭之前打开的微信内置浏览器窗口
                # 从第二个公众号开始执行关闭操作
                if i > 1 and self.close_windows_between_accounts:
                    self.logger.info(f"[预处理] 关闭之前打开的微信浏览器窗口以防止窗口累积...")
                    try:
                        # 创建临时的浏览器自动化实例来关闭窗口
                        temp_automation = WeChatBrowserAutomation()
                        temp_automation.close_wechat_browser_windows(keep_main_window=True)
                        self.logger.info("✅ 浏览器窗口清理完成")
                    except Exception as e:
                        self.logger.warning(f"⚠️ 清理浏览器窗口时出现警告: {e}")
                        # 不中断流程，继续处理

                # 更新公众号状态为PROCESSING
                if self.account_status_manager:
                    self.account_status_manager.update_account_status(target['url'], 'PROCESSING')

                # 为每个公众号创建独立的Cookie抓取器
                cookie_reader = None
                auth_info = None  # 统一在外层声明，便于后续步骤使用
                try:
                    # 预检查：尝试复用本地Cookie，若有效则跳过UI抓包
                    try:
                        self.logger.info("[预检查] 尝试复用本地 wechat_keys.txt 中的Cookie...")
                        reuse_reader = ReadCookie(delete_existing_file=False)
                        auth_info = reuse_reader.get_latest_cookies()
                        if auth_info:
                            # 校验biz是否匹配当前目标
                            import re
                            m = re.search(r"__biz=([^&]+)", target['url'])
                            target_biz = m.group(1) if m else None
                            if target_biz and target_biz != auth_info.get('biz'):
                                self.logger.info(f"本地Cookie的biz({auth_info.get('biz')})与目标biz({target_biz})不匹配，放弃复用")
                                auth_info = None
                        if auth_info:
                            # 快速校验Cookie有效性
                            self.logger.info("检测到可用Cookie，先行校验有效性...")
                            try:
                                test_spider = BatchReadnumSpider(
                                    auth_info=auth_info,
                                    save_to_db=self.save_to_db,
                                    db_config=self.db_config,
                                    unit_name=""  # 不预设单位名称，让爬虫自动根据公众号名称映射
                                )
                                if test_spider.validate_cookie():
                                    self.logger.info("✅ 本地Cookie验证通过，将直接使用该Cookie进行爬取（跳过UI抓包）")
                                else:
                                    self.logger.info("本地Cookie验证失败，进入UI自动化抓包流程")
                                    auth_info = None
                            except Exception as ve:
                                self.logger.info(f"本地Cookie验证出现异常，进入UI自动化抓包流程: {ve}")
                                auth_info = None
                    except Exception as pre_e:
                        self.logger.debug(f"预检查复用Cookie时出现问题: {pre_e}")

                    # 步骤1-4: 若未复用Cookie，则创建抓取器并执行UI抓包
                    if not auth_info:
                        self.logger.info(f"[步骤 1/5] 为 '{target['name']}' 创建独立的 Cookie 抓取器...")
                        cookie_reader = ReadCookie()  # 每个公众号独立创建，会删除旧文件
                        if not cookie_reader.start_cookie_extractor():
                            self.logger.error(f"❌ 公众号 '{target['name']}' Cookie 抓取器启动失败，跳过此公众号")
                            failed_count += 1
                            # 更新公众号状态为EXCEPTION并记录到异常补偿表
                            if self.account_status_manager:
                                self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', "Cookie抓取器启动失败")
                                self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' Cookie抓取器启动失败")
                            continue
                        self.logger.info("✅ Cookie 抓取器已在后台运行。")

                        # 步骤2: 运行 UI 自动化触发抓取
                        self.logger.info(f"[步骤 2/5] 为 '{target['name']}' 启动 UI 自动化...")
                        try:
                            ui_crawler = ExcelAutoCrawler()
                            # 直接传递当前公众号的URL，并传递cookie_reader以启用智能刷新停止
                            success = ui_crawler.automation.send_and_open_latest_link(target['url'], cookie_reader=cookie_reader)
                            if not success:
                                self.logger.error(f"❌ 公众号 '{target['name']}' UI 自动化触发失败，跳过此公众号")
                                cookie_reader.stop_cookie_extractor()
                                failed_count += 1
                                # 更新公众号状态为EXCEPTION并记录到异常补偿表
                                if self.account_status_manager:
                                    self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', "UI自动化触发失败")
                                    self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' UI自动化触发失败")
                                continue
                        except Exception as e:
                            self.logger.error(f"❌ 公众号 '{target['name']}' UI 自动化过程中发生错误: {e}")
                            cookie_reader.stop_cookie_extractor()
                            failed_count += 1
                            # 更新公众号状态为EXCEPTION并记录到异常补偿表
                            if self.account_status_manager:
                                self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', f"UI自动化异常: {str(e)}")
                                self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' UI自动化异常: {str(e)}")
                            continue
                        self.logger.info("✅ UI 自动化已成功触发链接打开。")

                        # 步骤3: 等待并验证 Cookie
                        self.logger.info(f"[步骤 3/5] 等待 '{target['name']}' 的 Cookie 数据...")
                        if not cookie_reader.wait_for_new_cookie(timeout=self.cookie_wait_timeout):
                            self.logger.error(f"❌ 公众号 '{target['name']}' 等待 Cookie 超时，跳过此公众号")
                            cookie_reader.stop_cookie_extractor()
                            failed_count += 1
                            # 更新公众号状态为EXCEPTION并记录到异常补偿表
                            if self.account_status_manager:
                                self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', "等待Cookie超时")
                                self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' 等待Cookie超时")
                            continue

                        # 获取并验证cookie是否有效
                        auth_info = cookie_reader.get_latest_cookies()
                        if not auth_info:
                            self.logger.error(f"❌ 公众号 '{target['name']}' Cookie 解析失败")
                            self.logger.error("💡 可能的原因:")
                            self.logger.error("   1. mitmproxy 没有成功抓取到微信请求")
                            self.logger.error("   2. 微信内置浏览器没有正确打开链接")
                            self.logger.error("   3. 网络连接问题或代理设置问题")
                            self.logger.error("💡 建议:")
                            self.logger.error("   1. 检查微信是否正常打开了文章链接")
                            self.logger.error("   2. 手动在微信中刷新文章页面")
                            self.logger.error("   3. 确保网络连接正常")
                            cookie_reader.stop_cookie_extractor()
                            failed_count += 1
                            # 更新公众号状态为EXCEPTION并记录到异常补偿表
                            if self.account_status_manager:
                                self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', "Cookie解析失败")
                                self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' Cookie解析失败")
                            continue
                        self.logger.info("✅ 成功获取并验证了新的 Cookie。")

                        # 步骤4: 停止 mitmproxy 抓取器
                        self.logger.info(f"[步骤 4/5] 停止 '{target['name']}' 的 Cookie 抓取器...")
                        cookie_reader.stop_cookie_extractor()
                        time.sleep(3)  # 等待代理完全关闭
                        self.logger.info("✅ Cookie 抓取器已停止，系统代理已恢复。")

                    # 步骤5: 运行批量爬虫（带Cookie重新抓取机制）
                    self.logger.info(f"[步骤 5/5] 开始爬取 '{target['name']}' 的文章...")

                    max_attempts = 2  # 最多尝试2次（第一次失败后重新抓取Cookie再试一次）
                    batch_spider = None

                    for attempt in range(max_attempts):
                        try:
                            self.logger.info(f"🔄 第 {attempt + 1}/{max_attempts} 次尝试爬取...")
                            batch_spider = BatchReadnumSpider(
                                auth_info=auth_info,
                                save_to_db=self.save_to_db,
                                db_config=self.db_config,
                                unit_name=""  # 不预设单位名称，让爬虫自动根据公众号名称映射
                            )

                            # 先验证Cookie
                            if not batch_spider.validate_cookie():
                                if attempt < max_attempts - 1:
                                    self.logger.warning("⚠️ Cookie验证失败（ret=-3），准备仅刷新文章页面以重新抓包...")

                                    # 重新抓取Cookie（仅启动抓取器，不重复粘贴点击）
                                    self.logger.info("🔄 重新启动Cookie抓取器...")
                                    fresh_cookie_reader = ReadCookie()
                                    if not fresh_cookie_reader.start_cookie_extractor():
                                        self.logger.error("❌ 重新启动Cookie抓取器失败")
                                        break

                                    # 仅刷新当前文章页面
                                    try:
                                        if not UI_AUTOMATION_AVAILABLE:
                                            self.logger.error("❌ UI自动化不可用，无法执行刷新")
                                        else:
                                            self.logger.info("🔁 不重新粘贴链接，直接刷新已打开的文章页面以触发新请求…")
                                            refresher = WeChatBrowserAutomation()
                                            # 刷新次数适当增加，提高触发概率
                                            refresher.auto_refresh_browser(refresh_count=self.crawler_config.get('refresh_count', 3),
                                                                           refresh_delay=self.crawler_config.get('refresh_delay', 3.0),
                                                                           cookie_reader=fresh_cookie_reader)
                                    except Exception as e:
                                        self.logger.warning(f"刷新文章页面时出错: {e}")

                                    # 等待新Cookie
                                    if not fresh_cookie_reader.wait_for_new_cookie(timeout=self.cookie_wait_timeout):
                                        self.logger.error("❌ 重新等待Cookie超时")
                                        fresh_cookie_reader.stop_cookie_extractor()
                                        break

                                    # 获取新的认证信息
                                    auth_info = fresh_cookie_reader.get_latest_cookies()
                                    fresh_cookie_reader.stop_cookie_extractor()
                                    time.sleep(3)

                                    if not auth_info:
                                        self.logger.error("❌ 重新获取Cookie失败")
                                        break

                                    self.logger.info("✅ 成功通过刷新重新获取Cookie，继续尝试...")
                                    continue
                                else:
                                    self.logger.error("❌ 多次尝试后Cookie仍然无效")
                                    # 更新公众号状态为EXCEPTION并记录到异常补偿表
                                    if self.account_status_manager:
                                        self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', f"多次尝试后Cookie仍然无效")
                                        self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' 多次尝试后Cookie仍然无效")
                                    break

                            # Cookie有效，开始正式爬取
                            self.logger.info("✅ Cookie验证成功，开始正式爬取...")
                            
                            batch_spider.batch_crawl_readnum(
                                max_pages=self.max_pages,
                                articles_per_page=self.articles_per_page,
                                days_back=self.days_back
                            )
                            break  # 成功完成，跳出重试循环

                        except Exception as e:
                            self.logger.error(f"❌ 第 {attempt + 1} 次尝试时发生异常: {e}")
                            if attempt < max_attempts - 1:
                                self.logger.info("🔄 准备重试...")
                                time.sleep(5)
                            else:
                                self.logger.error("❌ 所有尝试都失败了")
                                # 更新公众号状态为EXCEPTION并记录到异常补偿表
                                if self.account_status_manager:
                                    self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', f"所有尝试都失败: {str(e)}")
                                    self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' 所有尝试都失败: {str(e)}")

                    if not batch_spider or not batch_spider.articles_data:
                        self.logger.error(f"❌ 公众号 '{target['name']}' 爬取失败")
                        failed_count += 1
                        # 更新公众号状态为EXCEPTION并记录到异常补偿表
                        if self.account_status_manager:
                            self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', f"爬取失败")
                            self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' 爬取失败")
                        continue

                    if batch_spider.articles_data:
                        # 为每篇文章添加公众号信息
                        for article in batch_spider.articles_data:
                            article['公众号名称'] = target['name']
                            article['公众号序号'] = i

                        all_results.extend(batch_spider.articles_data)

                        # 保存当前公众号的数据
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        excel_file = batch_spider.save_to_excel(f"./data/readnum_batch/readnum_{target['name']}_{timestamp}.xlsx")
                        json_file = batch_spider.save_to_json(f"./data/readnum_batch/readnum_{target['name']}_{timestamp}.json")

                        self.logger.info(f"✅ 公众号 '{target['name']}' 爬取完成！获取 {len(batch_spider.articles_data)} 篇文章")
                        self.logger.info(f"📊 数据已保存到: {excel_file}")
                        successful_count += 1

                        # 更新公众号状态为COMPLETED
                        if self.account_status_manager:
                            self.account_status_manager.update_account_status(target['url'], 'COMPLETED')
                    else:
                        self.logger.warning(f"⚠️ 公众号 '{target['name']}' 未获取到任何文章数据")
                        failed_count += 1

                        # 更新公众号状态为EXCEPTION并记录到异常补偿表
                        if self.account_status_manager:
                            self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', '未获取到任何文章数据')
                            self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' 未获取到任何文章数据")

                    # 公众号间延迟，避免频繁请求
                    if i < len(all_targets):
                        self.logger.info(f"⏳ 公众号间延迟 {self.account_delay} 秒...")
                        time.sleep(self.account_delay)
                        
                        # 在延迟期间也关闭浏览器窗口，确保下一个公众号开始时窗口干净
                        if self.auto_close_browser_windows:
                            try:
                                temp_automation = WeChatBrowserAutomation()
                                temp_automation.close_wechat_browser_windows(keep_main_window=True)
                            except Exception as e:
                                self.logger.debug(f"延迟期间清理窗口时出现问题: {e}")

                except Exception as e:
                    self.logger.error(f"❌ 处理公众号 '{target['name']}' 时发生错误: {e}")
                    # 确保停止抓取器
                    if cookie_reader:
                        try:
                            cookie_reader.stop_cookie_extractor()
                        except:
                            pass
                    failed_count += 1

                    # 更新公众号状态为EXCEPTION并记录到异常补偿表
                    if self.account_status_manager:
                        self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', str(e))
                        self.account_status_manager.record_crawl_exception(f"公众号 '{target['name']}' 处理异常: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"❌ 自动化流程发生未知严重错误: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            # 更新所有公众号状态为EXCEPTION并记录到异常补偿表
            if self.account_status_manager:
                for target in all_targets:
                    self.account_status_manager.update_account_status(target['url'], 'EXCEPTION', f"全局异常: {str(e)}")
                # 记录全局异常到异常补偿表
                self.account_status_manager.record_crawl_exception(f"全局异常: {str(e)}")

            return False

        # 汇总结果
        self.logger.info("="*80)
        self.logger.info("📊 多公众号爬取汇总结果")
        self.logger.info("="*80)
        self.logger.info(f"✅ 成功处理: {successful_count} 个公众号")
        self.logger.info(f"❌ 失败处理: {failed_count} 个公众号")
        self.logger.info(f"📄 总计文章: {len(all_results)} 篇")

        # 汇总数据保存功能已移除

        self.logger.info("="*80)
        self.logger.info("✅ 多公众号全新自动化流程执行完毕 ✅")
        self.logger.info("="*80)

        # 如果流程成功完成，清除异常记录
        if self.account_status_manager and successful_count > 0:
            self.account_status_manager.clear_crawl_exception()

        return successful_count > 0  # 只要有一个成功就算成功
