# WeChat Spider - 微信公众号爬虫系统

## 项目简介

WeChat Spider 是一个基于 Python 开发的自动化微信公众号爬虫系统，主要用于爬取公众号文章、阅读数、评论等数据。该项目采用模块化架构，支持代理管理、数据库存储和用户界面操作，适用于数据分析、市场研究等领域。

## 功能特性

- **自动化爬取**：支持定时和批量爬取微信公众号数据
- **代理管理**：内置代理池和 Cookie 管理，应对反爬虫机制
- **数据存储**：支持关系型数据库存储和 Excel 导出
- **用户界面**：提供浏览器自动化和 Excel 驱动的界面
- **模块化设计**：易于扩展和维护

## 项目结构

### 根目录文件

- `main.py`：项目主入口
- `loop_crawler.py`：循环爬虫脚本
- `check_database.py`：数据库检查工具
- `requirements.txt`：Python 依赖列表
- `technical_plan.md`：技术计划文档
- `fx_*.sql`：数据库表结构脚本
- `logs.txt` / `test.logs`：运行日志
- `target_articles.xlsx`：目标文章配置

### 核心模块

- **config/**：配置管理（config_manager.py, config.yaml）
- **data/**：数据存储（JSON/Excel 文件）
- **src/config/**：凭据管理（credential.py）
- **src/core/**：核心逻辑（automated_crawler.py, enhanced_proxy_manager.py 等）
- **src/crawler/**：爬虫实现（batch_readnum_spider.py, enhanced_wx_crawler.py）
- **src/database/**：数据库管理（database_manager.py, account_status_manager.py 等）
- **src/proxy/**：代理管理（proxy_manager.py, cookie_extractor.py 等）
- **src/ui/**：用户界面（excel_auto_crawler.py, wechat_browser_automation.py）
- **src/utils/**：工具函数（utils.py）

## 运行命令

- python loop_crawler.py --once 单次批量爬取
- python loop_crawler.py --interval 1800 循环批量爬取 每次循环间隔 1800 秒
- python .\loop_crawler.py --excel .\test1.xlsx --once 单次指定文件批量爬取

## 安装与使用

### 环境要求

- Python 3.8+
- MySQL 或其他关系型数据库

### 安装步骤

1. 克隆项目：`git clone <repository-url>`
2. 安装依赖：`pip install -r requirements.txt`
3. 配置数据库：运行 `fx_*.sql` 创建表结构
4. 修改 `config/config.yaml` 配置参数
5. 运行主程序：`python main.py` 单次爬取

### 使用说明

- 编辑 `target_articles.xlsx` 添加目标公众号
- 运行 `loop_crawler.py` 开始批量爬取
- 查看 `logs.txt` 监控运行状态

## 注意事项

- 请遵守微信使用条款，避免过度爬取
- 定期更新代理和 Cookie 以维持稳定性
- 数据仅供研究使用，不得用于商业目的

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

MIT License
