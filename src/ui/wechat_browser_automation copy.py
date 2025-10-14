# coding:utf-8
# wechat_browser_automation.py
"""
微信内置浏览器自动化模块
专门用于在微信PC版中自动打开和刷新微信文章链接

主要功能:
1. 自动发送链接到文件传输助手
2. 自动点击链接打开文章页面
3. 自动检测并处理SSL证书错误页面（"您的连接不是私密连接"）
4. 使用 "thisisunsafe" 自动绕过SSL证书错误
5. 自动刷新页面（支持自定义刷新次数和间隔）

SSL证书错误处理:
- 在打开链接后立即检测SSL证书错误页面
- 支持多种检测方式：窗口标题、页面文本、地址栏
- 自动输入 "thisisunsafe" 绕过证书错误
- 等待页面重新加载后继续后续操作
"""

import time
import pyperclip
import logging

# 配置常量
WECHAT_LINK_PATTERNS = [
    r'https?://mp\.weixin\.qq\.com/s/[^\s]+',
]

BROWSER_WINDOW_CLASSES = [
    'CefWebViewWnd', 'Chrome_WidgetWin_1', 'WeChatWebview',
    'WebView2', 'WebBrowser', 'Internet Explorer_Server'
]

# 配置参数
CONFIG = {
    'search_timeout': 15,
    'click_retry_count': 3,
    'wait_after_click': 2,
    'max_recursion_depth': 5
}

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 尝试导入uiautomation
try:
    import uiautomation as auto
    UI_AUTOMATION_AVAILABLE = True
    auto.SetGlobalSearchTimeout(CONFIG['search_timeout'])
except ImportError:
    UI_AUTOMATION_AVAILABLE = False
    logging.error("uiautomation库未安装，无法执行UI自动化。请运行: pip install uiautomation")

class WeChatBrowserAutomation:
    """微信内置浏览器自动化控制器"""
    
    def __init__(self):
        # 移除这里的raise ImportError，让类始终可以被实例化
        self.wechat_window = None
        self.browser_window = None
        if UI_AUTOMATION_AVAILABLE:
            # 设置全局搜索超时，仅当uiautomation可用时设置
            auto.SetGlobalSearchTimeout(15) 
        else:
            logging.warning("uiautomation库不可用，WeChatBrowserAutomation的功能将受限。")

    def _check_automation_available(self) -> bool:
        """内部方法：检查uiautomation是否可用"""
        if not UI_AUTOMATION_AVAILABLE:
            logging.error("UI自动化功能不可用，请确保uiautomation库已正确安装。")
            return False
        return True

    def find_wechat_window(self) -> auto.WindowControl:
        """
        查找并返回微信PC版主窗口。
        使用更可靠的复合条件进行搜索。
        """
        if not self._check_automation_available():
            return None

        logging.info("正在查找微信主窗口...")
        # 微信窗口的类名通常是 'WeChatMainWndForPC'
        self.wechat_window = auto.WindowControl(ClassName='WeChatMainWndForPC')
        if self.wechat_window.Exists(10): 
            logging.info("成功找到微信窗口 (ClassName='WeChatMainWndForPC')")
            return self.wechat_window
        
        logging.warning("未找到 'WeChatMainWndForPC' 窗口，尝试备用方案...")
        # 备用方案：通过窗口标题"微信"查找
        self.wechat_window = auto.WindowControl(searchDepth=1, Name='微信')
        if self.wechat_window.Exists(5): 
            logging.info("成功找到微信窗口 (Name='微信')")
            return self.wechat_window
            
        logging.error("未找到微信主窗口，请确保微信已登录并显示主界面。")
        return None

    def activate_wechat(self) -> bool:
        """激活微信窗口并置顶"""
        if not self._check_automation_available():
            return False

        if not self.wechat_window or not self.wechat_window.Exists(1):
            if not self.find_wechat_window():
                return False
        
        try:
            logging.info("正在激活微信窗口...")
            self.wechat_window.SetActive()
            self.wechat_window.SetTopmost(True)
            time.sleep(1) 
            self.wechat_window.SetTopmost(False)
            logging.info("微信窗口已激活。")
            return True
        except Exception as e:
            logging.error(f"激活微信窗口失败: {e}")
            return False

    def send_link_to_file_transfer(self, article_url: str) -> bool:
        """
        将文章链接发送到文件传输助手。
        """
        if not self._check_automation_available():
            return False

        logging.info("准备将链接发送到文件传输助手...")
        if not self.activate_wechat():
            return False

        # 1. 尝试通过搜索框查找并进入"文件传输助手"
        try:
            logging.info("尝试通过搜索框查找并进入'文件传输助手'...")
            search_box = self.wechat_window.EditControl(Name='搜索')
            if search_box.Exists(5):
                search_box.Click(simulateMove=True)
                time.sleep(0.5)
                # 清空搜索框并输入文本
                search_box.SendKeys('{Ctrl}a')
                time.sleep(0.2)
                search_box.SendKeys('文件传输助手')
                time.sleep(0.5)
                auto.SendKeys('{Enter}')
                time.sleep(3)
                logging.info("已通过搜索进入'文件传输助手'。")

                # 重要：清空搜索框并点击聊天区域，确保焦点离开搜索框
                logging.info("清空搜索框并将焦点转移到聊天区域...")
                search_box.SendKeys('{Ctrl}a')
                time.sleep(0.2)
                search_box.SendKeys('{Delete}')
                time.sleep(0.5)

                # 点击聊天区域中央，确保焦点离开搜索框
                rect = self.wechat_window.BoundingRectangle
                chat_area_x = rect.left + (rect.right - rect.left) // 2
                chat_area_y = rect.top + (rect.bottom - rect.top) // 2
                auto.Click(chat_area_x, chat_area_y)
                time.sleep(1)
            else:
                logging.warning("未找到搜索框，尝试直接在聊天列表中查找'文件传输助手'。")
                # Fallback: direct click in chat list
                chat_list = self.wechat_window.ListControl(Name='会话')
                file_transfer_item = chat_list.ListItemControl(Name='文件传输助手')
                if file_transfer_item.Exists(5): 
                    logging.info("在聊天列表中找到'文件传输助手'，正在点击...")
                    file_transfer_item.Click(simulateMove=True)
                    time.sleep(1)
                else:
                    logging.error("未能找到'文件传输助手'。请确保微信已登录且'文件传输助手'可见。")
                    return False
        except Exception as e:
            logging.error(f"查找或进入'文件传输助手'失败: {e}")
            return False

        # 2. 将链接粘贴到输入框并发送
        try:
            logging.info("正在查找聊天输入框...")

            # 等待界面稳定
            time.sleep(2)

            # 尝试多种方式查找输入框
            input_box = None

            # 方法1: 查找所有EditControl，排除搜索框
            logging.info("方法1: 查找所有EditControl，排除搜索框...")
            edit_controls = []
            try:
                # 获取所有EditControl
                all_controls = self.wechat_window.GetChildren()
                for control in all_controls:
                    if hasattr(control, 'ControlType') and 'Edit' in str(control.ControlType):
                        # 检查是否是搜索框（通过Name属性）
                        if hasattr(control, 'Name') and control.Name != '搜索':
                            edit_controls.append(control)
                            logging.info(f"找到非搜索框的EditControl: {control.Name}")

                # 选择最后一个（通常是聊天输入框）
                if edit_controls:
                    input_box = edit_controls[-1]
                    logging.info("通过排除搜索框找到聊天输入框")
            except Exception as e:
                logging.warning(f"方法1失败: {e}")

            # 方法2: 如果方法1失败，尝试通过位置查找
            if not input_box:
                logging.info("方法2: 直接点击聊天输入区域...")
                rect = self.wechat_window.BoundingRectangle
                # 点击窗口底部中央位置（聊天输入区域）
                click_x = rect.left + (rect.right - rect.left) // 2
                click_y = rect.bottom - 80  # 距离底部80像素，避开发送按钮

                logging.info(f"点击聊天输入区域坐标: ({click_x}, {click_y})")
                auto.Click(click_x, click_y)
                time.sleep(1)

                # 确保输入框获得焦点后再粘贴
                pyperclip.copy(article_url)
                logging.info(f"已将链接复制到剪贴板: {article_url}")

                # 清空可能存在的内容并粘贴
                auto.SendKeys('{Ctrl}a')
                time.sleep(0.2)
                auto.SendKeys('{Ctrl}v')
                time.sleep(1)

                logging.info("链接已粘贴，正在发送...")

                # 直接查找并点击发送按钮
                try:
                    send_button = self.wechat_window.ButtonControl(Name='发送(S)')
                    if send_button.Exists(2):
                        logging.info("找到发送按钮，点击发送...")
                        send_button.Click(simulateMove=True)
                        logging.info("链接已发送。")
                        time.sleep(3)
                        return True
                    else:
                        logging.error("未找到发送按钮")
                        return False
                except Exception as e:
                    logging.error(f"点击发送按钮失败: {e}")
                    return False

            if input_box and input_box.Exists(2):
                logging.info("找到输入框，准备发送链接...")
                input_box.Click(simulateMove=True)
                time.sleep(0.5)

                # 清空输入框内容
                input_box.SendKeys('{Ctrl}a')
                time.sleep(0.2)

                pyperclip.copy(article_url)
                logging.info(f"已将链接复制到剪贴板: {article_url}")
                input_box.SendKeys('{Ctrl}v')
                time.sleep(1)

                logging.info("链接已粘贴到输入框，正在发送...")

                # 直接查找并点击发送按钮
                try:
                    send_button = self.wechat_window.ButtonControl(Name='发送')
                    if send_button.Exists(2):
                        logging.info("找到发送按钮，点击发送...")
                        send_button.Click(simulateMove=True)
                        logging.info("链接已发送。")
                        time.sleep(3)
                        return True
                    else:
                        logging.error("未找到发送按钮")
                        return False
                except Exception as e:
                    logging.error(f"点击发送按钮失败: {e}")
                    return False

            else:
                logging.error("未能找到聊天输入框。")
                return False

        except Exception as e:
            logging.error(f"发送链接到输入框失败: {e}")
            return False

    def send_and_open_latest_link(self, article_url: str, auto_refresh: bool = True, refresh_count: int = 3, refresh_delay: float = 2.5, cookie_reader=None) -> bool:
        """
        将链接发送到文件传输助手，然后找到并点击最新发送的链接。
        可选：点击后自动按F5刷新页面（默认自动刷新3次）

        参数:
            article_url: 要发送和打开的微信文章链接
            auto_refresh: 是否在打开链接后自动刷新，默认True
            refresh_count: 刷新次数，默认3次（适合抓包需求）
            refresh_delay: 每次刷新后的等待时间（秒），默认2.5秒
            cookie_reader: ReadCookie实例，用于检测抓包状态，如果提供则在抓包成功后停止刷新
        """
        # 步骤 1: 调用现有方法发送链接
        logging.info(f"--- 步骤 1: 正在发送链接到文件传输助手 ---")
        if not self.send_link_to_file_transfer(article_url):
            logging.error("发送链接失败，流程中止。")
            return False
        
        logging.info("--- 步骤 2: 链接已发送，准备查找并点击最新消息 ---")
        time.sleep(2) # 等待UI刷新，确保新消息已加载

        try:
            # 聊天记录区域的控件通常名为 "消息"
            message_list_control = self.wechat_window.ListControl(Name='消息')
            if not message_list_control.Exists(3):
                logging.error("未能找到聊天记录列表控件，无法点击链接。")
                return False

            # 获取所有消息项
            message_items = message_list_control.GetChildren()
            if not message_items:
                logging.error("聊天记录为空，找不到要点击的链接。")
                return False
            
            # 最新的消息在列表的最后一个
            latest_message_item = message_items[-1]
            logging.info("已定位到最新的消息项，准备点击。")

            # 直接点击整个消息项来打开链接
            latest_message_item.Click(simulateMove=True)
            logging.info("✅ 成功点击最新链接。")

            # 等待浏览器打开链接并完全加载页面
            time.sleep(3)

            # 步骤 2.5: 优先检测并处理SSL证书错误页面
            logging.info("--- 步骤 2.5: 检测并处理SSL证书错误页面 ---")
            if self.handle_ssl_certificate_error():
                logging.info("✅ 检测到SSL证书错误页面，已使用 'thisisunsafe' 自动绕过")
                # 等待页面重新加载完成
                time.sleep(3)
            else:
                logging.info("未检测到SSL证书错误页面，继续正常流程")

            # 步骤 3: 如果启用，执行自动刷新
            if auto_refresh and refresh_count > 0:
                logging.info("--- 步骤 3: 开始执行自动刷新 ---")
                if cookie_reader:
                    logging.info("🔍 启用了抓包检测，将在成功抓包后自动停止刷新")

                for i in range(refresh_count):
                    refresh_num = i + 1
                    logging.info(f"正在执行第 {refresh_num} 次刷新操作...")

                    # 如果提供了cookie_reader，在每次刷新前检查是否已经抓包成功
                    if cookie_reader and self._check_cookie_captured(cookie_reader):
                        logging.info(f"🎉 检测到抓包成功！在第 {refresh_num} 次刷新前停止刷新操作")
                        logging.info("✅ 自动刷新提前结束，开始进行阅读量爬取")
                        break

                    try:
                        # 每次刷新前都尝试找到并激活浏览器窗口
                        if self.find_and_activate_browser_window():
                            # 给窗口一点时间完全获得焦点
                            time.sleep(0.5)

                            # 检查并处理SSL证书错误页面
                            if self.handle_ssl_certificate_error():
                                logging.info("检测到SSL证书错误页面，已自动处理")
                                # 等待页面重新加载
                                time.sleep(3)

                            # 模拟F5按键进行刷新
                            auto.SendKey(auto.Keys.VK_F5)
                            logging.info("已发送F5刷新指令到浏览器窗口")
                        else:
                            # 如果找不到浏览器窗口，尝试使用通用方法
                            logging.warning("未找到专用浏览器窗口，使用通用刷新方法")
                            auto.SendKey(auto.Keys.VK_F5)

                        # 等待页面刷新完成
                        logging.info(f"等待页面刷新完成... ({refresh_delay}秒)")
                        time.sleep(refresh_delay)

                        # 刷新完成后再次检查抓包状态
                        if cookie_reader and self._check_cookie_captured(cookie_reader):
                            logging.info(f"🎉 检测到抓包成功！在第 {refresh_num} 次刷新后停止")
                            logging.info("✅ 自动刷新提前结束，开始进行阅读量爬取")
                            break

                        logging.info(f"第 {refresh_num} 次刷新完成")

                        # 如果不是最后一次，等待更长时间让页面稳定
                        if i < refresh_count - 1:
                            # 每次刷新间稍长等待，确保浏览器窗口可见
                            time.sleep(1.5)

                    except Exception as refresh_error:
                        logging.warning(f"第 {refresh_num} 次刷新失败: {refresh_error}")
                        continue

                if not cookie_reader or not self._check_cookie_captured(cookie_reader):
                    logging.info("✅ 自动刷新操作全部完成")
                else:
                    logging.info("✅ 自动刷新因抓包成功而提前结束")

            return True

        except Exception as e:
            logging.error(f"点击最新链接时发生错误: {e}")
            return False

    def get_messages_from_file_transfer(self) -> list:
        """
        获取 "文件传输助手" 聊天窗口中的消息列表。
        """
        if not self._check_automation_available():
            return []

        logging.info("准备从 '文件传输助手' 获取消息列表...")
        if not self.activate_wechat():
            return []

        # 1. 确保已进入 "文件传输助手"
        try:
            header = self.wechat_window.TextControl(Name='文件传输助手')
            if not header.Exists(2):
                logging.info("当前不是'文件传输助手'，正在切换...")
                # 优先通过左侧列表点击
                chat_list = self.wechat_window.ListControl(Name='会话')
                if not chat_list.Exists(2):
                    chat_list = self.wechat_window.ListControl(Name='消息')
                
                file_transfer_item = chat_list.ListItemControl(Name='文件传输助手')
                if file_transfer_item.Exists(5):
                    file_transfer_item.Click(simulateMove=True)
                    time.sleep(2)
                else:
                    logging.error("在左侧列表中未找到'文件传输助手'，无法获取消息。")
                    return []
            else:
                logging.info("已在'文件传输助手'聊天窗口。")
        except Exception as e:
            logging.error(f"切换到'文件传输助手'失败: {e}")
            return []

        # 2. 查找消息列表并提取消息
        messages = []
        try:
            # 微信的消息列表通常是一个名为 "消息" 的 ListControl
            message_list_control = self.wechat_window.ListControl(Name='消息')
            if not message_list_control.Exists(3):
                logging.error("未能找到聊天记录的'消息'列表控件。")
                return []
            
            # 获取列表中的所有消息项
            message_items = message_list_control.GetChildren()
            logging.info(f"找到 {len(message_items)} 条消息记录，正在提取内容...")
            
            for item in message_items:
                # 消息内容可能嵌套在多层子控件中，需要递归查找
                # 首先检查消息项本身是否有Name
                if item.Name:
                    messages.append(item.Name)
                    continue # 如果项本身有名字，就用它，然后处理下一项

                # 如果项本身没有名字，则递归查找其子控件
                try:
                    # 使用一个简单的栈来实现深度优先搜索，避免过深的递归
                    stack = item.GetChildren()
                    found_message = False
                    while stack and not found_message:
                        child = stack.pop(0) # 使用队列实现广度优先
                        if child.Name:
                            # 过滤掉一些常见的、非消息内容的控件名称
                            if child.Name not in ['图片', '视频', '链接', '文件']:
                                messages.append(child.Name)
                                found_message = True # 找到后处理下一个消息项
                                break
                        # 将子控件的子控件也加入待搜索列表
                        if hasattr(child, 'GetChildren'):
                            stack.extend(child.GetChildren())
                except Exception as find_e:
                    logging.debug(f"在消息项内查找文本时出错: {find_e}")

            logging.info(f"成功提取到 {len(messages)} 条消息。")
            return messages
        except Exception as e:
            logging.error(f"提取消息时发生错误: {e}")
            return []

    def get_message_list(self) -> list:
        """
        获取当前消息列表中的所有会话名称。
        参考 debug_message_list.py 的实现。
        """
        if not self._check_automation_available():
            return []

        if not self.activate_wechat():
            return []

        logging.info("正在获取消息列表...")
        message_list_names = []
        
        # 优先尝试查找名为 "会话" 的列表，这是较新版本微信的标识
        chat_list = self.wechat_window.ListControl(Name='会话')
        
        # 如果找不到，尝试备用名称 "消息"
        if not chat_list.Exists(3):
            logging.info("未找到'会话'列表，尝试查找'消息'列表...")
            chat_list = self.wechat_window.ListControl(Name='消息')

        if chat_list.Exists(2):
            try:
                list_items = chat_list.GetChildren()
                for item in list_items:
                    if hasattr(item, 'Name') and item.Name:
                        message_list_names.append(item.Name)
                logging.info(f"成功获取到 {len(message_list_names)} 个会话。")
                return message_list_names
            except Exception as e:
                logging.error(f"遍历消息列表项时出错: {e}")
                return []
        else:
            logging.error("未能找到消息列表控件 (尝试了'会话'和'消息')。")
            return []

    def find_and_activate_browser_window(self) -> bool:
        """
        查找并激活微信的浏览器窗口（文章阅读窗口）
        支持使用GetFocusedControl和传统的窗口查找相结合的方式
        
        返回:
            bool: 是否成功找到并激活浏览器窗口
        """
        if not self._check_automation_available():
            return False
        
        logging.info("正在查找微信浏览器窗口...")
        
        try:
            # 方法1: 使用GetFocusedControl查找当前焦点窗口
            logging.info("尝试使用GetFocusedControl查找当前焦点窗口...")
            focused_control = auto.GetFocusedControl()
            if focused_control:
                current_window = focused_control.GetTopLevelControl()
                if current_window and current_window != self.wechat_window:
                    window_title = current_window.Name
                    window_class = current_window.ClassName
                    
                    # 检查是否为浏览器相关窗口
                    browser_indicators = [
                        "微信",
                        "Cef",
                        "WebView",
                        "Chrome",
                        "Internet"
                    ]
                    
                    title_match = any(indicator.lower() in window_title.lower() for indicator in browser_indicators)
                    class_match = any(indicator.lower() in window_class.lower() for indicator in browser_indicators)
                    
                    if title_match or class_match:
                        logging.info(f"通过焦点检测找到浏览器窗口: '{window_title}' ({window_class})")
                        current_window.SetActive()
                        # 使用Alt+Tab模拟窗口切换，确保焦点正确
                        auto.PressKey(auto.Keys.VK_MENU, 0.1)
                        auto.PressKey(auto.Keys.VK_TAB, 0.1)
                        auto.ReleaseKey(auto.Keys.VK_TAB)
                        auto.ReleaseKey(auto.Keys.VK_MENU)
                        time.sleep(0.5)
                        current_window.SetActive()
                        logging.info("已成功激活焦点浏览器窗口")
                        return True
                    else:
                        logging.debug(f"焦点窗口不是浏览器窗口: '{window_title}' ({window_class})")
            
            # 方法2: 传统的窗口查找方法（作为备用）
            logging.info("尝试传统窗口查找方法...")
            
            # 查找微信的浏览器窗口，可能有以下几种可能
            browser_search_patterns = [
                {"Name": "微信文章"},
                {"Name": "微信公众平台"},
                {"Name": "微信"},  # 通用标题
                {"ClassName": "CefWebViewWnd"},
                {"ClassName": "Chrome_WidgetWin_1"},
                {"ClassName": "WeChatWebview"},
            ]
            
            # 先检查是否有明显的差异
            for pattern in browser_search_patterns:
                try:
                    if "Name" in pattern:
                        browser_window = auto.WindowControl(Name=pattern["Name"])
                    elif "ClassName" in pattern:
                        browser_window = auto.WindowControl(ClassName=pattern["ClassName"])
                    else:
                        continue
                        
                    if browser_window.Exists(1):  # 缩短等待时间
                        logging.info(f"找到浏览器窗口: {pattern}")
                        browser_window.SetActive()
                        browser_window.SetTopmost(True)
                        time.sleep(0.3)
                        browser_window.SetTopmost(False)
                        logging.info("已成功激活浏览器窗口")
                        return True
                except Exception as e:
                    logging.debug(f"使用模式 {pattern} 查找浏览器窗口失败: {e}")
                    continue
            
            # 方法3: 查找所有可见的微信相关窗口，排除主窗口
            logging.info("使用通用窗口查找方法...")
            all_windows = auto.GetRootControl().GetChildren()
            candidate_windows = []
            
            for window in all_windows:
                try:
                    window_name = window.Name if hasattr(window, 'Name') else ""
                    window_class = window.ClassName if hasattr(window, 'ClassName') else ""
                    
                    # 检查是否为微信相关而非主窗口
                    is_wechat_related = "微信" in window_name or any(cls.lower() in window_class.lower() for cls in [
                        'Cef', 'WebView', 'Chrome', 'Internet', 'MSWindowClass'
                    ])
                    
                    is_not_main = window_class != 'WeChatMainWndForPC'
                    
                    if is_wechat_related and is_not_main and window.Exists(1):
                        candidate_windows.append(window)
                        logging.info(f"候选浏览器窗口: '{window_name}' ({window_class})")
                except:
                    continue
            
            if candidate_windows:
                # 选择第一个候选窗口
                selected_window = candidate_windows[0]
                selected_window.SetActive()
                logging.info(f"激活候选浏览器窗口: '{selected_window.Name}' ({selected_window.ClassName})")
                return True
            
            logging.error("无法找到并激活微信的浏览器窗口")
            return False
            
        except Exception as e:
            logging.error(f"查找和激活浏览器窗口时发生错误: {e}")
            return False

    def auto_refresh_browser(self, refresh_count: int = 2, refresh_delay: float = 2, cookie_reader=None) -> bool:
        """
        自动刷新当前打开的浏览器窗口（使用浏览器窗口自动检测）

        参数:
            refresh_count: 刷新次数，默认3次（适合抓包需求）
            refresh_delay: 每次刷新后的等待时间（秒），默认2.5秒
            cookie_reader: 可选，抓包读取器；若提供，将在检测到抓包成功后提前停止

        返回:
            bool: 刷新操作是否成功
        """
        if not self._check_automation_available():
            return False

        logging.info("开始执行自动浏览器刷新...")

        try:
            # 如果提供了cookie_reader，先检查是否已经抓到
            if cookie_reader and self._check_cookie_captured(cookie_reader):
                logging.info("检测到已抓包成功，无需刷新")
                return True

            # 在开始刷新前，先检查并处理SSL证书错误页面
            logging.info("首先检查是否存在SSL证书错误页面...")
            if self.handle_ssl_certificate_error():
                logging.info("✅ 检测到SSL证书错误页面，已使用 'thisisunsafe' 自动绕过")
                # 等待页面重新加载完成
                time.sleep(3)
            else:
                logging.info("未检测到SSL证书错误页面，开始正常刷新流程")

            for i in range(refresh_count):
                refresh_num = i + 1
                logging.info(f"正在执行第 {refresh_num} 次刷新操作...")

                # 刷新前再次检测是否已抓到
                if cookie_reader and self._check_cookie_captured(cookie_reader):
                    logging.info(f"🎉 刷新前检测到抓包成功，在第 {refresh_num} 次前结束")
                    return True

                # 每次刷新前都尝试找到并激活浏览器窗口
                if self.find_and_activate_browser_window():
                    # 给窗口一点时间完全获得焦点
                    time.sleep(0.5)

                    # 发送F5按键进行刷新
                    auto.SendKey(auto.Keys.VK_F5)
                    logging.info("已发送F5刷新指令到浏览器窗口")
                else:
                    # 如果找不到浏览器窗口，尝试使用通用方法
                    logging.warning("未找到浏览器窗口，使用通用刷新方法")
                    auto.SendKey(auto.Keys.VK_F5)

                # 等待页面刷新完成
                logging.info(f"等待页面刷新完成... ({refresh_delay}秒)")
                time.sleep(refresh_delay)

                # 刷新后检测是否已抓到
                if cookie_reader and self._check_cookie_captured(cookie_reader):
                    logging.info(f"🎉 刷新后检测到抓包成功，在第 {refresh_num} 次后结束")
                    return True

                logging.info(f"第 {refresh_num} 次刷新完成")

                # 如果不是最后一次，等待更长时间让页面稳定
                if i < refresh_count - 1:
                    time.sleep(2)  # 给浏览器窗口留充足时间

            logging.info("✅ 自动刷新操作全部完成")
            return True

        except Exception as refresh_error:
            logging.error(f"自动刷新操作失败: {refresh_error}")
            return False

    def handle_ssl_certificate_error(self) -> bool:
        """
        检测并处理SSL证书错误页面（"您的连接不是私密连接"）
        如果检测到此类页面，自动输入 "thisisunsafe" 来绕过

        返回:
            bool: 是否检测到并处理了SSL证书错误页面
        """
        if not self._check_automation_available():
            return False

        try:
            # 首先确保浏览器窗口处于活动状态
            if not self.find_and_activate_browser_window():
                logging.warning("无法激活浏览器窗口，跳过SSL证书错误检测")
                return False

            # 等待页面完全加载
            time.sleep(1.5)

            logging.info("正在检测SSL证书错误页面...")

            # 方法1: 通过窗口标题检测
            try:
                focused_control = auto.GetFocusedControl()
                if focused_control:
                    current_window = focused_control.GetTopLevelControl()
                    if current_window:
                        window_title = current_window.Name.lower() if current_window.Name else ""

                        # 检测常见的SSL错误页面标题关键词
                        ssl_error_indicators = [
                            "您的连接不是私密连接",
                            "your connection is not private",
                            "privacy error",
                            "不安全",
                            "not secure",
                            "隐私设置错误",
                            "此连接不是私密连接"
                        ]

                        title_has_ssl_error = any(indicator in window_title for indicator in ssl_error_indicators)

                        if title_has_ssl_error:
                            logging.info(f"🔍 通过窗口标题检测到SSL证书错误页面: '{current_window.Name}'")
                            return self._bypass_ssl_error()
            except Exception as e:
                logging.debug(f"通过窗口标题检测SSL错误失败: {e}")

            # 方法2: 尝试查找页面中的特定文本控件
            try:
                # 查找包含SSL错误信息的文本控件
                ssl_error_texts = [
                    "您的连接不是私密连接",
                    "Your connection is not private",
                    "Privacy error",
                    "NET::ERR_CERT",
                    "此连接不是私密连接",
                    "隐私设置错误"
                ]

                for error_text in ssl_error_texts:
                    try:
                        # 在当前窗口中查找包含错误文本的控件
                        error_control = auto.TextControl(Name=error_text, searchDepth=4)
                        if error_control.Exists(1):  # 短暂等待
                            logging.info(f"🔍 通过页面文本检测到SSL证书错误: '{error_text}'")
                            return self._bypass_ssl_error()
                    except:
                        continue

            except Exception as e:
                logging.debug(f"通过页面文本检测SSL错误失败: {e}")

            # 方法3: 通过URL地址栏检测（如果可以获取到）
            try:
                # 尝试检测地址栏中是否包含错误相关的URL
                # 这种方法适用于某些浏览器会在地址栏显示错误信息的情况
                address_bar = auto.EditControl(searchDepth=3)
                if address_bar.Exists(1):
                    address_text = address_bar.GetValuePattern().Value if hasattr(address_bar, 'GetValuePattern') else ""
                    if address_text and any(indicator in address_text.lower() for indicator in ["err_cert", "privacy", "unsafe"]):
                        logging.info(f"🔍 通过地址栏检测到SSL证书错误: '{address_text}'")
                        return self._bypass_ssl_error()
            except Exception as e:
                logging.debug(f"通过地址栏检测SSL错误失败: {e}")

            # 如果没有检测到SSL错误，返回False
            logging.debug("未检测到SSL证书错误页面")
            return False

        except Exception as e:
            logging.error(f"检测SSL证书错误时发生异常: {e}")
            return False

    def _bypass_ssl_error(self) -> bool:
        """
        执行SSL证书错误绕过操作：输入 "thisisunsafe"

        返回:
            bool: 绕过操作是否成功
        """
        try:
            logging.info("🔧 开始执行SSL证书错误绕过操作...")

            # 确保浏览器窗口获得焦点
            time.sleep(0.8)

            # 点击页面中央确保焦点在页面上
            try:
                focused_control = auto.GetFocusedControl()
                if focused_control:
                    current_window = focused_control.GetTopLevelControl()
                    if current_window:
                        rect = current_window.BoundingRectangle
                        center_x = rect.left + (rect.right - rect.left) // 2
                        center_y = rect.top + (rect.bottom - rect.top) // 2
                        auto.Click(center_x, center_y)
                        time.sleep(0.3)
            except Exception as e:
                logging.debug(f"点击页面中央失败: {e}")

            # 清空可能存在的输入内容
            auto.SendKeys('{Ctrl}a')
            time.sleep(0.2)

            # 输入绕过代码
            bypass_code = "thisisunsafe"
            logging.info(f"🔑 正在输入绕过代码: {bypass_code}")

            # 方法1: 尝试直接输入整个字符串
            try:
                auto.SendKeys(bypass_code)
                time.sleep(0.5)
                logging.info("✅ 使用直接输入方式完成绕过代码输入")
            except Exception as e:
                logging.warning(f"直接输入失败，尝试逐字符输入: {e}")
                # 方法2: 逐字符输入，确保稳定性
                for i, char in enumerate(bypass_code):
                    try:
                        auto.SendKeys(char)
                        time.sleep(0.08)  # 每个字符间短暂延迟
                        logging.debug(f"已输入字符 {i+1}/{len(bypass_code)}: '{char}'")
                    except Exception as char_error:
                        logging.warning(f"输入字符 '{char}' 失败: {char_error}")
                        continue

            logging.info("✅ SSL证书错误绕过代码已输入，等待页面自动刷新...")

            # 等待页面自动刷新（Chrome会自动处理）
            # 增加等待时间，确保页面完全重新加载
            time.sleep(3)

            # 验证绕过是否成功（可选）
            try:
                # 再次检查是否还存在SSL错误页面
                time.sleep(1)
                focused_control = auto.GetFocusedControl()
                if focused_control:
                    current_window = focused_control.GetTopLevelControl()
                    if current_window:
                        window_title = current_window.Name.lower() if current_window.Name else ""
                        if any(indicator in window_title for indicator in ["您的连接不是私密连接", "your connection is not private"]):
                            logging.warning("⚠️ SSL证书错误页面仍然存在，绕过可能未成功")
                            return False
                        else:
                            logging.info("✅ SSL证书错误页面已消失，绕过成功")
            except Exception as e:
                logging.debug(f"验证绕过结果时出错: {e}")

            return True

        except Exception as e:
            logging.error(f"执行SSL证书错误绕过操作失败: {e}")
            return False

    def _check_cookie_captured(self, cookie_reader) -> bool:
        """
        检查是否已经成功抓取到Cookie

        参数:
            cookie_reader: ReadCookie实例

        返回:
            bool: 是否已经抓取到有效的Cookie
        """
        try:
            if not cookie_reader:
                return False

            # 检查输出文件是否存在且有内容
            if not hasattr(cookie_reader, 'outfile') or not cookie_reader.outfile:
                return False

            import os
            if not os.path.exists(cookie_reader.outfile):
                return False

            if os.path.getsize(cookie_reader.outfile) == 0:
                return False

            # 尝试解析Cookie，看是否有有效数据
            appmsg_token, biz, cookie_str, headers = cookie_reader.parse_cookie()

            if appmsg_token and biz and cookie_str:
                logging.debug(f"检测到有效Cookie: biz={biz[:20]}..., token={appmsg_token[:20]}...")
                return True
            else:
                logging.debug("Cookie文件存在但未包含有效数据")
                return False

        except Exception as e:
            logging.debug(f"检查Cookie状态时出错: {e}")
            return False


def main():
    """主函数，用于测试自动化模块"""
    logging.info("开始测试微信浏览器自动化模块...")
    
    automation = WeChatBrowserAutomation()

    # --- 测试发送并点击链接的完整流程 ---
    # !!!重要!!! 请将下面的链接替换为一个真实有效的微信文章链接
    test_url = "https://mp.weixin.qq.com/s?__biz=Mzg3MzcwMjI5NQ==&mid=2247521212&idx=1&sn=2d7cae536e0ced5e4f59ded16b88ab30&chksm=cf77a61131b97056fa39d8d9863d17ebd6c23a14e37c3dfd8cdcc5bb00fe2c549e215b8928d8&scene=27#wechat_redirect" 

    if "your_article_id" in test_url:
        logging.warning("请在main函数中设置一个有效的微信文章链接以进行完整流程测试。")
    else:
        print(f"\n--- 开始执行发送并点击链接的完整流程 ---")
        
        # 演示不同的使用方法：
        
        # 方法1: 默认行为（自动刷新3次，每次间隔2.5秒）
        print("\n📋 方法1: 使用默认刷新设置（3次刷新）")
        success = automation.send_and_open_latest_link(test_url)
        
        # 方法2: 禁用自动刷新
        # print("\n🔍 方法2: 禁用自动刷新功能")
        # success = automation.send_and_open_latest_link(test_url, auto_refresh=False)
        
        # 方法3: 自定义刷新次数（2次刷新，适合轻度抓包）
        # print("\n⚙️ 方法3: 2次刷新模式")
        # success = automation.send_and_open_latest_link(test_url, refresh_count=2, refresh_delay=3.0)
        
        # 方法4: 手动控制刷新设置
        # print("\n🎛️ 方法4: 自定义手动配置")
        # success = automation.send_and_open_latest_link(
        #     test_url, 
        #     auto_refresh=True, 
        #     refresh_count=3, 
        #     refresh_delay=5.0
        # )
        
        if success:
            print("\n✅ 完整流程执行成功！")
        else:
            print("\n❌ 完整流程执行失败，请检查日志获取详细信息。")
        print("--- 流程执行结束 ---\n")
        
        # 独立使用刷新功能
        # print("\n--- 独立使用自动刷新功能 ---")
        # time.sleep(5)  # 等待手动打开文章链接
        # success = automation.auto_refresh_browser(refresh_count=2, refresh_delay=4.0)
        # print(f"独立刷新结果: {'成功' if success else '失败'}")


if __name__ == "__main__":
    # 检查uiautomation是否可用
    if not UI_AUTOMATION_AVAILABLE:
        # 如果库不可用，直接退出，避免后续执行报错
        exit()
    main()