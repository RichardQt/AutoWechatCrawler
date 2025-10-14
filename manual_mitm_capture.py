"""
最小化微信抓包脚本（用于自动流程默认抓包后端）

变化：
- 去除 CA 自动安装、flows/JSON 摘要等重型逻辑，仅负责启动 mitmproxy 并加载微信抓包 addon。
- 端口默认读取环境变量 MITM_PORT；未设置时扫描 8080-8090。
- 支持 `--web` 和 `--filter` 两个轻量参数；其它历史参数移除。
"""
from __future__ import annotations
import argparse
import os
import sys
import socket
import signal
import time
import shutil
import subprocess
import platform
from datetime import datetime
from pathlib import Path

PORT_RANGE = list(range(8080, 8091))
process: subprocess.Popen | None = None
start_time = time.time()
wechat_keys_file = Path("wechat_keys.txt")  # 保存到项目根目录


def find_free_port() -> int:
    for p in PORT_RANGE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            try:
                if s.connect_ex(("127.0.0.1", p)) != 0:
                    return p
            except Exception:
                continue
    raise RuntimeError("没有可用端口 (8080-8090)")


def ensure_mitm_exists():
    exe = shutil.which("mitmdump")
    if not exe:
        raise SystemExit("未找到 mitmdump 可执行文件，请先: pip install mitmproxy")
    return exe


def build_command(args, port: int) -> list[str]:
    base_tool = "mitmweb" if args.web else "mitmdump"
    
    # 创建临时的微信抓包脚本
    addon_script = create_wechat_addon_script()
    
    cmd = [base_tool,
           "--listen-host", "0.0.0.0",
           "--listen-port", str(port),
           "--ssl-insecure",
           "-s", str(addon_script)]

    if args.filter:
        cmd += ["--set", f"console_filter={args.filter}"]
    # 降低事件日志噪音
    cmd += ["--set", "console_eventlog_verbosity=warn"]

    if args.web:
        # web 模式附加说明: mitmweb 默认会起 8081 (或下一个) 作为前端端口
        cmd += ["--web-host", "127.0.0.1"]
    return cmd


def parse_args():
    p = argparse.ArgumentParser(description="手动/极简 mitmproxy 抓包")
    p.add_argument("--port", type=int, help="指定监听端口, 优先于环境变量 MITM_PORT，未指定则自动扫描 8080-8090")
    p.add_argument("--web", action="store_true", help="使用 mitmweb 图形界面")
    p.add_argument("--filter", help="显示过滤 (mitmproxy display filter), 例如 wechat|weixin")
    return p.parse_args()


def graceful_exit(*_):
    global process
    print("\n[INFO] 收到退出信号, 正在清理 ...")
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=5)
            print("[INFO] 已终止 mitmproxy 进程")
        except subprocess.TimeoutExpired:
            print("[WARN] 终止超时, 强制 kill")
            process.kill()
        except Exception as e:
            print(f"[ERROR] 结束进程异常: {e}")

    # 清理临时文件
    temp_dir = Path("temp")
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
            
    dur = time.time() - start_time
    print(f"[DONE] 已退出. 总运行时长: {dur:.1f}s")
    if wechat_keys_file.exists():
        print(f"[SAVE] 微信抓包数据: {wechat_keys_file.absolute()}")
    sys.exit(0)


    # 已移除 JSON 摘要功能


def create_wechat_addon_script() -> Path:
    """创建微信抓包的 mitmproxy addon 脚本"""
    addon_dir = Path("temp")
    addon_dir.mkdir(exist_ok=True)
    addon_path = addon_dir / "wechat_capture_addon.py"
    
    addon_code = '''# 微信抓包 Addon
import re
from datetime import datetime
from mitmproxy import http
from pathlib import Path

class WechatCaptureAddon:
    def __init__(self):
        self.keys_file = Path("wechat_keys.txt")
        self.saved_urls = set()  # URL去重
        self.saved_cookies = set()  # Cookie去重
        self.init_keys_file()
        
    def init_keys_file(self):
        """初始化或追加到keys文件"""
        if not self.keys_file.exists():
            with open(self.keys_file, "w", encoding="utf-8") as f:
                f.write("=== 微信公众号Keys和URLs记录 ===\\n")
                f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
                
    def request(self, flow: http.HTTPFlow) -> None:
        """拦截请求，提取微信相关的Cookie和URL"""
        request = flow.request
        # 拦截文章页或关键接口
        if self.is_wechat_article_url(request.pretty_url) or self.is_wechat_important_api(request.pretty_url):
            self.save_keys_and_url(request)
            
    def is_wechat_article_url(self, url: str) -> bool:
        """判断是否为公众号文章页链接"""
        pattern = r'^https?://mp\\.weixin\\.qq\\.com/s\\?.*__biz='
        return bool(re.match(pattern, url))

    def is_wechat_important_api(self, url: str) -> bool:
        """关键接口: mp/getappmsgext 等，用于携带 appmsg_token/cookie 等"""
        return bool(re.search(r'^https?://mp\\.weixin\\.qq\\.com/mp/getappmsgext', url))
        
    def save_keys_and_url(self, request):
        """保存Cookie、URL和关键Headers"""
        # 过滤掉jsmonitor等监控请求
        if "jsmonitor" in request.pretty_url:
            return
            
        # URL去重检查
        if request.pretty_url in self.saved_urls:
            return
            
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 提取Cookie
        cookies_string = ""
        if request.cookies:
            cookie_parts = []
            key_cookies = ["wxuin", "appmsg_token", "pass_ticket", "wap_sid2"]
            
            for cookie_name, cookie_value in request.cookies.items():
                if any(key in cookie_name.lower() for key in key_cookies) or len(cookie_value) > 20:
                    cookie_parts.append(f"{cookie_name}={cookie_value}")
                    
            if cookie_parts:
                cookies_string = "; ".join(cookie_parts)
                
        # 提取关键请求头
        key_headers = {}
        important_headers = [
            'x-wechat-key', 'x-wechat-uin', 'exportkey',
            'user-agent', 'accept', 'accept-language',
            'cache-control', 'sec-fetch-site', 'sec-fetch-mode',
            'sec-fetch-dest', 'priority'
        ]
        
        for header_name in important_headers:
            if header_name in request.headers:
                key_headers[header_name] = request.headers[header_name]
                
        # 如果没有cookie或已记录，跳过
        if not cookies_string or cookies_string in self.saved_cookies:
            return
            
        # 添加到已保存集合
        self.saved_urls.add(request.pretty_url)
        self.saved_cookies.add(cookies_string)
        
        # 保存到文件
        with open(self.keys_file, "a", encoding="utf-8") as f:
            f.write(f"{'='*60}\\n")
            f.write(f"time: {timestamp}\\n")
            f.write(f"allurl: {request.pretty_url}\\n")
            f.write(f"Cookies: {cookies_string}\\n")
            
            if key_headers:
                f.write("Headers:\\n")
                for header_name, header_value in key_headers.items():
                    f.write(f"  {header_name}: {header_value}\\n")
                    
            f.write("\\n")
            
        print(f"✅ 已捕获微信公众号文章: {request.pretty_url}")
        print(f"📝 数据已保存到: {self.keys_file.absolute()}")

addons = [WechatCaptureAddon()]
'''
    
    addon_path.write_text(addon_code, encoding='utf-8')
    return addon_path

MITMPROXY_DIR = Path(os.path.expandvars(r"%USERPROFILE%")) / ".mitmproxy"


def main():
    global process, ARGS
    ARGS = parse_args()

    ensure_mitm_exists()

    # 端口优先级: --port > 环境变量 MITM_PORT > 自动扫描
    env_port = os.environ.get('MITM_PORT')
    if ARGS.port:
        # 校验端口是否可用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", ARGS.port)) == 0:
                print(f"[FATAL] 指定端口 {ARGS.port} 已被占用")
                return
        port = ARGS.port
    elif env_port and env_port.isdigit():
        p = int(env_port)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) == 0:
                print(f"[FATAL] 环境端口 {p} 已被占用")
                return
        port = p
    else:
        port = find_free_port()

    cmd = build_command(ARGS, port)
    print("========== MITMPROXY 抓包 ==========")
    print(f"[INFO] 启动命令: {' '.join(cmd)}")
    print(f"[INFO] 监听端口: {port}")
    print("[HINT] 请在目标应用/浏览器中设置 HTTP/HTTPS 代理: 127.0.0.1:" + str(port))
    print(f"[INFO] 微信数据将保存到: {wechat_keys_file.absolute()}")
    print("[HINT] 访问微信公众号文章页面进行抓包 (https://mp.weixin.qq.com/s?...)")
    if ARGS.web:
        print("[HINT] 打开浏览器面板 (若端口空闲) 例如: http://127.0.0.1:8081  或控制台输出提示的 URL")

    try:
        process = subprocess.Popen(cmd)
        print(f"[INFO] 进程 PID: {process.pid}")
    except FileNotFoundError:
        print("[FATAL] 未找到 mitmproxy 可执行文件 (mitmweb/mitmdump)")
        return
    except Exception as e:
        print(f"[FATAL] 启动失败: {e}")
        return

    # 设置信号处理
    signal.signal(signal.SIGINT, graceful_exit)
    if hasattr(signal, 'SIGTERM'):
        try:
            signal.signal(signal.SIGTERM, graceful_exit)
        except Exception:
            pass

    print("[READY] 已启动, 按 Ctrl + C 结束并生成摘要 (若启用)")

    try:
        while True:
            if process.poll() is not None:
                print(f"\n[ERROR] mitmproxy 进程已退出 code={process.returncode}")
                break
            time.sleep(2)
    finally:
        graceful_exit()


if __name__ == '__main__':
    main()
