#!/bin/bash
# RM 规则检索 · 队内部署脚本（Ubuntu 22.04）
#
# 用法（在服务器上以 root 运行）：
#   bash deploy.sh
# 或指定访问密码（跳过交互输入）：
#   ACCESS_PASSWORD=你的密码 bash deploy.sh
#
# 完成后会自动：装依赖 → clone 代码 → 下载规则数据 → 加访问密码 → 注册开机自启。
set -e

APP_DIR="/opt/rm-rules-tool"
REPO_URL="https://github.com/Lo2xKK/rm-rules-tool-team.git"
ENV_FILE="/etc/rm-rules-tool.env"
SERVICE_FILE="/etc/systemd/system/rm-rules-tool.service"

echo "==> [1/6] 更新系统并安装基础依赖"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl

echo "==> [2/6] 拉取代码"
if [ -d "$APP_DIR/.git" ]; then
  echo "    已存在，执行 git pull 更新"
  git -C "$APP_DIR" pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> [3/6] 创建虚拟环境并安装依赖（清华镜像）"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
.venv/bin/pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "==> [4/6] 安装 Playwright chromium（npmmirror 镜像 + 系统依赖）"
PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright .venv/bin/playwright install chromium
apt-get install -y -qq \
  libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
  libasound2 libpango-1.0-0 libcairo2 libatspi2.0-0

echo "==> [5/6] 下载规则数据（首次建库，约 240MB，视网络几分钟）"
.venv/bin/python download.py --rules-cn || echo "    警告：数据下载失败，可稍后重跑本脚本或手动 .venv/bin/python download.py --rules-cn"

echo "==> [6/6] 配置访问密码 + 注册开机自启"
if [ -z "$ACCESS_PASSWORD" ]; then
  read -r -s -p "请输入队友访问密码: " ACCESS_PASSWORD
  echo
fi
cat > "$ENV_FILE" <<EOF
ACCESS_PASSWORD=$ACCESS_PASSWORD
HOST=0.0.0.0
PORT=8000
EOF
chmod 600 "$ENV_FILE"

cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=RM Rules Tool
After=network.target

[Service]
WorkingDirectory=/opt/rm-rules-tool
EnvironmentFile=/etc/rm-rules-tool.env
ExecStart=/opt/rm-rules-tool/.venv/bin/python server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now rm-rules-tool

IP=$(curl -s --noproxy '*' ifconfig.me 2>/dev/null || echo "你的公网IP")
echo ""
echo "=============================================="
echo " 部署完成！"
echo " 队友访问地址: http://$IP:8000"
echo " 访问密码:     $ACCESS_PASSWORD"
echo "=============================================="
echo " 常用命令："
echo "   查看状态: systemctl status rm-rules-tool"
echo "   查看日志: journalctl -u rm-rules-tool -f"
echo "   重启服务: systemctl restart rm-rules-tool"
echo "   更新代码: cd $APP_DIR && git pull && systemctl restart rm-rules-tool"
