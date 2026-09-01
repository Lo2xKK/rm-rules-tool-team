# RM 规则检索工具（rm-rules-tool）

一个方便**搜索 + 对比** RoboMaster 官方规则的本地 Web 工具。以官方 PDF 为准，把规则手册、制作规范、参赛手册变成可全文搜索、可条款级对比的本地数据库，浏览器打开 `localhost` 就能用。

> 解决的核心痛点：PDF 阅读器搜索只能"点下一个逐个跳"，本工具**搜一次把所有命中条款一次性铺开**，还能**条款级对比任意两个版本**，一眼看出本赛季改了什么。

## 功能

- **全文搜索**：一次列出所有命中条款，关键词高亮 + 条款号 + 出处（版本/页码），不用逐个跳。
- **版本对比**：任意两个版本条款级 diff，改动处红（删除）绿（新增）高亮，摘要统计新增/修改/删除/未变。
- **检查更新**：一键检查本地与官方是否同步最新，增量下载新版本（无需定时任务，按需手动查）。
- **文档类型切换**：规则手册 / 制作规范 / 参赛手册 × 超级对抗赛（RMUC）/ 高校联盟赛（RMUL）。

## 快速开始

### 1. 环境要求

- Python 3.11+
- 能访问 RoboMaster 官方社区（首次建库需联网下载 PDF）

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活（Windows）
.venv\Scripts\activate
# 或 Linux/macOS
source .venv/bin/activate

# 安装依赖（国内建议用清华镜像加速）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Playwright 浏览器内核（国内用镜像加速）
PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright playwright install chromium
```

### 3. 首次建库（下载官方规则）

```bash
# 只下载 RMUC 规则手册中文版（对比功能核心数据，约 240MB）
python download.py --rules-cn

# 或下载所有中文版文档（规则手册 + 制作规范 + 参赛手册）
python download.py --zh-only

# 或下载全部文档（含英文版）
python download.py
```

### 4. 启动

```bash
python server.py
```

浏览器打开 <http://127.0.0.1:8000/> 即可使用。

Windows 用户也可直接双击 `start.bat` 一键启动。

## 数据获取原理

官方规则发布在 RoboMaster 社区 wiki（正文由 JS 异步加载，故用 Playwright 渲染真实浏览器抓取）：

- RMUC 超级对抗赛：`bbs.robomaster.com/wiki/20204847/809871`
- RMUL 高校联盟赛：`bbs.robomaster.com/wiki/20204847/809872`

数据流：`抓官方页面 → 解析版本清单 → 下载 PDF（CDN 直链） → PyMuPDF 抽文本 → 条款切分 → SQLite 入库 → 搜索/对比`。

"检查更新"按钮即复用了这条链路：实时抓官方清单，与本地已入库版本对比，报告新增/更新，一键增量下载。

## 项目结构

```
rm-rules-tool/
├── crawler.py        # 爬虫：渲染官方页面 + 解析版本清单
├── updater.py        # 检查更新 + 下载入库（版本比较、去重）
├── parser.py         # PDF → 条款结构化入库（PyMuPDF）
├── compare.py        # 版本对比：条款级对齐 + 字符级 diff
├── search.py         # 关键词检索（支持文档类型/赛事过滤）
├── server.py         # FastAPI Web 服务 + 单页前端
├── download.py       # CLI 建库脚本
├── start.bat         # Windows 一键启动
├── requirements.txt  # 依赖清单
└── data/             # 下载的 PDF + SQLite（不提交到仓库）
```

## 技术栈

Python / FastAPI（单页前端）/ Playwright（渲染爬虫）/ BeautifulSoup（解析）/ PyMuPDF（PDF 解析）/ SQLite（存储）。核心功能纯本地，不依赖任何大模型或外部 API。

## 免责声明

- 本项目**只提供代码（导入脚本）**，不包含、不发布任何 RoboMaster 官方文档的提取文本或 PDF。使用者需自行从官方渠道下载规则文件。
- 官方规则手册 PDF 等文档版权归大疆（DJI）所有，请仅用于个人学习、战队备赛等合理用途。
- 规则内容以官方最新发布为准，本项目解析结果仅供参考。

## License

[MIT License](LICENSE)
