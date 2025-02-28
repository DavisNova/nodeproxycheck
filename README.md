# 代理测试系统

一个基于Flask的代理测试系统，用于批量测试代理服务器的可用性。

## 快速安装

### 方法一：使用安装脚本（推荐）

```bash
# 1. 下载安装脚本
wget https://raw.githubusercontent.com/DavisNova/nodeproxycheck/main/install.sh

# 2. 添加执行权限
chmod +x install.sh

# 3. 运行安装脚本
sudo ./install.sh
```

安装脚本会自动：
- 安装所需的系统依赖
- 克隆代码仓库
- 创建Python虚拟环境
- 安装Python依赖
- 配置并启动服务

### 方法二：手动安装

1. 克隆代码仓库：
```bash
git clone https://github.com/DavisNova/nodeproxycheck.git
cd nodeproxycheck
```

2. 安装系统依赖：
```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y python3 python3-pip curl

# CentOS/RHEL
sudo yum update -y
sudo yum install -y python3 python3-pip curl
```

3. 安装Python依赖：
```bash
pip install -r requirements.txt
```

4. 运行服务：
```bash
python app.py
```

## 项目结构
```
proxy_tester/
├── app.py              # Flask主应用程序
├── proxy_tester.py     # 代理测试核心逻辑
├── static/            # 静态文件目录
│   └── index.html     # 前端页面
├── uploads/           # 上传文件目录
├── logs/             # 日志目录
├── install.sh        # 安装脚本
└── README.md         # 项目说明文档
```

## 功能特点

- 支持Excel文件批量导入代理账号
- 支持并发测试（1-500线程可配置）
- 实时显示测试进度和结果
- 自动生成测试报告
- 支持测试过程中断和恢复

## 安装要求

- Python 3.6+
- curl
- 其他依赖见requirements.txt

## 使用说明

### Excel文件格式要求

- 必须是Excel文件（.xls或.xlsx格式）
- 文件名不限制，但建议不要包含特殊字符
- 必须包含至少5列数据
- 第4列(D列)必须是代理账号
- 第5列(E列)必须是代理密码
- 其他列的内容不影响测试
- 建议单次测试数据不超过1000条

### 运行服务

1. 开发环境运行：
```bash
python app.py
```

2. 生产环境部署：
```bash
# 创建systemd服务
sudo cp proxy_tester.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable proxy_tester
sudo systemctl start proxy_tester
```

### 访问系统

- 开发环境：http://localhost:5000
- 生产环境：http://服务器IP:5000

## 配置说明

### 系统配置

- 默认端口：5000
- 最大并发数：500
- 超时时间：5秒
- 日志路径：/logs
- 上传文件路径：/uploads

## 常见问题

1. 文件上传失败
   - 检查文件格式是否正确
   - 确保文件大小在限制范围内
   - 验证文件权限

2. 测试进度不更新
   - 检查网络连接
   - 查看后台日志
   - 确认服务状态

3. 下载结果失败
   - 确认测试是否完成
   - 检查文件权限
   - 验证存储空间

## 维护说明

### 日志管理

- 日志位置：/logs/proxy_tester.log
- 自动记录测试过程和结果

### 性能优化

- 建议并发数：
  - 数据量<100：使用默认值50
  - 数据量>100：可适当增加，但不超过500

### 安全建议

- 定期更新系统
- 及时清理日志和临时文件
- 控制文件上传大小
- 限制并发数量

## 更新历史

- v1.0.0 (2024-02-28)
  - 初始版本发布
  - 基本功能实现
  - 添加自动安装脚本

## 许可证

MIT License 