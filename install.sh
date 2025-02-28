#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 输出带颜色的信息函数
info() {
    echo -e "${GREEN}[INFO] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    error "请使用root用户运行此脚本"
    exit 1
fi

# 设置安装目录
INSTALL_DIR="/opt/proxy_tester"
GITHUB_REPO="https://github.com/DavisNova/nodeproxycheck.git"

# 1. 安装系统依赖
info "正在安装系统依赖..."
if [ -f /etc/debian_version ]; then
    # Debian/Ubuntu系统
    apt-get update
    apt-get install -y python3 python3-pip curl git
elif [ -f /etc/redhat-release ]; then
    # CentOS/RHEL系统
    yum update -y
    yum install -y python3 python3-pip curl git
else
    error "不支持的操作系统"
    exit 1
fi

# 2. 创建安装目录
info "创建安装目录..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# 3. 克隆代码仓库
info "克隆代码仓库..."
if [ -d "$INSTALL_DIR/.git" ]; then
    info "代码仓库已存在，正在更新..."
    git pull
else
    git clone $GITHUB_REPO .
fi

# 4. 创建Python虚拟环境
info "创建Python虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 5. 安装Python依赖
info "安装Python依赖..."
pip install -r requirements.txt

# 6. 创建必要的目录
info "创建必要的目录..."
mkdir -p $INSTALL_DIR/{uploads,logs,static}
chmod 777 $INSTALL_DIR/{uploads,logs}

# 7. 创建systemd服务文件
info "创建systemd服务..."
cat > /etc/systemd/system/proxy_tester.service << EOL
[Unit]
Description=Proxy Tester Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOL

# 8. 重新加载systemd配置
info "重新加载systemd配置..."
systemctl daemon-reload
systemctl enable proxy_tester
systemctl start proxy_tester

# 9. 检查服务状态
info "检查服务状态..."
if systemctl is-active --quiet proxy_tester; then
    info "服务已成功启动!"
    info "您现在可以通过以下地址访问系统："
    echo -e "${GREEN}http://$(hostname -I | cut -d' ' -f1):5000${NC}"
else
    error "服务启动失败，请检查日志："
    echo "journalctl -u proxy_tester -n 50"
fi

# 10. 显示使用说明
info "安装完成！"
echo -e "
${GREEN}使用说明：${NC}
1. 访问系统：http://服务器IP:5000
2. 查看服务状态：systemctl status proxy_tester
3. 查看日志：tail -f $INSTALL_DIR/logs/proxy_tester.log
4. 重启服务：systemctl restart proxy_tester
5. 停止服务：systemctl stop proxy_tester

${YELLOW}注意事项：${NC}
- 上传的Excel文件必须包含至少5列数据
- 第4列(D列)必须是代理账号
- 第5列(E列)必须是代理密码
- 建议单次测试数据不超过1000条
" 