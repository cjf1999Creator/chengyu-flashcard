#!/bin/bash
# 成语积累 Web 应用部署脚本
# 用法: bash deploy.sh
# 首次部署时需要输入 SSH 密码

SERVER="root@45.62.104.118"
REMOTE_DIR="/opt/chengyu-web"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 成语积累 Web 应用部署 ==="
echo "目标服务器: $SERVER"
echo "本地目录: $LOCAL_DIR"
echo ""

# 1. 上传文件
echo ">>> 上传文件到服务器..."
ssh $SERVER "mkdir -p $REMOTE_DIR/data $REMOTE_DIR/static $REMOTE_DIR/templates"
scp "$LOCAL_DIR/app.py" "$SERVER:$REMOTE_DIR/"
scp "$LOCAL_DIR/parser.py" "$SERVER:$REMOTE_DIR/"
scp "$LOCAL_DIR/storage.py" "$SERVER:$REMOTE_DIR/"
scp "$LOCAL_DIR/requirements.txt" "$SERVER:$REMOTE_DIR/"
scp "$LOCAL_DIR/data/idioms.json" "$SERVER:$REMOTE_DIR/data/"
scp "$LOCAL_DIR/static/style.css" "$SERVER:$REMOTE_DIR/static/"
scp "$LOCAL_DIR/static/app.js" "$SERVER:$REMOTE_DIR/static/"
scp "$LOCAL_DIR/templates/index.html" "$SERVER:$REMOTE_DIR/templates/"
echo "  文件上传完成"

# 2. 安装依赖
echo ">>> 安装 Python 依赖..."
ssh $SERVER "command -v python3 || (apt update && apt install -y python3 python3-pip python3-venv)"
ssh $SERVER "cd $REMOTE_DIR && [ -d venv ] || python3 -m venv venv"
ssh $SERVER "cd $REMOTE_DIR && venv/bin/pip install flask gunicorn"
echo "  依赖安装完成"

# 3. 创建 systemd 服务
echo ">>> 配置 systemd 服务..."
ssh $SERVER "cat > /etc/systemd/system/chengyu-web.service << 'EOF'
[Unit]
Description=Chengyu Flashcard Web App
After=network.target

[Service]
User=root
WorkingDirectory=$REMOTE_DIR
ExecStart=$REMOTE_DIR/venv/bin/gunicorn --bind 0.0.0.0:80 --workers 2 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF"
echo "  服务配置完成"

# 4. 启动服务
echo ">>> 启动服务..."
ssh $SERVER "systemctl daemon-reload && systemctl enable chengyu-web && systemctl restart chengyu-web"
echo ""

# 5. 验证
echo ">>> 验证部署..."
sleep 2
HTTP_CODE=$(ssh $SERVER "curl -s -o /dev/null -w '%{http_code}' http://localhost:80/ 2>/dev/null || echo '000'")
IDIOM_COUNT=$(ssh $SERVER "curl -s http://localhost:80/api/idioms 2>/dev/null | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null || echo '?'")

echo ""
echo "=== 部署完成 ==="
echo "HTTP 状态码: $HTTP_CODE"
echo "成语数量: $IDIOM_COUNT"
echo "访问地址: http://45.62.104.118/"
