#!/usr/bin/python3
# -*- coding: utf-8 -*-
#本脚本用于自动化恩山论坛账号登录验证和推广链接访问任务。集成了携趣代理和白名单管理功能，能够自动切换代理IP进行推广操作。
#基础使用方法：
# 设置环境变量
#恩山论坛Cookie
#export es_cookie="你的cookie"
#携趣白名单配置（必需）
#export xq_add_white="123456#你的ukey"
#携趣代理配置（必需）
#export xq_proxy="123456#你的vkey"
#重要说明：白名单和代理配置必须同时设置，否则将跳过推广任务。
#携趣配置获取方法

#🔍 获取携趣UID

#登录携趣官网 (https://www.xiequ.cn/index.html?e31b2954)
#进入用户中心
#在个人信息或账户设置中查看UID
#🔑 获取白名单ukey

#登录携趣用户中心
#进入“IP白名单管理“页面
#查看页面URL或API接口文档获取ukey
#或联系携趣客服获取白名单管理密钥
#🌐 获取代理vkey

#登录携趣用户中心
#进入“代理IP提取“页面
#查看提取链接中的vkey参数
#例如：http://api.xiequ.cn/VAD/GetIp.aspx?uid=123456&vkey=ABC123...
#💡 重要说明

#ukey 和 vkey 是不同的密钥，不能通用
#ukey 用于白名单管理
#vkey 用于代理IP提取
#必须同时配置 xq_add_white 和 xq_proxy 才能执行推广任务
#缺少任一配置将跳过白名单检查和推广任务

# 1. 网盘脚本资源：https://pan.quark.cn/s/3e02a6670a5e   
# 2. 更多资源加群：958310806
# 3. 企业微信客服：https://work.weixin.qq.com/kfid/kfc15fe72d1a9187b2f
# 携趣代理注册地址：https://www.xiequ.cn/index.html?e31b2954
import requests
import time
import os
import random
from bs4 import BeautifulSoup
import re

def print_banner():
    """打印脚本信息横幅"""
    print("#" * 60)
    print("# 1. 网盘脚本资源：https://pan.quark.cn/s/3e02a6670a5e   ")
    print("# 2. 更多资源加群：958310806")
    print("# 3. 企业微信客服：https://work.weixin.qq.com/kfid/kfc15fe72d1a9187b2f")
    print("# 携趣代理注册地址：https://www.xiequ.cn/index.html?e31b2954")
    print("#" * 60)
    print()

# --- 配置 ---
NUM_VISITS = 10      # 推广次数
MAX_RETRIES = 5      # 每次推广最大重试次数

# 携趣配置
# 白名单使用 uid#ukey，代理使用 uid#vkey
xq_add_white_str = os.getenv('xq_add_white')  # 白名单配置: uid#ukey  
xq_proxy_str = os.getenv('xq_proxy')  # 代理配置: uid#vkey

# 白名单配置
XQ_UID = None
XQ_UKEY = None
PROXY_API = None

# 优先使用专门的白名单配置
if xq_add_white_str:
    try:
        XQ_UID, XQ_UKEY = xq_add_white_str.split('#')
        print(f"✅ 白名单配置: UID={XQ_UID}")
    except ValueError:
        print("❌ xq_add_white 格式错误，应为 'uid#ukey'")

# 优先使用专门的代理配置，如果没有则尝试使用白名单配置
if xq_proxy_str:
    try:
        proxy_uid, proxy_vkey = xq_proxy_str.split('#')
        PROXY_API = f'http://api.xiequ.cn/VAD/GetIp.aspx?act=get&uid={proxy_uid}&vkey={proxy_vkey}&num=1&time=30&plat=1&re=0&type=0&so=1&ow=1&spl=1&addr=&db=1'
        print(f"✅ 代理配置: UID={proxy_uid}")
    except ValueError:
        print("❌ xq_proxy 格式错误，应为 'uid#vkey'")
# ukey和vkey不通用，不能复用白名单配置

# 提示信息
if not XQ_UID or not XQ_UKEY:
    print("⚠️ 未配置携趣白名单，将跳过白名单检查")
if not PROXY_API:
    print("⚠️ 未配置携趣代理，将跳过代理获取")

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
}

# --- 携趣白名单管理函数 ---
def get_public_ip():
    """获取当前服务器公网IP地址"""
    print('🔍 正在获取服务器IP地址...')
    try:
        response = requests.get('https://whois.pconline.com.cn/ipJson.jsp?ip=&json=true', timeout=10)
        if response.status_code == 200:
            data = response.json()
            ip = data.get('ip', None)
            if ip:
                print(f"📍 当前服务器IP: {ip}")
                return ip
    except Exception as e:
        print(f"❌ 获取IP失败，尝试备用方法...")
    
    # 备用方法
    try:
        response = requests.get('https://httpbin.org/ip', timeout=10)
        if response.status_code == 200:
            ip = response.json().get('origin', '').split(',')[0].strip()
            if ip:
                print(f"📍 当前服务器IP: {ip} (备用方法)")
                return ip
    except Exception as e:
        print(f"❌ 备用方法也失败了")
    
    print("❌ 无法获取当前服务器IP地址")
    return None

def get_whitelist():
    """获取携趣白名单"""
    if not XQ_UID or not XQ_UKEY:
        return []
    
    url = f"http://op.xiequ.cn/IpWhiteList.aspx?uid={XQ_UID}&ukey={XQ_UKEY}&act=get"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            whitelist_text = response.text.strip()
            
            # 检查是否是错误信息
            if whitelist_text.startswith('Err:'):
                print(f"❌ 携趣API认证失败: {whitelist_text}")
                return None  # 返回None表示API错误，区别于空白名单
            
            if whitelist_text and whitelist_text != '':
                return whitelist_text.split(',')
            else:
                return []  # 空白名单
    except Exception as e:
        print(f"❌ 网络错误: {str(e)[:50]}...")
    return None  # 网络错误等

def delete_whitelist_ip(ip):
    """删除白名单IP"""
    if not XQ_UID or not XQ_UKEY:
        return False
    
    url = f"http://op.xiequ.cn/IpWhiteList.aspx?uid={XQ_UID}&ukey={XQ_UKEY}&act=del&ip={ip}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            result_text = response.text.strip()
            
            # 检查是否是错误信息
            if result_text.startswith('Err:'):
                print(f"❌ 删除IP失败: {result_text}")
                return False
            
            print(f"🗑️ 已删除旧IP: {ip}")
            return True
        else:
            print(f"❌ 删除IP失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 删除IP网络错误: {str(e)[:30]}...")
    return False

def add_whitelist_ip(ip):
    """添加白名单IP"""
    if not XQ_UID or not XQ_UKEY:
        return False
    
    url = f"http://op.xiequ.cn/IpWhiteList.aspx?uid={XQ_UID}&ukey={XQ_UKEY}&act=add&ip={ip}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            result_text = response.text.strip()
            
            # 检查是否是错误信息
            if result_text.startswith('Err:'):
                print(f"❌ 添加IP失败: {result_text}")
                return False
            
            print(f"✅ 已添加IP到白名单: {ip}")
            return True
        else:
            print(f"❌ 添加IP失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 添加IP网络错误: {str(e)[:30]}...")
    return False

def manage_whitelist(new_ip):
    """管理白名单，如果满了就删除最后一个，然后添加新IP"""
    whitelist = get_whitelist()
    
    # 如果获取白名单失败（返回None），直接尝试添加
    if whitelist is None:
        print("⚠️ 无法获取白名单，直接尝试添加...")
        return add_whitelist_ip(new_ip)
    
    print(f"📋 当前白名单: {whitelist} ({len(whitelist)}/5)")
    
    # 检查IP是否已在白名单中
    if new_ip in whitelist:
        print(f"✅ IP已在白名单中: {new_ip}")
        return True
    
    # 如果白名单满了（≥5个），删除最后一个
    if len(whitelist) >= 5:
        oldest_ip = whitelist[-1]
        print(f"⚠️ 白名单已满，删除最旧IP: {oldest_ip}")
        delete_whitelist_ip(oldest_ip)
    
    # 添加新IP
    return add_whitelist_ip(new_ip)

def check_and_update_whitelist():
    """检查并更新携趣白名单"""
    if not XQ_UID or not XQ_UKEY:
        # 这里不再打印跳过信息，由main函数统一处理
        return True
    
    print("\n🔐 ═══════ 携趣白名单检查 ═══════")
    current_ip = get_public_ip()
    if not current_ip:
        print("❌ 无法获取当前IP，跳过白名单检查")
        return False
    
    # 检查当前IP是否在白名单中
    whitelist = get_whitelist()
    
    # 如果获取白名单失败（API错误），直接尝试添加IP
    if whitelist is None:
        print("⚠️ API认证失败，尝试直接添加IP...")
        success = add_whitelist_ip(current_ip)
    elif current_ip in whitelist:
        print(f"✅ IP已在白名单中: {current_ip}")
        print("🔐 ═══════ 白名单检查完成 ═══════\n")
        return True
    else:
        print(f"⚠️ IP不在白名单中: {current_ip}")
        success = manage_whitelist(current_ip)
    
    if success:
        print(f"✅ 白名单更新成功")
    else:
        print(f"❌ 白名单更新失败")
    
    print("🔐 ═══════ 白名单检查完成 ═══════\n")
    return success

def setup_session():
    """配置并返回 requests.Session 对象"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0'
    })
    return session

def get_login_status(session, cookie_str):
    """尝试登录，提取用户名和用户ID"""
    signin_url = "https://www.right.com.cn/forum/forum.php"
    login_headers = {'Cookie': cookie_str}
    
    for retry in range(MAX_RETRIES):
        try:
            response = session.get(signin_url, headers=login_headers, timeout=120)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 提取用户名
                user_element = soup.find('strong', class_='vwmy qq')
                username = None
                if user_element:
                    username_tag = user_element.find('a')
                    username = username_tag.get_text(strip=True) if username_tag else None
                
                # 提取用户ID
                user_id = None
                avatar_div = soup.find('div', class_='avt y')
                if avatar_div:
                    avatar_a_tag = avatar_div.find('a')
                    if avatar_a_tag and avatar_a_tag.has_attr('href'):
                        match = re.search(r'uid-(\d+)\.html', avatar_a_tag['href'])
                        if match:
                            user_id = match.group(1)
                
                # 构建消息
                if username:
                    if user_id:
                        message = f'✅ {username} (UID:{user_id})'
                    else:
                        message = f'✅ {username} (UID:未提取)'
                else:
                    message = '❌ 登录失败'
                
                return {'login_message': message, 'user_id': user_id}
            
            else:
                if retry < MAX_RETRIES - 1:
                    time.sleep(5)
                    
        except Exception as e:
            if retry < MAX_RETRIES - 1:
                time.sleep(5)
    
    return {'login_message': f"❌ 登录失败 (重试{MAX_RETRIES}次)", 'user_id': None}

def process_cookies(cookies_list):
    """处理多个cookie，执行登录操作"""
    log_messages = []
    first_extracted_uid = None
    
    for index, cookie in enumerate(cookies_list, 1):
        result = get_login_status(setup_session(), cookie)
        log_messages.append(f"账号{index}: {result['login_message']}")
        
        if result['user_id'] and first_extracted_uid is None:
            first_extracted_uid = result['user_id']
    
    return "\n".join(log_messages), first_extracted_uid

def get_proxy():
    """获取代理IP"""
    if not PROXY_API:
        return None
    
    try:
        response = requests.get(PROXY_API, timeout=10)
        response.raise_for_status()
        proxy_ip = response.text.strip()
        return proxy_ip if proxy_ip else None
    except Exception as e:
        # 简化错误输出，不在这里打印，交给调用方处理
        return None

def visit_promotion_link(target_url):
    """访问指定的推广链接并返回结果信息"""
    promotion_results = []
    uid = target_url.split('=')[-1]
    print(f"🎯 推广目标UID: {uid}")
    
    success_count = 0
    fail_count = 0
    
    for i in range(NUM_VISITS):
        success = False
        
        # 添加随机延时3-5秒
        if i > 0:
            delay = random.uniform(3, 5)
            print(f"⏱️ 等待 {delay:.1f}s...")
            time.sleep(delay)
        
        for retry in range(MAX_RETRIES):
            try:
                # 获取代理IP
                proxy_ip = get_proxy()
                if not proxy_ip:
                    print(f"❌ [{i + 1}] 无法获取代理IP")
                    if retry < MAX_RETRIES - 1:
                        time.sleep(5)
                    continue
                
                print(f"🚀 [{i + 1}] 使用代理: {proxy_ip}")
                
                # 使用代理发送请求
                proxies = {'http': f'http://{proxy_ip}', 'https': f'http://{proxy_ip}'}
                response = requests.get(target_url, headers=HEADERS, proxies=proxies, timeout=15)
                
                if response.status_code == 200:
                    print(f"✅ [{i + 1}] 推广成功")
                    promotion_results.append(f"✅ 第{i + 1}次成功")
                    success_count += 1
                    success = True
                    break
                else:
                    print(f"❌ [{i + 1}] HTTP {response.status_code}")
                    
            except Exception as e:
                error_msg = str(e)
                if "ProxyError" in error_msg:
                    print(f"❌ [{i + 1}] 代理连接失败")
                elif "timeout" in error_msg.lower():
                    print(f"❌ [{i + 1}] 连接超时")
                else:
                    print(f"❌ [{i + 1}] 网络错误")
            
            if retry < MAX_RETRIES - 1:
                print(f"🔄 [{i + 1}] 重试中... ({retry + 1}/{MAX_RETRIES})")
                time.sleep(5)
        
        if not success:
            print(f"💥 [{i + 1}] 最终失败")
            promotion_results.append(f"❌ 第{i + 1}次失败")
            fail_count += 1
    
    # 添加统计信息
    promotion_results.append(f"\n📊 推广统计: 成功 {success_count}/{NUM_VISITS}, 失败 {fail_count}/{NUM_VISITS}")
    return promotion_results

def main():
    """主函数入口"""
    # 打印脚本信息横幅
    print_banner()
    
    # 尝试导入 notify 库，如果失败则使用模拟的通知函数
    try:
        from notify import send
    except ImportError:
        print("警告: 'notify' 模块未找到。将使用打印输出模拟通知。")
        def send(title, content):
            print(f"--- 模拟通知 ---")
            print(f"标题: {title}")
            print(f"内容:\n{content}")
            print(f"--- 结束模拟通知 ---")
    
    env_cookie_string = os.environ.get("es_cookie")
    
    if not env_cookie_string:
        err_msg = "错误：未在环境变量中设置 es_cookie"
        print(err_msg)
        send("恩山论坛任务执行结果", err_msg)
        return

    # 处理cookie
    cookies = [c.strip() for c in env_cookie_string.splitlines() if c.strip()]
    if not cookies:
        err_msg = "错误：环境变量 es_cookie 为空或只包含无效条目"
        print(err_msg)
        send("恩山论坛任务执行结果", err_msg)
        return

    print("\n🔑 ═══════ 恩山论坛登录 ═══════")
    login_summary_messages, dynamic_uid = process_cookies(cookies)
    print(login_summary_messages)
    
    # 检查是否成功提取到UID
    if not dynamic_uid:
        err_msg = "❌ 未能提取到UID，无法生成推广链接"
        print(err_msg)
        send("恩山论坛任务执行结果", f"{login_summary_messages}\n\n{err_msg}")
        return
    
    print(f"🎯 推广UID: {dynamic_uid}")
    print("🔑 ═══════ 登录检查完成 ═══════")
    
    
    # 检查携趣配置完整性
    if not (XQ_UID and XQ_UKEY and PROXY_API):
        skip_msg = "⚠️ 携趣配置不完整，跳过白名单检查和推广任务"
        print(skip_msg)
        
        # 发送通知（仅登录结果）
        notification_content = [
            "【恩山论坛登录结果】",
            login_summary_messages,
            f"\n【推广UID】",
            f"🎯 {dynamic_uid}",
            "\n【执行状态】",
            skip_msg,
        ]
        send("恩山论坛任务执行结果", "\n".join(notification_content))
        return

    # 构建推广链接
    promotion_url_template = 'https://www.right.com.cn/forum/?fromuid={}'
    actual_promotion_url = promotion_url_template.format(dynamic_uid)

    # 检查并更新携趣白名单
    whitelist_success = check_and_update_whitelist()
    whitelist_message = "携趣白名单检查成功" if whitelist_success else "携趣白名单检查失败"
    
    if not whitelist_success:
        print("⚠️ 白名单检查失败，可能影响代理获取")

    print("🚀 ═══════ 开始推广任务 ═══════")
    promotion_results = visit_promotion_link(actual_promotion_url)
    print("🚀 ═══════ 推广任务完成 ═══════\n")

    # 发送通知
    notification_content = [
        "【恩山论坛登录结果】",
        login_summary_messages,
        f"\n【推广UID】",
        f"🎯 {dynamic_uid}",
        "\n【携趣白名单检查结果】",
        whitelist_message,
        "\n【推广链接访问详情】",
    ]
    notification_content.extend(promotion_results)
    
    send("恩山论坛任务执行结果", "\n".join(notification_content))

if __name__ == "__main__":
    main()