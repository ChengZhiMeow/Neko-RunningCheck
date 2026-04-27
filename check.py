import os
import requests
import time
import smtplib
import re
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

def mask_url(url):
    """脱敏处理：隐藏 IP 中间段和端口"""
    # 匹配 IP:端口 或 域名:端口
    pattern = r'(https?://)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+)(:\d+)?'
    def replace(match):
        protocol = match.group(1)
        address = match.group(2)
        # 如果是IP，遮盖中间两段；如果是域名，遮盖前缀
        if re.match(r'\d+\.', address):
            parts = address.split('.')
            address = f"{parts[0]}.***.***.{parts[-1]}"
        else:
            address = f"***{address[len(address)//2:]}"
        return f"{protocol}{address}[:****]"
    
    return re.sub(pattern, replace, url)

def send_email(subject, content):
    """发送中文告警邮件"""
    conf = {
        'sender': os.environ.get('SMTP_USER'),
        'receiver': os.environ.get('EMAIL_TO'),
        'password': os.environ.get('SMTP_PASS'),
        'server': os.environ.get('SMTP_SERVER')
    }

    # 检查哪个配置丢了
    missing = [k for k, v in conf.items() if not v]
    if missing:
        print(f"❌ 错误: 邮件配置项缺失: {', '.join(missing)}")
        return

    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = conf['sender']
    msg['To'] = conf['receiver']
    msg['Subject'] = Header(subject, 'utf-8')
    
    try:
        with smtplib.SMTP_SSL(conf['server'], 465) as server:
            server.login(conf['sender'], conf['password'])
            server.sendmail(conf['sender'], [conf['receiver']], msg.as_string())
        print("✅ 告警邮件已发送")
    except Exception as e:
        print(f"❌ 邮件发送失败: {str(e)[:50]}...") # 限制报错长度防止泄露

def check_sites():
    raw_hosts = os.environ.get('HOSTS', '').strip("[] ")
    if not raw_hosts:
        print("❌ 未发现 HOST 配置")
        return

    hosts = [h.strip() for h in raw_hosts.split(',') if h.strip()]
    token = os.environ.get('PING_TOKEN', '')
    try_limit_str = os.environ.get('TRY_TIMES', '5')
    try_limit = int(try_limit_str) if try_limit_str.isdigit() else 5
    
    failed_reports = []

    for host in hosts:
        base = host.rstrip('/')
        target_url = base if base.endswith('/ping') else f"{base}/ping"
        
        # 日志脱敏显示
        masked_url = mask_url(target_url)
        is_ok = False
        print(f"🔍 正在检查: {masked_url}")

        for i in range(1, try_limit + 1):
            try:
                response = requests.get(
                    target_url, 
                    headers={"Authorization": f"Bearer {token}"}, 
                    timeout=15
                )
                if response.status_code == 200:
                    print(f"  - 第 {i} 次尝试: 成功")
                    is_ok = True
                    break
                else:
                    print(f"  - 第 {i} 次尝试: 失败 (Code: {response.status_code})")
            except Exception as e:
                print(f"  - 第 {i} 次尝试: 异常 ({type(e).__name__})")
            
            if i < try_limit:
                time.sleep(5)

        if not is_ok:
            # 邮件里保留真实地址，方便运维
            failed_reports.append(target_url)

    if failed_reports:
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = "可用性检查不通过"
        failed_list_str = "\n".join([f" - {url}" for url in failed_reports])
        content = f"""警报：站点监控发现异常！

失败地址：
{failed_list_str}

检查时间：{now_time} (UTC)
重试策略：已重试 {try_limit} 次。"""
        
        send_email(subject, content)
    else:
        print("✨ 所有站点检查通过。")

if __name__ == "__main__":
    check_sites()
