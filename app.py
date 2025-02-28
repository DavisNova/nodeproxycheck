from flask import Flask, request, jsonify, send_file
import os
import logging
from werkzeug.utils import secure_filename
import threading
import time
from proxy_tester import process_excel_file, total_count, current_count, success_count, failure_count, log_messages, set_concurrency
import signal
import datetime
import subprocess
from pathlib import Path

# 创建Flask应用
app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/proxy_tester.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局变量
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = '.'
current_test = None
is_testing = False
progress = 0

# 确保必要的目录存在
for folder in ['uploads', 'static', 'logs']:
    os.makedirs(folder, exist_ok=True)

def check_curl_installed():
    """检查curl是否已安装"""
    try:
        subprocess.run(['curl', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

class TestThread(threading.Thread):
    """测试线程类"""
    def __init__(self, file_path, concurrency):
        super().__init__()
        self.file_path = file_path
        self.concurrency = concurrency
        self.stopped = False

    def run(self):
        """运行测试"""
        global is_testing, failure_count
        try:
            if not check_curl_installed():
                log_messages.append({
                    'time': datetime.datetime.now().strftime("%H:%M:%S"),
                    'message': "错误: curl 命令未安装，请先安装 curl"
                })
                failure_count += 1
                return

            set_concurrency(self.concurrency)  # 设置并发数
            process_excel_file(self.file_path)
        except Exception as e:
            logger.error(f"测试过程出错: {str(e)}")
            log_messages.append({
                'time': datetime.datetime.now().strftime("%H:%M:%S"),
                'message': f"测试过程出错: {str(e)}"
            })
            failure_count += 1
        finally:
            is_testing = False

    def stop(self):
        """停止测试"""
        self.stopped = True
        os.kill(os.getpid(), signal.SIGINT)

@app.route('/')
def index():
    """主页"""
    return app.send_static_file('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    global current_test, is_testing, failure_count, success_count
    
    # 重置计数器
    failure_count = 0
    success_count = 0
    
    if 'file' not in request.files:
        return jsonify({'error': '没有文件上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if not file.filename.endswith(('.xls', '.xlsx')):
        return jsonify({'error': '只支持Excel文件'}), 400

    try:
        concurrency = int(request.form.get('concurrency', '50'))
        if not 1 <= concurrency <= 500:
            return jsonify({'error': '并发数必须在1-500之间'}), 400
    except ValueError:
        return jsonify({'error': '无效的并发数'}), 400

    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # 确保文件权限正确
        os.chmod(file_path, 0o666)
        
        current_test = TestThread(file_path, concurrency)
        is_testing = True
        current_test.start()
        
        logger.info(f"开始测试文件: {filename}, 并发数: {concurrency}")
        return jsonify({'message': '文件上传成功，开始测试'})
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        failure_count += 1
        return jsonify({'error': f'文件上传失败: {str(e)}'}), 500

@app.route('/status')
def get_status():
    """获取测试状态"""
    current_progress = 0
    if total_count > 0:
        current_progress = min(100, int((current_count / total_count) * 100))
    
    return jsonify({
        'is_running': is_testing,
        'progress': current_progress,
        'success_count': success_count,
        'failure_count': failure_count,
        'log_messages': log_messages[-100:] if log_messages else []
    })

@app.route('/stop', methods=['POST'])
def stop_test():
    """停止测试"""
    global current_test, is_testing
    if current_test and is_testing:
        current_test.stop()
        is_testing = False
        logger.info("测试已手动停止")
    return jsonify({'message': '测试已停止'})

@app.route('/download')
def download_result():
    """下载测试结果"""
    try:
        result_files = []
        for file in os.listdir(RESULT_FOLDER):
            if '_结果_' in file and file.endswith('.xlsx'):
                full_path = os.path.join(RESULT_FOLDER, file)
                result_files.append((full_path, os.path.getmtime(full_path)))
        
        if not result_files:
            logger.warning("没有找到结果文件")
            return jsonify({'error': '没有可用的结果文件'}), 404
        
        latest_file, _ = max(result_files, key=lambda x: x[1])
        
        if not os.path.exists(latest_file):
            logger.error(f"结果文件不存在: {latest_file}")
            return jsonify({'error': '文件不存在'}), 404
            
        try:
            filename = os.path.basename(latest_file)
            logger.info(f"下载结果文件: {filename}")
            response = send_file(
                latest_file,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            return response
        except Exception as e:
            logger.error(f'文件下载失败: {str(e)}')
            return jsonify({'error': f'文件下载失败: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f'系统错误: {str(e)}')
        return jsonify({'error': f'系统错误: {str(e)}'}), 500

@app.errorhandler(404)
def not_found_error(error):
    """404错误处理"""
    return jsonify({'error': '页面不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({'error': '服务器内部错误'}), 500

if __name__ == '__main__':
    # 设置日志
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # 启动应用
    app.run(host='0.0.0.0', port=5000, debug=False) 