# RM 规则检索工具（rm-rules-tool）

一个方便**搜索 + 对比** RoboMaster 官方规则的本地 Web 工具。以官方 PDF 为准，把规则手册、制作规范、参赛手册变成可全文搜索、可条款级对比的本地数据库，浏览器打开 `localhost` 就能用。

> 解决的核心痛点：PDF 阅读器搜索只能「点下一个逐个跳」，本工具**搜一次把所有命中条款一次性铺开**，还能**条款级对比任意两个版本（同赛季 / 跨赛季）**，并直接打开原 PDF 对照原文。

## 功能

- **全文搜索**：一次列出所有命中条款，关键词高亮 + 条款号 + 出处（赛季/版本/页码），支持卡片 / 分组 / 表格三种视图；可按赛季筛选 + 同文档多版本过滤。
- **版本对比**（同赛季）：任意两个版本条款级 diff（新增/修改/删除/未变），改动处红绿高亮，支持卡片 / 双栏两种视图；同步展示官方修改日志（Release Notes）；结果区可输入关键词实时过滤。
- **赛季对比**（跨赛季）：任意两个赛季最新规则条款级 diff，结果区可输入关键词实时过滤。
- **PDF 原文查看**：点击任一搜索 / 对比结果卡片，用 PDF.js 内嵌查看原 PDF 原文（含图片、表格、封面等），跳页到该条款所在页。
- **检查更新**：打开页面自动检测；按钮变红（有更新）/ 变绿（已是最新）；点击一键增量下载新版本 PDF 并入库。
- **赛季筛选**：当前支持 2024 / 2025 / 2026 三个赛季，数据来自官方资料站 + wiki。

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
# 下载当前赛季（2026）—— 规则手册 + 制作规范 + 参赛手册全部中文版
python download.py --zh-only

# 或更轻量：只下载 RMUC 规则手册中文版（约 240MB，足以使用核心搜索 / 对比功能）
python download.py --rules-cn

# 或下载当前赛季全部文档（含英文版）
python download.py

# 补全历史赛季：资料站数据源
python download.py --season=2025
python download.py --season=2024
```

> 历史赛季（`--season`）走 `robomaster.com` 资料站 announcement 页面；当前赛季走 bbs wiki。同一赛季内同版本号重复文件自动去重。

### 4. 启动

```bash
python server.py
```

浏览器打开 <http://127.0.0.1:8000/> 即可使用。

Windows 用户也可直接双击 `start.bat` 一键启动。

## 队内部署（私有服务器，多人共享）

想让队友用手机 / 平板 / 电脑浏览器直接访问、无需各自安装，可以部署到一台常开的服务器（云服务器或队里不关的机器）：

1. 把代码推到你的私有 Git 仓库（`data/` 已由 `.gitignore` 排除，不要提交）。
2. 服务器上 clone 代码后运行一键部署脚本：
   ```bash
   bash deploy.sh
   ```
   脚本会自动：装依赖（清华镜像）→ 装 chromium（npmmirror 镜像）→ 下载规则数据 → 交互式设置访问密码 → 注册 systemd 开机自启。
3. 完成后队友访问 `http://服务器IP:8000`，输入访问密码即可使用。

**访问控制**：设置环境变量 `ACCESS_PASSWORD`（或 `config.json` 里的 `access_password`）后，访问需先登录；不设置则完全放行（适合本地个人使用）。

**局域网直连**（不部署公网服务器、仅队内同一网络使用）：启动时加 `HOST=0.0.0.0`，队友访问 `http://服务器内网IP:8000` 即可。

**首次建库**：若数据为空，打开首页会自动显示「一键下载规则数据」引导，点击即可在网页内完成下载，无需命令行。

## 数据获取原理

官方规则分布在两个数据源：

| 数据源 | 用途 | URL |
|---|---|---|
| bbs 官方 wiki | 当前赛季（2026 RMUC / RMUL） | `bbs.robomaster.com/wiki/20204847/809871`、`809871` |
| robomaster.com 资料站 | 历史赛季（2024 / 2025） | `robomaster.com/zh-CN/resource/pages/announcement/{id}` |
| 总入口 | 发现各赛季 announcement 页面 | `robomaster.com/zh-CN/resource/announcement/competition` |

数据流：`抓官方页面（Playwright 渲染，正文 JS 异步加载） → 解析版本清单 → 下载 PDF（CDN 直链） → PyMuPDF 抽文本 → TOC 切分条款 → SQLite 入库 → 搜索 / 对比`。

「检查更新」按钮即复用了这条链路：实时抓官方清单，与本地已入库版本对比，报告新增 / 更新，一键增量下载。

## 项目结构

```
rm-rules-tool/
├── crawler.py         # 爬虫：渲染官方页面 + 解析版本清单（含 bbs wiki 与 announcement 资料站）
├── updater.py         # 检查更新 + 下载入库（版本比较、去重）
├── parser.py          # PDF → 条款结构化入库（PyMuPDF）
├── compare.py         # 版本对比 + 赛季对比：条款级对齐 + 字符级 diff
├── release_notes.py   # 提取官方修改日志（Release Notes）
├── search.py          # 关键词检索（支持赛季 / 文档类型 / 多版本过滤）
├── server.py          # FastAPI Web 服务 + 单页前端（三 tab：搜索 / 版本对比 / 赛季对比）
├── download.py        # CLI 建库脚本（--season=YYYY 接历史赛季）
├── start.bat          # Windows 一键启动
├── requirements.txt   # 依赖清单
├── static/pdfjs/      # PDF.js 查看器（离线版，含 worker）
├── tests/             # 端到端回归测试（Playwright）
└── data/              # 下载的 PDF + SQLite（不提交到仓库，见 .gitignore）
```

## 技术栈

Python 3.11+ / FastAPI + Uvicorn / Playwright（渲染爬虫）/ BeautifulSoup + lxml（解析）/ PyMuPDF（PDF 解析）/ SQLite（存储）/ **PDF.js**（前端内嵌 PDF 阅读器，纯静态，Apache-2.0）。核心功能纯本地，不依赖任何大模型或外部 API。

## 免责声明

- 本项目**只提供代码（导入脚本）**，不包含、不发布任何 RoboMaster 官方文档的提取文本或 PDF。使用者需自行从官方渠道下载规则文件。
- 官方规则手册 PDF 等文档版权归大疆（DJI）所有，请仅用于个人学习、战队备赛等合理用途。
- 规则内容以官方最新发布为准，本项目解析结果仅供参考。

## License

[MIT License](LICENSE)