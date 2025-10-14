# coding:utf-8
# excel_auto_crawler.py
import pandas as pd
import logging
import time
import os
import json
from src.proxy.read_cookie import ReadCookie
from src.crawler.batch_readnum_spider import BatchReadnumSpider
from src.ui.wechat_browser_automation import WeChatBrowserAutomation, UI_AUTOMATION_AVAILABLE
from config import get_crawler_config

class ExcelAutoCrawler:
    def __init__(self, excel_path="target_articles.xlsx"):
        cfg = get_crawler_config()
        if excel_path == "target_articles.xlsx":
            excel_path = cfg.get('excel_file', excel_path)
        self.excel_path = excel_path
        self.logger = logging.getLogger()
        self.crawler_config = cfg
        self.days_back = self.crawler_config.get('days_back', 90)
        self.max_pages = self.crawler_config.get('max_pages', 200)
        self.articles_per_page = self.crawler_config.get('articles_per_page', 5)
        self.account_delay = self.crawler_config.get('account_delay', 15)
        
        if not UI_AUTOMATION_AVAILABLE:
            raise ImportError("UI自动化库 'uiautomation' 未安装或导入失败。")
            
        self.automation = WeChatBrowserAutomation()
        # 使用旧版ReadCookie，但不删除现有文件（用于验证现有Cookie）
        self.cookie_reader = ReadCookie(outfile="wechat_keys.txt", delete_existing_file=False)
        self.spider = BatchReadnumSpider()

    def _get_target_url_from_excel(self) -> str:
        # ... (此方法与之前版本相同，无需修改)
        self.logger.info(f"正在从 {self.excel_path} 读取目标URL...")
        if not os.path.exists(self.excel_path):
            self.logger.error(f"Excel文件未找到: {self.excel_path}")
            return None
        try:
            df = pd.read_excel(self.excel_path)
            url_column = '文章链接' if '文章链接' in df.columns else 'url'
            if url_column not in df.columns:
                self.logger.error("Excel中未找到 '文章链接' 或 'url' 列。")
                return None
            for url in df[url_column]:
                if pd.notna(url) and 'mp.weixin.qq.com' in str(url):
                    self.logger.info(f"成功读取到目标URL: {url[:50]}...")
                    return str(url)
            self.logger.error("Excel中未找到任何有效的微信文章链接。")
            return None
        except Exception as e:
            self.logger.error(f"读取Excel文件失败: {e}")
            return None

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

    def _get_new_cookie_via_automation(self, target_url=None) -> bool:
        """
        核心流程：启动抓取器，UI自动化打开链接，等待Cookie，停止抓取器。
        :param target_url: 指定的目标URL，如果为None则从Excel读取第一个
        """
        if target_url is None:
            target_url = self._get_target_url_from_excel()

        if not target_url:
            return False

        # 为重新抓取Cookie创建新的ReadCookie实例，删除旧文件
        fresh_cookie_reader = ReadCookie(outfile="wechat_keys.txt", delete_existing_file=True)

        self.logger.info("启动mitmproxy抓取器...")
        if not fresh_cookie_reader.start_cookie_extractor():
            self.logger.error("mitmproxy抓取器启动失败。")
            return False

        self.logger.info("抓取器已在后台启动，现在开始执行微信UI自动化...")

        # 调用UI自动化发送并点击链接，传递fresh_cookie_reader以启用智能刷新停止
        success = self.automation.send_and_open_latest_link(target_url, cookie_reader=fresh_cookie_reader)

        if not success:
            self.logger.error("UI自动化操作失败，未能成功点击链接。")
            fresh_cookie_reader.stop_cookie_extractor()
            return False

        self.logger.info("UI自动化操作成功，等待Cookie被抓取...")

        # 等待mitmproxy抓取到新的cookie
        if fresh_cookie_reader.wait_for_new_cookie(timeout=60):
            self.logger.info("✅ 成功抓取到新的Cookie！")
            fresh_cookie_reader.stop_cookie_extractor()
            return True
        else:
            self.logger.error("❌ Cookie抓取超时或失败。")
            fresh_cookie_reader.stop_cookie_extractor()
            return False

    def open_wechat_and_trigger_url(self) -> bool:
        """
        仅执行UI自动化部分：打开微信，发送并点击链接以触发mitmproxy抓取。
        不包含启动或停止mitmproxy的逻辑。
        """
        target_url = self._get_target_url_from_excel()
        if not target_url:
            return False

        self.logger.info("正在执行微信UI自动化，发送并打开链接...")
        success = self.automation.send_and_open_latest_link(target_url, cookie_reader=self.cookie_reader)
        
        if not success:
            self.logger.error("UI自动化操作失败，未能成功点击链接。")
            return False
            
        self.logger.info("UI自动化操作成功，链接已在微信内置浏览器中打开。")
        return True

    def auto_crawl_from_excel(self):
        """
        【升级版】执行从Excel启动的全自动爬取流程，支持多个公众号。
        此方法会循环处理Excel中的所有公众号链接。
        """
        self.logger.info("="*80)
        self.logger.info("🚀 启动Excel多公众号全自动爬取流程")
        self.logger.info("="*80)

        # 获取所有目标公众号
        all_targets = self._get_all_target_urls_from_excel()
        if not all_targets:
            self.logger.error("❌ 未找到任何有效的公众号链接，无法继续执行。")
            return

        self.logger.info(f"📋 共找到 {len(all_targets)} 个公众号，开始逐个处理...")

        # 用于存储所有公众号的抓取结果
        all_results = []
        successful_count = 0
        failed_count = 0

        for i, target in enumerate(all_targets, 1):
            self.logger.info("="*60)
            self.logger.info(f"📍 处理第 {i}/{len(all_targets)} 个公众号: {target['name']}")
            self.logger.info("="*60)

            try:
                # 步骤1: 为当前公众号获取Cookie
                self.logger.info(f"[步骤 1/2] 为 '{target['name']}' 获取最新Cookie...")
                if not self._get_new_cookie_via_automation(target['url']):
                    self.logger.error(f"❌ 公众号 '{target['name']}' Cookie获取失败，跳过此公众号")
                    failed_count += 1
                    continue

                # 步骤2: 使用新Cookie批量爬取文章
                self.logger.info(f"[步骤 2/2] 使用新Cookie爬取 '{target['name']}' 的文章...")

                # 使用get_latest_cookies获取解析后的数据
                cookie_data = self.cookie_reader.get_latest_cookies()
                if not cookie_data:
                    self.logger.error(f"❌ 公众号 '{target['name']}' Cookie数据解析失败")
                    self.logger.error("💡 可能的原因:")
                    self.logger.error("   1. mitmproxy 没有成功抓取到微信请求")
                    self.logger.error("   2. 微信内置浏览器没有正确打开链接")
                    self.logger.error("   3. Cookie文件格式不正确或为空")
                    self.logger.error("💡 建议:")
                    self.logger.error("   1. 检查微信是否正常打开了文章链接")
                    self.logger.error("   2. 手动在微信中刷新文章页面")
                    self.logger.error("   3. 检查wechat_keys.txt文件是否存在且包含完整数据")
                    failed_count += 1
                    continue

                # 创建新的爬虫实例（避免数据混淆）
                current_spider = BatchReadnumSpider()
                current_spider.biz = cookie_data['biz']
                current_spider.appmsg_token = cookie_data['appmsg_token']
                current_spider.cookie_str = cookie_data['cookie_str']
                current_spider.headers['Cookie'] = cookie_data['cookie_str']

                # 执行爬取
                current_spider.batch_crawl_readnum(
                    max_pages=self.max_pages,
                    articles_per_page=self.articles_per_page,
                    days_back=self.days_back
                )

                if current_spider.articles_data:
                    # 为每篇文章添加公众号信息
                    for article in current_spider.articles_data:
                        article['公众号名称'] = target['name']
                        article['公众号序号'] = i

                    all_results.extend(current_spider.articles_data)

                    # 保存当前公众号的数据
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    excel_file = current_spider.save_to_excel(f"./data/readnum_batch/readnum_{target['name']}_{timestamp}.xlsx")
                    json_file = current_spider.save_to_json(f"./data/readnum_batch/readnum_{target['name']}_{timestamp}.json")

                    self.logger.info(f"✅ 公众号 '{target['name']}' 爬取完成！获取 {len(current_spider.articles_data)} 篇文章")
                    self.logger.info(f"📊 数据已保存到: {excel_file}")
                    successful_count += 1
                else:
                    self.logger.warning(f"⚠️ 公众号 '{target['name']}' 未获取到任何文章数据")
                    failed_count += 1

                # 公众号间延迟，避免频繁请求
                if i < len(all_targets):
                    self.logger.info(f"⏳ 公众号间延迟 {self.account_delay} 秒...")
                    time.sleep(self.account_delay)

            except Exception as e:
                self.logger.error(f"❌ 处理公众号 '{target['name']}' 时发生错误: {e}")
                failed_count += 1
                continue

        # 汇总结果
        self.logger.info("="*80)
        self.logger.info("📊 多公众号爬取汇总结果")
        self.logger.info("="*80)
        self.logger.info(f"✅ 成功处理: {successful_count} 个公众号")
        self.logger.info(f"❌ 失败处理: {failed_count} 个公众号")
        self.logger.info(f"📄 总计文章: {len(all_results)} 篇")

        # 汇总数据保存功能已移除

        self.logger.info("="*80)
        self.logger.info("✅ 多公众号全自动爬取流程执行完毕")
        self.logger.info("="*80)