# 微信公众号爬虫

一个功能强大的微信公众号文章批量抓取工具，支持全自动化运行、多公众号处理、阅读量获取等功能。专为Windows环境设计，可配合任务计划程序实现定时自动抓取。
<hr>

>✨现已增加分支：[loop](https://github.com/RichardQt/AutoWechatCrawler/tree/loop) --实现循环爬虫
> 重要：暂时只支持3.9.12版本的微信！！！！！

## 📚 文档导航

- **[快速开始](QUICK_START.md)** - 5分钟快速上手指南
- **[常见问题](FAQ.md)** - 详细的问题解答和故障排除
- **[更新日志](CHANGELOG.md)** - 版本更新历史和变更记录
- **[SSL绕过说明](SSL_BYPASS_README.md)** - SSL证书错误自动处理功能
- **[任务计划配置](Windows任务计划程序配置说明.md)** - Windows定时任务配置指南

## 🌟 主要特性

### 🤖 全自动化运行
- **零人工干预**：配合Windows任务计划程序，实现完全自动化运行
- **智能UI自动化**：自动打开微信PC版，发送链接并触发抓取
- **SSL错误自动绕过**：智能检测并自动处理SSL证书错误页面
- **代理自动管理**：自动设置和清理系统代理，无需手动配置

### 📊 多公众号批量处理
- **Excel批量导入**：从Excel文件读取多个公众号链接
- **并发处理**：支持多个公众号的顺序自动处理
- **结果汇总**：自动汇总所有公众号的抓取结果
- **失败重试**：智能重试机制，提高抓取成功率

### 🔍 数据抓取功能
- **文章列表抓取**：获取公众号历史文章列表
- **阅读量获取**：精确获取文章阅读量、点赞数等数据
- **文章内容抓取**：可选择性获取文章完整内容
- **多格式导出**：支持Excel、JSON等多种格式导出

### 🛡️ 安全与稳定性
- **Cookie自动获取**：通过mitmproxy自动抓取有效Cookie
- **反爬虫机制**：内置延迟、随机化等反检测机制
- **错误恢复**：完善的错误处理和恢复机制
- **日志记录**：详细的操作日志，便于问题排查

## 📁 项目结构

```
wechat_spider_gitlab/
├── main_enhanced.py              # 主程序入口（全自动化版本）
├── automated_crawler.py          # 全自动化爬虫控制器
├── batch_readnum_spider.py       # 批量阅读量抓取器
├── excel_auto_crawler.py         # Excel自动化爬虫
├── enhanced_wx_crawler.py        # 增强版微信爬虫
├── wechat_browser_automation.py  # 微信浏览器UI自动化
├── cookie_extractor.py           # Cookie抓取器（mitmproxy插件）
├── read_cookie.py                # Cookie读取和管理
├── proxy_manager.py              # 代理管理器
├── enhanced_proxy_manager.py     # 增强代理管理器
├── utils.py                      # 工具函数
├── credential.py                 # 凭证管理
├── requirements.txt              # 依赖包列表
├── target_articles.xlsx          # 目标文章Excel模板
├── run_auto_crawler.bat          # Windows批处理启动脚本
├── run_auto_crawler.ps1          # PowerShell启动脚本
├── chromedriver.exe              # Chrome驱动程序
├── data/                         # 数据输出目录
│   └── readnum_batch/           # 批量抓取结果
├── logs/                        # 日志文件目录
├── SSL_BYPASS_README.md         # SSL绕过功能说明
├── Windows任务计划程序配置说明.md # 任务计划配置说明
├── QUICK_START.md               # 快速开始指南
├── FAQ.md                       # 常见问题解答
└── CHANGELOG.md                 # 更新日志
```

## 🚀 快速开始

### ⚡ 三步快速部署

```bash
# 1. 下载项目
git clone https://github.com/your-repo/wechat_spider2.git
cd wechat_spider2

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行程序
python main_enhanced.py --auto
```

### 📋 环境要求

- Windows 10/11 + Python 3.8+
- 微信PC版（已安装并登录）
- Chrome/Edge浏览器

### 📖 详细教程

**新手用户请查看**: [📚 快速开始指南](QUICK_START.md) - 包含详细的安装配置步骤

**遇到问题请查看**: [❓ 常见问题解答](FAQ.md) - 详细的故障排除指南

## 📋 使用方法

### 基本使用

1. **准备目标文章列表**
   - 打开 `target_articles.xlsx`
   - 在 `文章链接` 列填入微信公众号文章链接
   - 在 `公众号名称` 列填入对应的公众号名称

2. **运行自动化抓取**
```bash
python main_enhanced.py --auto
```

3. **查看结果**
   - 抓取结果保存在 `data/readnum_batch/` 目录
   - 日志文件保存在 `logs/` 目录

### 高级配置

#### 自定义Excel文件路径
```python
from automated_crawler import AutomatedCrawler

crawler = AutomatedCrawler(excel_path="custom_articles.xlsx")
crawler.run_full_automation()
```

#### 配置抓取参数
```python
# 在 batch_readnum_spider.py 中修改
class BatchReadnumSpider:
    def __init__(self, auth_info=None):
        self.delay_range = (10, 20)  # 请求间隔（秒）
        self.max_retries = 3         # 最大重试次数
        self.timeout = 30            # 请求超时时间
```

## 🔧 Windows任务计划程序配置

为了实现定时自动抓取，可以配置Windows任务计划程序：

1. **打开任务计划程序**：`Win + R` → `taskschd.msc`

2. **创建基本任务**：
   - 任务名称：`微信公众号自动爬取`
   - 触发器：每天凌晨2:00执行
   - 操作：启动程序 `run_auto_crawler.bat`

3. **高级设置**：
   - ✅ 不管用户是否登录都要运行
   - ✅ 使用最高权限运行
   - ✅ 允许按需运行任务

详细配置说明请参考：[Windows任务计划程序配置说明.md](Windows任务计划程序配置说明.md)

## 📊 输出格式

### Excel格式输出
```
文章标题 | 发布时间 | 阅读量 | 点赞数 | 在看数 | 文章链接 | 公众号名称
```

### JSON格式输出
```json
{
  "title": "文章标题",
  "publish_time": "2024-01-01 12:00:00",
  "read_num": 1000,
  "like_num": 50,
  "share_num": 20,
  "url": "https://mp.weixin.qq.com/s/...",
  "account_name": "公众号名称"
}
```

## 🛠️ 核心功能模块

### 1. 自动化控制器 (AutomatedCrawler)
- 协调整个自动化流程
- 支持多公众号批量处理
- 智能错误处理和重试

### 2. Cookie抓取器 (CookieExtractor)
- 基于mitmproxy的Cookie自动抓取
- 智能过滤和去重
- 自动代理管理

### 3. UI自动化 (WeChatBrowserAutomation)
- 微信PC版UI自动化操作
- SSL错误自动绕过
- 智能页面刷新

### 4. 批量爬虫 (BatchReadnumSpider)
- 高效的批量数据抓取
- 反爬虫机制
- 多格式数据导出

### 5. 代理管理器 (ProxyManager)
- 系统代理自动设置
- 网络状态检测
- 安全清理机制

## 🔍 SSL证书错误自动绕过

项目内置SSL证书错误自动绕过功能，支持：

- **智能检测**：窗口标题、页面文本、地址栏检测
- **自动绕过**：使用 `thisisunsafe` 自动绕过
- **验证机制**：绕过后自动验证是否成功

详细说明请参考：[SSL_BYPASS_README.md](SSL_BYPASS_README.md)

## 📝 日志系统

项目提供详细的日志记录：

- **控制台输出**：实时显示运行状态
- **文件日志**：保存在 `logs/` 目录，按时间戳命名
- **分级日志**：INFO、WARNING、ERROR等不同级别

## ⚠️ 注意事项

1. **合规使用**：请遵守相关法律法规，仅用于学习和研究目的
2. **频率控制**：内置延迟机制，避免过于频繁的请求
3. **账号安全**：注意保护微信账号安全，避免触发风控
4. **网络环境**：确保网络连接稳定，代理设置正确

## 🐛 故障排除

### 常见问题

1. **Cookie获取失败**
   - 检查微信PC版是否正常登录
   - 确认代理设置是否正确
   - 查看mitmproxy是否正常启动

2. **UI自动化失败**
   - 确认微信PC版窗口可见
   - 检查文件传输助手是否可访问
   - 查看是否有其他程序干扰

3. **数据抓取失败**
   - 检查Cookie是否有效
   - 确认文章链接格式正确
   - 查看网络连接状态

### 获取帮助

- 查看详细日志：`logs/` 目录下的日志文件
- 检查配置文件：确认Excel文件格式正确
- 联系技术支持：提供详细的错误日志

## 📄 许可证

本项目仅供学习和研究使用，请遵守相关法律法规。

## 🔧 开发者指南

### 项目架构

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   main_enhanced │───▶│ AutomatedCrawler│───▶│ ExcelAutoCrawler│
│   (程序入口)     │    │  (流程控制器)    │    │  (UI自动化)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ BatchReadnum    │◀───│   ReadCookie    │◀───│WeChatBrowser    │
│ Spider(数据抓取)│    │ (Cookie管理)    │    │Automation(UI)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  ProxyManager   │◀───│ CookieExtractor │    │  SSL Bypass     │
│  (代理管理)     │    │ (mitmproxy插件) │    │  (错误处理)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 核心工作流程

1. **初始化阶段**
   - 读取Excel配置文件
   - 初始化日志系统
   - 检查环境依赖

2. **Cookie获取阶段**
   - 启动mitmproxy代理服务
   - 设置系统代理配置
   - UI自动化触发链接访问
   - 自动抓取有效Cookie

3. **数据抓取阶段**
   - 使用获取的Cookie进行认证
   - 批量抓取文章列表和阅读量
   - 实时保存抓取结果

4. **清理阶段**
   - 关闭代理服务
   - 恢复网络设置
   - 生成抓取报告

### API参考

#### AutomatedCrawler类

```python
class AutomatedCrawler:
    def __init__(self, excel_path="target_articles.xlsx"):
        """初始化自动化爬虫控制器"""

    def run_full_automation(self) -> dict:
        """运行完整的自动化流程"""

    def _get_all_target_urls_from_excel(self) -> list:
        """从Excel读取所有目标URL"""
```

#### BatchReadnumSpider类

```python
class BatchReadnumSpider:
    def __init__(self, auth_info: dict = None):
        """初始化批量阅读量抓取器"""

    def run_batch_crawl(self, target_urls: list) -> list:
        """批量抓取多个公众号"""

    def crawl_single_account(self, biz: str, account_name: str) -> list:
        """抓取单个公众号的所有文章"""
```

#### WeChatBrowserAutomation类

```python
class WeChatBrowserAutomation:
    def send_and_open_latest_link(self, article_url: str,
                                 auto_refresh: bool = True,
                                 refresh_count: int = 3,
                                 cookie_reader=None) -> bool:
        """发送链接并自动打开"""

    def handle_ssl_certificate_error(self) -> bool:
        """处理SSL证书错误"""
```

### 配置文件说明

#### target_articles.xlsx格式

| 列名 | 说明 | 示例 |
|------|------|------|
| 文章链接 | 微信公众号文章完整URL | `https://mp.weixin.qq.com/s/xxx` |
| 公众号名称 | 公众号显示名称 | 科技前沿 |
| 备注 | 可选备注信息 | 重点关注 |

#### 环境变量配置

```bash
# 可选环境变量
WECHAT_SPIDER_LOG_LEVEL=INFO    # 日志级别
WECHAT_SPIDER_PROXY_PORT=8080   # 代理端口
WECHAT_SPIDER_TIMEOUT=30        # 请求超时时间
```



## 📈 性能优化

### 抓取效率优化

1. **并发控制**：合理设置请求间隔，避免被限流
2. **缓存机制**：缓存已抓取的数据，避免重复请求
3. **断点续传**：支持从中断点继续抓取
4. **智能重试**：指数退避重试策略

### 内存优化

1. **流式处理**：大数据量时使用流式处理
2. **及时释放**：及时释放不需要的对象
3. **分批处理**：将大任务分解为小批次

### 网络优化

1. **连接池**：复用HTTP连接
2. **压缩传输**：启用gzip压缩
3. **DNS缓存**：缓存DNS解析结果

## 🔒 安全考虑

### 数据安全

- **敏感信息加密**：Cookie等敏感信息本地加密存储
- **访问控制**：限制文件访问权限
- **日志脱敏**：日志中不记录敏感信息

### 网络安全

- **HTTPS验证**：严格验证SSL证书（生产环境）
- **代理安全**：确保代理服务器安全
- **防火墙配置**：合理配置防火墙规则

### 合规性

- **频率限制**：严格控制请求频率
- **用户协议**：遵守平台用户协议
- **数据使用**：合规使用抓取的数据

## 🚀 部署指南

### 开发环境部署

```bash
# 1. 克隆代码
git clone https://github.com/your-repo/wechat_spider2.git
cd wechat_spider2

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境
cp config.example.py config.py
# 编辑config.py配置文件

# 5. 运行测试
python main_enhanced.py --test
```

### 生产环境部署

1. **服务器配置**
   - Windows Server 2019+
   - 4GB+ RAM
   - 50GB+ 存储空间

2. **依赖安装**
   - Python 3.8+
   - 微信PC版
   - Chrome浏览器

3. **服务配置**
   - 配置Windows服务
   - 设置任务计划程序
   - 配置日志轮转

4. **监控配置**
   - 设置性能监控
   - 配置告警通知
   - 定期健康检查

## 🤝 贡献指南

### 贡献流程

1. **Fork项目**：在GitHub上Fork本项目
2. **创建分支**：`git checkout -b feature/your-feature`
3. **提交代码**：`git commit -m "Add your feature"`
4. **推送分支**：`git push origin feature/your-feature`
5. **创建PR**：在GitHub上创建Pull Request

### 代码规范

- **PEP 8**：遵循Python代码规范
- **类型注解**：使用类型注解提高代码可读性
- **文档字符串**：为函数和类添加详细文档
- **单元测试**：为新功能添加相应测试

### 提交规范

```text
feat: 添加新功能
fix: 修复bug
docs: 更新文档
style: 代码格式调整
refactor: 代码重构
test: 添加测试
chore: 构建过程或辅助工具的变动
```

## 📞 支持与反馈

### 获取帮助

- **GitHub Issues**：[提交Issue](https://github.com/your-repo/wechat_spider2/issues)
- **讨论区**：[GitHub Discussions](https://github.com/your-repo/wechat_spider2/discussions)
- **邮件支持**：`support@example.com`

### 常见问题

查看 [FAQ.md](docs/FAQ.md) 获取常见问题解答。

### 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本更新历史。

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## ⚠️ 免责声明

本工具仅供学习和研究使用，使用者需自行承担使用风险。开发者不承担任何法律责任，请遵守相关法律法规和平台服务条款。

---

**如果这个项目对你有帮助，请给个⭐️支持一下！**
