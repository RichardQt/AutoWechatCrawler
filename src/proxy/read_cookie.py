# read_cookie.py
import re
import os
import sys
import subprocess
import time
import logging
import platform
from datetime import datetime
from src.proxy.unified_proxy_manager import UnifiedProxyManager
import shutil
import socket

class ReadCookie(object):
    """
    启动cookie_extractor.py和解析cookie文件
    """

    def __init__(self, outfile="wechat_keys.txt", delete_existing_file: bool = True):
        self.outfile = outfile
        self.mitm_process = None
        self.started_via_manual_mitm = False
        self.logger = logging.getLogger()
        self.proxy_manager = UnifiedProxyManager()
        # 根据参数决定是否删除旧文件
        if delete_existing_file and os.path.exists(self.outfile):
            os.remove(self.outfile)
            self.logger.info(f"已删除旧的日志文件: {self.outfile}")
        # 选择一个可用端口（8080-8090）
        self.port = self._find_free_port(list(range(8080, 8091)))
        if not self.port:
            self.port = 8080  # 兜底
        self.logger.info(f"本次抓包将使用端口: {self.port}")

    def _find_free_port(self, port_range):
        for p in port_range:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                try:
                    if s.connect_ex(("127.0.0.1", p)) != 0:
                        return p
                except Exception:
                    continue
        return None

    def parse_cookie(self):
        """
        解析cookie文件，提取最新的appmsg_token、biz、cookie_str和headers
        :return: appmsg_token, biz, cookie_str, headers
        """
        if not os.path.exists(self.outfile):
            self.logger.warning(f"文件 {self.outfile} 不存在")
            return None, None, None, None

        with open(self.outfile, 'r', encoding='utf-8') as f:
            content = f.read()

        records = content.split('=' * 60)
        for record in reversed(records):
            if 'Cookies:' in record and 'allurl:' in record:
                lines = record.strip().split('\n')
                url_line = cookie_line = None
                headers_section = False
                headers = {}
                for line in lines:
                    if line.startswith('allurl:'): url_line = line
                    elif line.startswith('Cookies:'): cookie_line = line
                    elif line.startswith('Headers:'): headers_section = True
                    elif headers_section and line.startswith('  '):
                        header_match = re.match(r'\s+([^:]+):\s*(.+)', line)
                        if header_match:
                            headers[header_match.group(1).strip()] = header_match.group(2).strip()
                
                if url_line and cookie_line:
                    url = url_line.split('allurl:', 1)[1].strip()
                    biz_match = re.search(r'__biz=([^&]+)', url)
                    biz = biz_match.group(1) if biz_match else None
                    cookie_str = cookie_line.split('Cookies:', 1)[1].strip()
                    appmsg_token_match = re.search(r'appmsg_token=([^;]+)', cookie_str)
                    appmsg_token = appmsg_token_match.group(1) if appmsg_token_match else None
                    # 回退：若 Cookies 中未出现 appmsg_token，尝试从 URL 查询参数提取
                    if not appmsg_token:
                        appmsg_token_q = re.search(r'[?&]appmsg_token=([^&]+)', url)
                        if appmsg_token_q:
                            appmsg_token = appmsg_token_q.group(1)

                    if appmsg_token and biz and cookie_str:
                        self.logger.info("从文件中解析到有效Cookie数据。")
                        return appmsg_token, biz, cookie_str, headers
        
        self.logger.warning("在文件中未找到有效的Cookie数据。")
        return None, None, None, None

    def start_cookie_extractor(self) -> bool:
        """
        在后台启动cookie_extractor.py进行cookie抓取 (非阻塞)
        """
        self.logger.info("🚀 开始启动Cookie抓取器...")
        
        try:
            # 确保网络状态是干净的
            self.logger.info("步骤1: 正在准备网络环境...")
            
            # 显示当前代理模式信息
            proxy_mode = self.proxy_manager.get_proxy_mode()
            proxy_info = self.proxy_manager.get_proxy_info()
            self.logger.info(f"[INFO] 当前代理模式: {proxy_mode}")
            if proxy_mode == 'pool':
                self.logger.info("[INFO] 代理池模式详情:")
                self.logger.info(f"   - 当前代理: {proxy_info.get('current_proxy', '无')}")
                self.logger.info(f"   - 代理启用状态: {proxy_info.get('proxy_enabled', False)}")
            else:
                self.logger.info("[INFO] 传统代理模式详情:")
                self.logger.info(f"   - 系统代理状态: {proxy_info.get('system_proxy_enabled', False)}")
            
            if not self.proxy_manager.reset_network_state():
                self.logger.warning("⚠️ 网络清理可能存在异常，继续尝试启动...")
            
            # 备份原始代理设置
            try:
                self.logger.info("步骤2: 正在备份原始网络配置...")
                self.proxy_manager.backup_proxy_settings()
            except Exception as e:
                self.logger.warning(f"⚠️ 备份网络配置失败: {e}")
            
            current_path = os.path.dirname(os.path.realpath(__file__))
            extractor_path = os.path.join(current_path, 'cookie_extractor.py')

            env_manual = os.environ.get('USE_MANUAL_MITM')
            # 默认改为使用 manual_mitm_capture.py；仅当 USE_MANUAL_MITM=0/false 时回退到 cookie_extractor
            use_manual = True if env_manual is None else (env_manual.lower() not in ['0', 'false'])
            if use_manual:
                # 使用项目根目录的 manual_mitm_capture.py （极简模式，不保存flow/JSON，不自动安装证书）
                project_root = os.path.abspath(os.path.join(current_path, os.pardir, os.pardir))
                manual_script = os.path.join(project_root, 'manual_mitm_capture.py')
                if not os.path.exists(manual_script):
                    self.logger.error(f"❌ 未找到 manual_mitm_capture.py: {manual_script}")
                    return False
                py = os.environ.get('PYTHON_EXECUTABLE', sys.executable or 'python')
                command = [py, manual_script, "--port", str(self.port), "--filter", "mp.weixin.qq.com"]
                self.started_via_manual_mitm = True
            else:
                if not os.path.exists(extractor_path):
                    self.logger.error(f"❌ 未找到cookie_extractor.py文件: {extractor_path}")
                    return False
                command = ["mitmdump", "-s", extractor_path, "--listen-port", str(self.port), "--ssl-insecure"]
                self.started_via_manual_mitm = False
            
            self.logger.info(f"步骤3: 正在启动命令: {' '.join(command)}")
            # 将端口通过环境变量传递给 mitm addon，以便写入一致的系统代理
            child_env = os.environ.copy()
            child_env['MITM_PORT'] = str(self.port)
            
            # 可选: 检查 mitmdump 版本 (允许跳过)
            skip_version = os.environ.get('MITMDUMP_SKIP_VERSION') == '1'
            if skip_version:
                self.logger.warning("[MITM] 已根据环境变量 MITMDUMP_SKIP_VERSION=1 跳过版本检测")
            else:
                mitm_path = shutil.which('mitmdump')
                if not mitm_path:
                    self.logger.error("❌ 未找到 mitmdump 可执行文件 (不在 PATH). 可执行: pip install mitmproxy 或设置 PATH / 使用 venv。")
                    return False
                progressive_timeouts = [3, 6, 10]
                last_err = None
                version_ok = False
                for to in progressive_timeouts:
                    try:
                        self.logger.info(f"[MITM] 进行 mitmdump --version 检测 (超时 {to}s)... 路径: {mitm_path}")
                        start_ts = time.time()
                        proc = subprocess.run(["mitmdump", "--version"], capture_output=True, text=True, timeout=to)
                        elapsed = time.time() - start_ts
                        if proc.returncode == 0:
                            out = (proc.stdout or proc.stderr).strip().splitlines()[0]
                            self.logger.info(f"✅ mitmdump版本: {out} (耗时 {elapsed:.2f}s)")
                            version_ok = True
                            break
                        last_err = f"exit_code={proc.returncode} stdout={proc.stdout} stderr={proc.stderr}"
                    except subprocess.TimeoutExpired:
                        last_err = f"超时>{to}s"
                        self.logger.warning(f"[MITM] --version 在 {to}s 内无响应 (可能首次生成证书/被杀毒扫描) 继续尝试下一阶段...")
                    except Exception as e:
                        last_err = repr(e)
                        self.logger.warning(f"[MITM] 版本检测异常: {e}")
                if not version_ok:
                    # 尝试 python import fallback
                    try:
                        self.logger.info("[MITM] 尝试 python -c import 方式获取版本 ...")
                        fallback = subprocess.check_output([
                            os.environ.get('PYTHON_EXECUTABLE', 'python'),
                            '-c', 'import mitmproxy.version as v;print(v.VERSION)'
                        ], text=True, timeout=5).strip()
                        if fallback:
                            self.logger.info(f"✅ mitmdump版本 (fallback): {fallback}")
                            version_ok = True
                    except Exception as e:
                        self.logger.warning(f"[MITM] fallback 仍失败: {e}")
                if not version_ok:
                    self.logger.warning(f"[MITM] 未能确认 mitmdump 版本 (最后错误: {last_err}) => 仍尝试启动代理。可设置 MITMDUMP_SKIP_VERSION=1 直接跳过。")
            
            # 不重定向输出，让mitmproxy直接输出到控制台，避免管道阻塞
            self.mitm_process = subprocess.Popen(command, env=child_env)

            self.logger.info(f"🔄 Cookie抓取器进程已启动，PID: {self.mitm_process.pid}")

            # 等待并验证代理服务正常
            self.logger.info("步骤4: 等待代理服务启动... (最多30秒)")
            time.sleep(3)  # 减少初始等待时间

            if self.proxy_manager.wait_for_proxy_ready(max_wait=30):
                # 关键：在手动抓包模式下，同步开启系统代理到相同端口，确保微信流量走代理
                try:
                    self.logger.info(f"正在启用系统代理到 127.0.0.1:{self.port} 以捕获微信流量...")
                    if not self.proxy_manager.enable_proxy(self.port):
                        self.logger.warning("⚠️ 启用系统代理失败，可能影响抓包 (请检查权限/注册表策略)")
                    else:
                        # 给系统代理一点时间生效
                        time.sleep(2)
                except Exception as e:
                    self.logger.warning(f"⚠️ 启用系统代理时异常: {e}")

                self.logger.info(f"✅ Cookie抓取器已成功启动并运行正常 (PID: {self.mitm_process.pid})")
                return True
            else:
                self.logger.error("❌ 代理服务无法正常启动")
                # 检查进程是否还在运行
                if self.mitm_process.poll() is not None:
                    self.logger.error(f"进程已退出，返回码: {self.mitm_process.returncode}")
                else:
                    self.logger.error("进程仍在运行，但代理服务无响应")
                self.stop_cookie_extractor()
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("❌ Cookie抓取器响应超时")
            self.stop_cookie_extractor()
            return False
        except FileNotFoundError as e:
            self.logger.error(f"❌ 找不到必要的可执行文件: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ 启动Cookie抓取器时出现意外错误: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.stop_cookie_extractor()
            return False

    def stop_cookie_extractor(self):
        """停止后台的mitmdump进程并确保代理完全关闭"""
        self.logger.info("🧹 开始清理抓取器资源...")
        
        # 1. 直接停止mitmproxy进程
        if self.mitm_process and self.mitm_process.poll() is None:
            self.logger.info(f"正在停止Cookie抓取器 (PID: {self.mitm_process.pid})...")
            try:
                if self.started_via_manual_mitm and platform.system().lower().startswith('win'):
                    # Windows下杀进程树，避免残留 mitmdump 子进程
                    subprocess.run(["taskkill", "/PID", str(self.mitm_process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.logger.info("已通过 taskkill 终止 manual_mitm_capture 及其子进程。")
                else:
                    # 优雅地终止进程
                    self.mitm_process.terminate()
                    self.mitm_process.wait(timeout=5)
                    self.logger.info("Cookie抓取器已成功终止。")
            except subprocess.TimeoutExpired:
                self.logger.warning("终止超时，正在强制终止...")
                self.mitm_process.kill()
                self.mitm_process.wait(timeout=3)
                self.logger.info("Cookie抓取器已被强制终止。")
            except Exception as e:
                self.logger.error(f"停止Cookie抓取器时发生错误: {e}")
        else:
            self.logger.info("Cookie抓取器未在运行或已停止。")
        
        # 2. 使用新的ProxyManager确保代理设置被清理
        self.logger.info("正在验证并清理代理设置...")
        if self.proxy_manager.reset_network_state():
            self.logger.info("✅ 代理已完全关闭，网络状态已清理")
        else:
            self.logger.error("❌ 代理清理可能不完全")
        
        # 3. 验证网络连接是否正常
        if self.proxy_manager.validate_and_fix_network():
            self.logger.info("✅ 网络连接验证正常")
        else:
            self.logger.warning("⚠️ 网络连接验证失败，可能需要手动检查")

    def wait_for_new_cookie(self, timeout: int = 60) -> bool:
        """
        在指定时间内等待wechat_keys.txt文件被创建并包含有效内容。
        """
        self.logger.info(f"正在等待Cookie数据写入 '{self.outfile}'... (超时: {timeout}秒)")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(self.outfile) and os.path.getsize(self.outfile) > 0:
                time.sleep(1) # 等待文件写完
                self.logger.info("检测到Cookie文件已生成。")
                return True
            time.sleep(1)
        
        self.logger.error("等待Cookie超时！")
        return False

    def get_latest_cookies(self):
        """
        获取最新的cookie信息
        """
        appmsg_token, biz, cookie_str, headers = self.parse_cookie()
        if appmsg_token and biz and cookie_str:
            return {
                'appmsg_token': appmsg_token,
                'biz': biz,
                'cookie_str': cookie_str,
                'headers': headers,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        return None
def main():
    """主函数，演示如何使用"""
    print("=== 微信Cookie抓取器 ===")
    print("1. 自动启动抓取")
    print("2. 只解析现有文件")

    choice = input("请选择操作(1/2): ").strip()

    if choice == '1':
        # 重新抓取Cookie，删除旧文件
        rc = ReadCookie()
        # 启动抓取器
        if rc.start_cookie_extractor(timeout=120):  # 2分钟超时
            print("\n抓取完成，开始解析...")
            time.sleep(1)  # 等待文件写入完成
        else:
            print("抓取器启动失败")
            return
    else:
        # 只解析现有文件，不删除
        rc = ReadCookie(delete_existing_file=False)

    # 解析cookie
    result = rc.get_latest_cookies()
    
    if result:
        print("\n" + "="*50)
        print("解析结果:")
        print(f"appmsg_token: {result['appmsg_token']}")
        print(f"biz: {result['biz']}")
        print(f"cookie: {result['cookie_str']}")
        print(f"解析时间: {result['timestamp']}")
        print("="*50)
    else:
        print("未找到有效的cookie数据，请确保:")
        print("1. 已正确访问微信公众号文章")
        print("2. 代理设置正确(127.0.0.1:8080)")
        print("3. wechat_keys.txt文件中有有效数据")

if __name__ == '__main__':
    main()
