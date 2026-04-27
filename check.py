import os
import requests
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

def send_email(subject, content):
    """发送中文告警邮件"""
    # 从 Secrets 获取配置
    smtp_user = os.environ.get('SMTP_USER')    # 发件人邮箱账号
    smtp_pass = os.environ.get('SMTP_PASS')    # 发件人邮箱授权码
    smtp_server = os.environ.get('SMTP_SERVER')# SMTP服务器地址
    email_to = os.environ.get('EMAIL_TO')      # 收件人邮箱 (292200693@qq.com)

    if not all([smtp_user, smtp_pass, smtp_server, email_to]):
        print("❌ 错误: 邮件配置不全。请检查 Secrets: SMTP_USER, SMTP_PASS, SMTP_SERVER, EMAIL")
        return

    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = smtp_user  # 发件人显示
    msg['To'] = email_to     # 收件人显示
    msg['Subject'] = Header(subject, 'utf-8')
    
    try:
        # 尝试 3 次发信，应对 "system busy" 错误
        for attempt in range(1, 4):
            try:
                with smtplib.SMTP_SSL(smtp_server, 465, timeout=15) as server:
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_user, [email_to], msg.as_string())
                print(f"✅ 告警邮件已发送至: {email_to}")
                return
            except Exception as e:
                if attempt < 3:
                    print(f"⚠️ 邮件尝试 {attempt} 失败，5秒后重试... ({e})")
                    time.sleep(5)
                else:
                    raise e
    except Exception as e:
        print(f"❌ 邮件发送最终失败: {e}")

def check_sites():
    # 解析 HOST 地址列表
    raw_hosts = os.environ.get('HOSTS', '').strip("[] ")
    if not raw_hosts:
        print("❌ 未发现 HOST 配置")
        return

    hosts = [h.strip() for h in raw_hosts.split(',') if h.strip()]
    token = os.environ.get('PING_TOKEN', '')
    try_limit_str = os.environ.get('TRY_TIMES', '5')
    try_limit = int(try_limit_str) if try_limit_str.isdigit() else 5
    
    failed_reports = []

    # 循环检查每个服务器
    for index, host in enumerate(hosts, start=1):
        # 内部处理 URL 逻辑
        base = host.rstrip('/')
        target_url = base if base.endswith('/ping') else f"{base}/ping"
        
        # 🔐 日志脱敏：仅显示别名
        display_name = f"服务器 {index}"
        is_ok = False
        
        print(f"🔍 正在检查: {display_name}")

        for i in range(1, try_limit + 1):
            try:
                # 增加超时到 15s
                response = requests.get(
                    target_url, 
                    headers={"Authorization": f"Bearer {token}"}, 
                    timeout=15
                )
                if response.status_code == 200:
                    print(f"  - [{display_name}] 第 {i} 次尝试: 成功")
                    is_ok = True
                    break
                else:
                    print(f"  - [{display_name}] 第 {i} 次尝试: 异常状态码 {response.status_code}")
            except Exception:
                # 异常时不打印堆栈，防止泄露 IP 或端口
                print(f"  - [{display_name}] 第 {i} 次尝试: 连接失败/超时")
            
            if i < try_limit:
                time.sleep(5)

        if not is_ok:
            failed_reports.append((display_name, target_url))

    if failed_reports:
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = "可用性检查不通过"
        
        # 邮件内容是私密的，可以包含具体地址
        detail_lines = [f"● {name}: {url}" for name, url in failed_reports]
        content = f"""【监控警报】站点可用性检查失败

检测到以下服务器异常：
{chr(10).join(detail_lines)}

检查时间：{now_time} (UTC)
重试情况：已连续重试 {try_limit} 次失败。
"""
        send_email(subject, content)
    else:
        print("✨ 所有服务器检查通过，且已通过匿名化处理显示日志。")

if __name__ == "__main__":
    check_sites()
