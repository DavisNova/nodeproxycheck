#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import pandas as pd
from pathlib import Path
import time
import datetime
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
import platform

# 全局变量
all_results = []  # 存储所有测试结果
current_file = None

# 添加全局变量用于进度更新
total_count = 0
current_count = 0
success_count = 0
failure_count = 0
log_messages = []
concurrency = 50  # 默认并发数

# 根据操作系统设置curl路径
CURL_PATH = 'curl.exe' if platform.system() == 'Windows' else '/usr/bin/curl'

def set_concurrency(value):
    """设置并发数"""
    global concurrency
    concurrency = max(1, min(500, value))  # 确保在1-500范围内

def update_progress(message, is_success=None):
    """更新进度和日志"""
    global current_count, success_count, failure_count, log_messages
    try:
        if is_success is not None:
            if is_success:
                success_count += 1
            else:
                failure_count += 1
        current_count += 1
        log_messages.append({
            'time': datetime.datetime.now().strftime("%H:%M:%S"),
            'message': message
        })
        # 保持日志消息数量在合理范围内
        if len(log_messages) > 1000:  # 增加日志容量
            log_messages = log_messages[-1000:]
    except Exception as e:
        print(f"更新进度时出错: {str(e)}")

def signal_handler(sig, frame):
    """处理Ctrl+C中断"""
    print("\n检测到中断，正在保存结果...")
    save_final_results(current_file)
    sys.exit(0)

def test_proxy(username, password, index):
    """测试单个代理，带5秒超时"""
    if not username or not password:
        return index, False, "失败 - 账号或密码为空", None, None
    
    # 构建curl命令参数列表
    cmd = [
        CURL_PATH,
        '-x', f'socks5://{username}:{password}@120.233.207.183:10093',
        '--connect-timeout', '5',  # 连接超时
        '--max-time', '10',        # 总超时
        '-s',                      # 静默模式
        '-w', '%{http_code},%{time_total},%{speed_download}',  # 获取更多信息
        'ipinfo.io'
    ]
    
    message = f"执行命令 [{index + 1}]: {' '.join(cmd)}"
    update_progress(message)
    
    try:
        start_time = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=15)  # 总超时15秒
            end_time = time.time()
            response_time = end_time - start_time
            
            if process.returncode == 0 and stdout.strip():
                try:
                    # 分离响应内容和统计信息
                    response_parts = stdout.strip().split('\n')
                    if len(response_parts) >= 2:
                        response_data = json.loads('\n'.join(response_parts[:-1]))
                        stats = response_parts[-1].split(',')
                        
                        if 'ip' in response_data:
                            performance_data = {
                                'http_code': stats[0],
                                'response_time': f"{float(stats[1]):.2f}s",
                                'download_speed': f"{float(stats[2])/1024:.2f}KB/s",
                                'total_time': f"{response_time:.2f}s"
                            }
                            
                            success_msg = (
                                f"成功 - "
                                f"代理IP: {response_data['ip']}, "
                                f"响应时间: {performance_data['response_time']}, "
                                f"下载速度: {performance_data['download_speed']}"
                            )
                            update_progress(success_msg, True)
                            return index, True, success_msg, response_data['ip'], performance_data
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    pass
            
            fail_msg = f"失败 - 代理连接失败: {stderr if stderr else '未知错误'}"
            update_progress(fail_msg, False)
            return index, False, fail_msg, None, None
            
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except:
                pass
            timeout_msg = "失败 - 连接超时(15秒)"
            update_progress(timeout_msg, False)
            return index, False, timeout_msg, None, None
            
        finally:
            try:
                process.kill()
            except:
                pass
                
    except Exception as e:
        error_msg = f"失败 - 错误: {str(e)}"
        update_progress(error_msg, False)
        return index, False, error_msg, None, None

def save_final_results(original_file_path):
    """保存最终结果到单个文件"""
    if not all_results:
        return

    try:
        # 使用绝对路径
        save_dir = os.path.dirname(os.path.abspath(original_file_path))
        file_stem = Path(original_file_path).stem
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(save_dir, f"{file_stem}_结果_{current_time}.xlsx")

        # 按原始索引排序
        sorted_results = sorted(all_results, key=lambda x: x['序号'])
        
        # 创建DataFrame并保存
        df = pd.DataFrame(sorted_results)
        
        # 设置列顺序
        columns = [
            '序号', '测试时间', '账号', '密码', '代理服务器', '代理端口',
            '代理IP', '状态', '响应时间', '下载速度', '总耗时', '备注'
        ]
        df = df.reindex(columns=columns)
        
        # 设置Excel格式
        writer = pd.ExcelWriter(result_file, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='测试结果')
        
        # 获取工作表
        worksheet = writer.sheets['测试结果']
        
        # 设置列宽
        for column in worksheet.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
        
        # 保存文件
        writer.close()
        
        # 确保文件权限正确
        os.chmod(result_file, 0o666)
        
        print(f"\n测试完成!")
        print(f"结果文件保存位置: {result_file}")
        print(f"总测试数量: {len(sorted_results)}")
        print(f"成功数量: {len([r for r in sorted_results if r['状态'] == '成功'])}")
        print(f"失败数量: {len([r for r in sorted_results if r['状态'] == '失败'])}")
        
        return result_file
    except Exception as e:
        print(f"保存结果文件时出错: {str(e)}")
        return None

def safe_str(value):
    """安全地将值转换为字符串"""
    try:
        if pd.isna(value):  # 检查是否为NaN
            return ""
        return str(value).strip()
    except:
        return str(value)

def process_batch(batch_data, start_index):
    """处理一批代理"""
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for i, (_, row) in enumerate(batch_data.iterrows()):
            try:
                username = safe_str(row[3])
                password = safe_str(row[4])
                
                if username and password:
                    futures.append((
                        executor.submit(test_proxy, username, password, start_index + i),
                        (username, password, start_index + i)
                    ))
                else:
                    results.append({
                        '序号': start_index + i + 1,
                        '测试时间': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        '账号': username,
                        '密码': password,
                        '代理服务器': '120.233.207.183',
                        '代理端口': '10093',
                        '代理IP': '',
                        '状态': '失败',
                        '响应时间': '',
                        '下载速度': '',
                        '总耗时': '',
                        '备注': '无效的账号或密码'
                    })
                    update_progress(f"跳过无效账号 [{start_index + i + 1}]: {username}", False)
            except Exception as e:
                error_msg = f"数据处理错误: {str(e)}"
                update_progress(error_msg, False)
                results.append({
                    '序号': start_index + i + 1,
                    '测试时间': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '账号': safe_str(row[3]) if row is not None else '',
                    '密码': safe_str(row[4]) if row is not None else '',
                    '代理服务器': '120.233.207.183',
                    '代理端口': '10093',
                    '代理IP': '',
                    '状态': '失败',
                    '响应时间': '',
                    '下载速度': '',
                    '总耗时': '',
                    '备注': error_msg
                })
        
        for future, (username, password, index) in futures:
            try:
                index, success, message, proxy_ip, performance = future.result(timeout=20)
                results.append({
                    '序号': index + 1,
                    '测试时间': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '账号': username,
                    '密码': password,
                    '代理服务器': '120.233.207.183',
                    '代理端口': '10093',
                    '代理IP': proxy_ip if success else '',
                    '状态': '成功' if success else '失败',
                    '响应时间': performance['response_time'] if success and performance else '',
                    '下载速度': performance['download_speed'] if success and performance else '',
                    '总耗时': performance['total_time'] if success and performance else '',
                    '备注': message
                })
            except Exception as e:
                error_msg = f"测试执行错误: {str(e)}"
                update_progress(error_msg, False)
                results.append({
                    '序号': index + 1,
                    '测试时间': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '账号': username,
                    '密码': password,
                    '代理服务器': '120.233.207.183',
                    '代理端口': '10093',
                    '代理IP': '',
                    '状态': '失败',
                    '响应时间': '',
                    '下载速度': '',
                    '总耗时': '',
                    '备注': error_msg
                })
    
    return sorted(results, key=lambda x: x['序号'])

def process_excel_file(file_path):
    """处理Excel文件"""
    global current_file, all_results, total_count, current_count, success_count, failure_count
    current_file = file_path
    
    # 重置计数器
    total_count = 0
    current_count = 0
    success_count = 0
    failure_count = 0
    all_results = []
    
    save_dir = os.path.dirname(os.path.abspath(file_path))
    file_stem = Path(file_path).stem
    update_progress(f"开始处理文件: {file_path}")
    update_progress(f"结果将保存在目录: {save_dir}")
    
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path, header=None)
        total_count = len(df)
        update_progress(f"找到 {total_count} 条记录，开始测试...")
        
        # 按每批200个处理
        batch_size = 200
        for start_idx in range(0, total_count, batch_size):
            end_idx = min(start_idx + batch_size, total_count)
            batch_df = df.iloc[start_idx:end_idx]
            batch_results = process_batch(batch_df, start_idx)
            all_results.extend(batch_results)
            
            # 每批次完成后保存一次结果
            save_final_results(file_path)
            
            # 检查是否需要继续
            if current_count >= total_count:
                break
    
    except Exception as e:
        error_msg = f"处理Excel文件时出错: {str(e)}"
        update_progress(error_msg, False)
    
    finally:
        # 最后保存一次结果
        save_final_results(file_path)

def find_excel_files(directory='.'):
    """查找目录中的Excel文件"""
    excel_files = []
    for file in os.listdir(directory):
        if file.endswith(('.xlsx', '.xls')) and not file.endswith('_结果.xlsx'):
            excel_files.append(os.path.join(directory, file))
    return excel_files

def main():
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            process_excel_file(file_path)
        else:
            print(f"文件不存在: {file_path}")
    else:
        excel_files = find_excel_files()
        if excel_files:
            print("找到以下Excel文件:")
            for i, file in enumerate(excel_files, 1):
                print(f"{i}. {file}")
            choice = input("请选择要处理的文件编号（输入q退出）: ")
            if choice.lower() != 'q':
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(excel_files):
                        process_excel_file(excel_files[index])
                    else:
                        print("无效的选择")
                except ValueError:
                    print("无效的输入")
        else:
            print("当前目录下没有找到Excel文件")

if __name__ == '__main__':
    main()