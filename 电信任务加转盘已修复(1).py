# 自己设置电信的服务密码和 AndroidID, 把 手机号#服务密码#AndroidID 填到变量里, 多账号换行或&隔开:
# export chinaTelecomAccount="18638363194#521314#079bf463c82ce200"&"17337901121#521314#079bf463c82ce200"
# AndroidID获取:
# https://telecom.nufe.ccwu.cc

import asyncio
import base64
import json
import os
import random
import re
import string
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Union

import certifi
import requests
from Crypto.Cipher import AES, DES3, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

try:
    from sendNotify import send as send_notify
except ImportError:
    send_notify = None

# --- 配置与常量 ---
KEYS = {
    'login_rsa': """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDBkLT15ThVgz6/NOl6s8GNPofdWzWbCkWnkaAm7O2LjkM1H7dMvzkiqdxU02jamGRHLX/ZNMCXHnPcW/sDhiFCBN18qFvy8g6VYb9QtroI09e176s+ZCtiv7hbin2cCTj99iUpnEloZm19lwHyo69u5UMiPMpq0/XKBO8lYhN/gwIDAQAB
-----END PUBLIC KEY-----""",
    'data_rsa': """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC+ugG5A8cZ3FqUKDwM57GM4io6JGcStivT8UdGt67PEOihLZTw3P7371+N47PrmsCpnTRzbTgcupKtUv8ImZalYk65dU8rjC/ridwhw9ffW2LBwvkEnDkkKKRi2liWIItDftJVBiWOh17o6gfbPoNrWORcAdcbpk2L+udld5kZNwIDAQAB
-----END PUBLIC KEY-----""",
    'mall_rsa': """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDIPOHtjs6p4sTlpFvrx+ESsYkEvyT4JB/dcEbU6C8+yclpcmWEvwZFymqlKQq89laSH4IxUsPJHKIOiYAMzNibhED1swzecH5XLKEAJclopJqoO95o8W63Euq6K+AKMzyZt1SEqtZ0mXsN8UPnuN/5aoB3kbPLYpfEwBbhto6yrwIDAQAB
-----END PUBLIC KEY-----""",
    'des3': b'1234567`90koiuyhgtfrdews',
    'aes_def': b'34d7cb0bcdf07523',
    'aes_login': 'telecom_wap_2018',
}
CACHE_FILE = Path(__file__).parent / 'chinaTelecom_cache.json'
global_logs, cache = [], {}

# --- 工具函数 ---
log = lambda m: (global_logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}"), print(global_logs[-1]))
mask = lambda p: f"{p[:3]}****{p[-4:]}" if len(p) >= 7 else p
ts = lambda: datetime.now().strftime('%Y%m%d%H%M%S')
rd_str = lambda l: ''.join(random.choices(string.ascii_letters + string.digits, k=l))
encode = lambda s: ''.join(chr(ord(c) + 2) for c in s)


# --- SSL与会话 ---
class CustomSSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1:!aNULL:!eNULL:!MD5')
        ctx.check_hostname = False
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


session = requests.Session()
session.verify = certifi.where()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; U; Android 12; zh-cn) AppleWebKit/533.1 (KHTML, like Gecko) Version/5.0 Mobile Safari/533.1'})
session.mount('https://', CustomSSLAdapter())


# --- 加密逻辑 ---
def encrypt_des3(data, mode='enc'):
    cipher = DES3.new(KEYS['des3'], DES3.MODE_CBC, 8 * b'\0')
    if mode == 'enc':
        return cipher.encrypt(pad(data.encode(), 8)).hex()
    return unpad(cipher.decrypt(bytes.fromhex(data)), 8).decode()


def encrypt_aes(data, key=KEYS['aes_def'], b64=False):
    data = json.dumps(data, separators=(',', ':')) if isinstance(data, (dict, list)) else data
    cipher = AES.new(key if isinstance(key, bytes) else key.encode(), AES.MODE_ECB)
    enc = cipher.encrypt(pad(data.encode(), 16))
    return base64.b64encode(enc).decode() if b64 else enc.hex()


def encrypt_rsa(data, key_type='data', out='hex'):
    cipher = PKCS1_v1_5.new(RSA.import_key(KEYS[f'{key_type}_rsa']))
    data = json.dumps(data, separators=(',', ':')) if isinstance(data, (dict, list)) else data
    chunks = [data[i : i + 32].encode() for i in range(0, len(data), 32)]
    if out == 'hex':
        return ''.join(cipher.encrypt(c).hex() for c in chunks)
    return base64.b64encode(b''.join(cipher.encrypt(c) for c in chunks)).decode()


def encrypt_login_rsa(data):
    cipher = PKCS1_v1_5.new(RSA.import_key(KEYS['login_rsa']))
    return base64.b64encode(cipher.encrypt(data.encode())).decode()


# --- 请求装饰器/助手 ---
def api_req(url, method='POST', log_msg=None, raw=False, **kwargs) -> Union[Dict[str, Any], str]:
    try:
        r = session.request(method, url, timeout=15, **kwargs)
        if raw:
            return r.text

        # Try parse JSON
        res = r.json()
        if not isinstance(res, dict):
            return {}  # Enforce dict return

        if log_msg:
            if url.startswith('https://wapact.189.cn:9001/gateway/golden/api/lottery'):
                msg = res.get('biz', {}).get('resultInfo', {}).get('title') or res.get('msg') or res.get('message') or '成功'
            else:
                msg = res.get('msg') or res.get('resoultMsg') or ('成功' if isinstance(res, dict) else '已响应')
            log(f"{log_msg}: {msg}")
        return res
    except Exception as e:
        if log_msg:
            log(f"{log_msg}失败: {e}")
        return '' if raw else {}


# --- 业务逻辑 ---
def login(phone, password, raw_android_id, account_index=None):
    m_phone = mask(phone)
    account_cache = cache.get(phone)
    if not isinstance(account_cache, dict):
        account_cache = {}
        cache[phone] = account_cache

    using_cached_token = bool(account_cache.get('token') and account_cache.get('userId'))
    if not using_cached_token:
        if not raw_android_id:
            prefix = f"[账号{account_index}]" if account_index is not None else f"[登录失败] {m_phone}"
            log(f"{prefix} 错误：缺少AndroidID，格式应为 手机号#密码#AndroidID")
            return None
        android_id = encode(raw_android_id)
        log(f"[登录] {m_phone} 正在请求新Token...")
        timestamp = ts()
        body = {
            "headerInfos": {
                "code": "userLoginNormal",
                "timestamp": timestamp,
                "broadAccount": "",
                "broadToken": "",
                "clientType": "#13.1.0#channel38#Xiaomi 22021211RC#",
                "provinceCode": "",
                "shopId": "20002",
                "source": "110003",
                "sourcePassword": "Sid98s",
                "token": "",
                "userLoginName": encode(phone),
            },
            "content": {
                "attach": "test",
                "fieldData": {
                    "signSignatureString": "",
                    "loginType": "4",
                    "accountType": "",
                    "loginAuthCipherAsymmertric": encrypt_login_rsa(f"iPhone 14 15.4.{raw_android_id[:12]}{phone}{timestamp}{password}0$$$0."),
                    "deviceUid": "",
                    "phoneNum": encode(phone),
                    "isChinatelecom": "",
                    "systemVersion": "12",
                    "androidId": android_id,
                    "loginAuthCipher": "",
                    "authentication": encode(password),
                },
            },
        }
        res = api_req('https://appgologin.189.cn:9031/login/client/userLoginNormal', json=body, headers={'User-Agent': 'P216010901'}, log_msg=f"[请求登录] {m_phone}")
        log(res)
        if isinstance(res, dict):
            response_data = res.get('responseData') or {}
            login_data = response_data.get('data') or {}
            res_data = login_data.get('loginSuccessResult')
            if not res_data:
                code = response_data.get('resultCode', '')
                desc = response_data.get('resultDesc') or '无响应数据'
                log(f"[登录失败] {m_phone} [{code}] {desc}")
                return None
            cache[phone] = {**res_data, 'rawAndroidId': raw_android_id, 'androidId': android_id}
            save_cache()

    # 获取Ticket/UID
    xml = f'<Request><HeaderInfos><Code>getSingle</Code><Timestamp>{ts()}</Timestamp><BroadAccount></BroadAccount><BroadToken></BroadToken><ClientType>#9.6.1#channel50#iPhone 14 Pro Max#</ClientType><ShopId>20002</ShopId><Source>110003</Source><SourcePassword>Sid98s</SourcePassword><Token>{cache[phone]["token"]}</Token><UserLoginName>{phone}</UserLoginName></HeaderInfos><Content><Attach>test</Attach><FieldData><TargetId>{encrypt_des3(cache[phone]["userId"])}</TargetId><Url>4a6862274835b451</Url></FieldData></Content></Request>'
    res_xml = api_req('https://appgologin.189.cn:9031/map/clientXML', data=xml, headers={'Content-Type': 'application/xml'}, raw=True, log_msg=f"[获取Ticket] {m_phone}")
    if isinstance(res_xml, str) and ('过期' in res_xml or '校验错误' in res_xml):
        log(f"[Token失效] {m_phone} 重新登录")
        cache[phone] = {}
        save_cache()
        return login(phone, password, raw_android_id, account_index)

    try:
        if not isinstance(res_xml, str) or '<Ticket>' not in res_xml:
            log(f"[Ticket异常] {m_phone} 响应: {str(res_xml)[:100]}")
            return None
        uid = encrypt_des3(res_xml.split('<Ticket>')[1].split('</Ticket>')[0], 'dec')
        if using_cached_token:
            log(f"[登录] {m_phone} 缓存Token登录成功")
        user = {**cache[phone], 'uid': uid, 'phoneNbr': phone}
        # 统一登录获取Bearer
        auth_body = encrypt_aes({"ticket": uid, "backUrl": "https%3A%2F%2Fwapact.189.cn%3A9001", "platformCode": "P201010301", "loginType": 2}, KEYS['aes_login'], True)
        auth_res = api_req('https://wapact.189.cn:9001/unified/user/login', data=auth_body, headers={'Content-Type': 'application/json'})
        if isinstance(auth_res, dict) and auth_res.get('code') == 0:
            user['Authorization'] = f"Bearer {auth_res['biz']['token']}"
        return user
    except Exception as e:
        log(f"[登录流程异常] {m_phone}: {e}")
        return None


def sign_tasks(user):
    m = mask(user['phoneNbr'])
    sso = api_req(f"https://wappark.189.cn/jt-sign/ssoHomLogin?ticket={user['uid']}", method='GET')
    if not isinstance(sso, dict) or not sso or 'sign' not in sso:
        return

    # 签到
    api_req(
        'https://wappark.189.cn/jt-sign/webSign/sign', json={"encode": encrypt_aes({"phone": user['phoneNbr'], "date": int(time.time() * 1000)})}, headers={'sign': sso['sign']}, log_msg=f"[签到] {m}"
    )

    # 进度与奖励
    def check_and_award(path, key, days_list, label):
        res = api_req(f'https://wappark.189.cn/jt-sign/{path}', json={"para": encrypt_rsa({"phone": user['phoneNbr']})}, headers={'sign': sso['sign']})
        if not isinstance(res, dict):
            return
        days = str(res.get('data', {}).get(key) if 'data' in res else res.get(key, 0))
        log(f"[{label}] {m}: {days}天")
        if days in days_list:
            api_req(
                'https://wappark.189.cn/jt-sign/webSign/exchangePrize',
                json={"para": encrypt_rsa({"phone": user['phoneNbr'], "type": days})},
                headers={'sign': sso['sign']},
                log_msg=f"[领奖] {m} {days}天",
            )

    check_and_award('api/home/userStatusInfo', 'signDay', ['7'], '连签')
    check_and_award('webSign/continueSignDays', 'continueSignDays', ['15', '28'], '累签')

    # 任务列表
    xtoken = ''
    tasks = api_req(
        'https://wappark.189.cn/jt-sign/webSign/homepage', json={"para": encrypt_rsa({"phone": user['phoneNbr'], "shopId": "20001", "type": "hg_qd_zrwzjd"})}, headers={'sign': sso['sign']}
    )
    if isinstance(tasks, dict):
        for t in tasks.get('data', {}).get('biz', {}).get('adItems', []):
            if t.get('taskState') not in ['0', '1']:
                continue
            content = t.get('contentOne')
            title = (t.get('title') or '').split()[0] if t.get('title') else ''
            if content == '3':
                if t.get('rewardId'):
                    api_req(
                        'https://wappark.189.cn/jt-sign/paradise/receiveReward',
                        json={"para": encrypt_rsa({"phone": user['phoneNbr'], "rewardId": t['rewardId']})},
                        headers={'sign': sso['sign']},
                        log_msg=f"[领奖] {m} {title}",
                    )
            elif content == '5':
                api_req(
                    'https://wappark.189.cn/jt-sign/paradise/openMsg',
                    json={"para": encrypt_rsa({"phone": user['phoneNbr']})},
                    headers={'sign': sso['sign']},
                    log_msg=f"[任务] {m} {title}",
                )
            elif content == '6':
                api_req(
                    'https://appfuwu.189.cn:9021/query/sharingGetGold',
                    json={
                        "headerInfos": {
                            "code": "sharingGetGold",
                            "timestamp": ts(),
                            "broadAccount": "",
                            "broadToken": "",
                            "clientType": "#9.6.1#channel50#iPhone 14 Pro Max#",
                            "shopId": "20002",
                            "source": "110003",
                            "sourcePassword": "Sid98s",
                            "token": user.get('token', ''),
                            "userLoginName": user.get('phoneNbr', ''),
                        },
                        "content": {
                            "attach": "test",
                            "fieldData": {
                                "shareSource": "3",
                                "userId": user.get('userId', ''),
                                "account": encode(user.get('phoneNbr', '')),
                            },
                        },
                    },
                    log_msg=f"[分享] {m}",
                )
            elif content in ('10', '13'):
                if not xtoken:
                    r = session.get(
                        'https://xbk.189.cn/xbkapi/api/auth/jump', params={'userID': user.get('uid', ''), 'version': '9.3.3', 'type': 'room', 'l': 'renwu'}, allow_redirects=False, timeout=15
                    )
                    m_loc = re.search(r'usercode=(\w+)', r.headers.get('location', ''))
                    if m_loc:
                        ct = api_req('https://xbk.189.cn/xbkapi/api/auth/userinfo/codeToken', json={"usercode": m_loc.group(1)})
                        if isinstance(ct, dict) and ct.get('code') == 0:
                            xtoken = ct.get('data', {}).get('token', '')
                if xtoken:
                    auth_h = {'Authorization': f'Bearer {encrypt_rsa(xtoken, "mall", "b64")}'}
                    for _ in range(11):
                        live_id = random.randint(1000, 1999)
                        init = api_req('https://xbk.189.cn/xbkapi/lteration/liveTask/index/watchLiveInit', json={"period": 1, "liveId": live_id}, headers=auth_h)
                        if not isinstance(init, dict) or init.get('code') != 0:
                            break
                        time.sleep(15)
                        wl = api_req('https://xbk.189.cn/xbkapi/lteration/liveTask/index/watchLive', json={"period": 1, "liveId": live_id, "key": init.get('data')}, headers=auth_h)
                        if isinstance(wl, dict) and wl.get('code') == 0:
                            log(f"[直播] {m} 观看直播[{live_id}]成功")
                        else:
                            break
            elif content == '18':
                api_req(
                    'https://wappark.189.cn/jt-sign/webSign/polymerize',
                    json={"para": encrypt_rsa({"phone": user['phoneNbr'], "jobId": t['taskId']})},
                    headers={'sign': sso['sign']},
                    log_msg=f"[任务] {m} {title}",
                )
            time.sleep(2)

    # 喂食
    for i in range(10):
        res = api_req('https://wappark.189.cn/jt-sign/paradise/food', json={"para": encrypt_rsa({"phone": user['phoneNbr']})}, headers={'sign': sso['sign']})
        msg = res.get('resoultMsg', '') if isinstance(res, dict) else ''
        if "最大" in msg or not msg:
            break
        log(f"[喂食] {m} 第{i+1}次: {msg}")
        time.sleep(1)

    # 宠物等级
    pi = api_req('https://wappark.189.cn/jt-sign/paradise/getParadiseInfo', json={"para": encrypt_rsa({"phone": user['phoneNbr']})}, headers={'sign': sso['sign']})
    if isinstance(pi, dict) and str(pi.get('resoultCode', '')) == '0':
        li = pi.get('userInfo', {}).get('levelInfoMap', {})
        if li:
            log(f"[宠物] {m} 宠物等级[Lv.{li.get('level', 0)}], 升级进度: {li.get('growthValue', 0)}/{li.get('fullGrowthCoinValue', 0)}")
            notify.append(f"宠物等级[Lv.{li.get('level', 0)}], 升级进度: {li.get('growthValue', 0)}/{li.get('fullGrowthCoinValue', 0)}")
        else:
            log(f"[宠物] {m} 响应数据: {json.dumps(pi, ensure_ascii=False)[:200]}")
    elif isinstance(pi, dict):
        log(f"[宠物] {m} 查询失败[{pi.get('resoultCode')}]: {pi.get('resoultMsg') or pi.get('msg') or pi.get('error', '')}")

    # 金豆余额
    ci = api_req('https://wappark.189.cn/jt-sign/api/home/userCoinInfo', json={"para": encrypt_rsa({"phone": user['phoneNbr']})}, headers={'sign': sso['sign']})
    if isinstance(ci, dict) and str(ci.get('resoultCode', '')) == '0':
        total = ci.get('totalCoin', 0)
        log(f"[金豆] {m} 金豆余额: {total}")
        notify.append(f"金豆余额: {total}")
        if ci.get('amountEx'):
            try:
                ym = datetime.fromtimestamp(ci['expireDate'] / 1000).strftime('%Y-%m') if ci.get('expireDate') else ''
            except Exception:
                ym = ''
            log(f"[金豆] {m} {ym}月底将过期{ci['amountEx']}金豆")
            notify.append(f"{ym}月底将过期{ci['amountEx']}金豆")
    elif isinstance(ci, dict):
        log(f"[金豆] {m} 余额查询失败[{ci.get('resoultCode')}]: {ci.get('resoultMsg') or ci.get('msg') or ci.get('error', '')}")

        # 金豆转盘
    if 'Authorization' in user:
        tab = api_req(f"https://wapact.189.cn:9001/gateway/golden/api/queryTurnTable?userType=1&_={int(time.time()*1000)}", method='GET', headers={'Authorization': user['Authorization']})
        if isinstance(tab, dict) and tab.get('code') == 0:
            act_id = tab['biz']['wzTurntable']['code']
            chk = api_req(f"https://wapact.189.cn:9001/gateway/standQuery/detail/check?activityId={act_id}", method='GET', headers={'Authorization': user['Authorization']})
            rem = chk.get('biz', {}).get('resultInfo', {}).get('userMaximum', 0) - chk.get('biz', {}).get('resultInfo', {}).get('userCount', 0) if isinstance(chk, dict) else 0
            log(f"[抽奖] {m} 可抽{rem}次")
            for _ in range(rem):
                lr = api_req('https://wapact.189.cn:9001/gateway/golden/api/lottery', json={"activityId": act_id}, headers={'Authorization': user['Authorization']})
                prize = lr.get('biz', {}).get('resultInfo', {}).get('title', '') if isinstance(lr, dict) else ''
                if prize:
                    notify.append(f"抽奖结果:{prize}")
                    log(f"[抽奖] {m} 抽奖结果:{prize}")
                time.sleep(2)


# --- 缓存管理 ---
def load_cache():
    global cache
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))


def save_cache():
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')


# --- 主入口 ---
if __name__ == '__main__':
    notify = []
    load_cache()
    chinaTelecomAccount = os.environ.get('chinaTelecomAccount', '')
    accs = [a.split('#') for a in re.split('[&\n]', chinaTelecomAccount) if '#' in a]
    if not accs:
        log("未找到账号，请按 手机号#密码#AndroidID 格式设置 chinaTelecomAccount")
        sys.exit(1)

    for i, parts in enumerate(accs, 1):
        phone = parts[0].strip()
        pwd = parts[1].strip() if len(parts) > 1 else ''
        android_id = parts[2].strip() if len(parts) > 2 else ''
        log(f"\n{'='*10} 账号[{i}] {mask(phone)} {'='*10}")
        u = login(phone, pwd, android_id, i)
        if u:
            notify.append(f"账号[{i}] {mask(phone)}")
            sign_tasks(u)
            notify.append("")
        time.sleep(2)
    # 推送通知
    if notify and send_notify:
        send_notify(f"电信营业厅", '\n'.join(notify))
