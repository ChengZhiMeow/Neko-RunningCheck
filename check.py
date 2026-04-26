import os
import requests
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

def send_email(subject, content):
    """发送中文告警邮件"""
    sender = os.environ.get('SMTP_USER')
    receiver = os.environ.get('EMAIL_TO')
    password = os.environ.get('SMTP_PASS')
    smtp_server = os.environ.get('SMTP_SERVER')

    if not all([sender, receiver, password, smtp_server]):
        print("❌ 错误: 邮件配置信息不全，请检查 Secrets 配置")
        return

    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = sender  # QQ邮箱强制要求From必须等于登录邮箱
    msg['To'] = receiver
    msg['Subject'] = Header(subject, 'utf-8')
    
    try:
        # 使用 SSL 端口 465
        with smtplib.SMTP_SSL(smtp_server, 465) as server:
            server.login(sender, password)
            server.sendmail(sender, [receiver], msg.as_string())
        print("✅ 告警邮件已发送至:", receiver)
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def check_sites():
    # 获取并清洗 HOST 变量
    raw_hosts = os.environ.get('HOSTS', '').strip("[] ")
    if not raw_hosts:
        print("❌ 未发现 HOST 配置")
        return

    hosts = [h.strip() for h in raw_hosts.split(',') if h.strip()]
    token = os.environ.get('PING_TOKEN', '')
    try_limit = int(os.environ.get('TRY_TIMES', 5))
    
    failed_reports = []

    for host in hosts:
        # 智能拼接: 确保最终是以 /ping 结尾，且不重复
        base = host.rstrip('/')
        target_url = base if base.endswith('/ping') else f"{base}/ping"
        
        is_ok = False
        print(f"🔍 正在检查: {target_url}")

        for i in range(1, try_limit + 1):
            try:
                # 增加了超时时间到 20s，应对网络波动
                response = requests.get(
                    target_url, 
                    headers={"Authorization": f"Bearer {token}"}, 
                    timeout=20
                )
                if response.status_code == 200:
                    print(f"  - 第 {i} 次尝试: 成功 (200)")
                    is_ok = True
                    break
                else:
                    print(f"  - 第 {i} 次尝试: 失败 (状态码: {response.status_code})")
            except Exception as e:
                print(f"  - 第 {i} 次尝试: 异常 ({type(e).__name__})")
            
            if i < try_limit:
                time.sleep(5) # 失败后等待 5 秒

        if not is_ok:
            failed_reports.append(target_url)

    if failed_reports:
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = "可用性检查不通过"
        content = (
            f"警
