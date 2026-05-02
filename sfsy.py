#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顺丰速运自动任务 v1.0.8

功能：自动执行顺丰速运日常积分任务 + 33周年庆活动任务 + 33周年庆抽奖 + 会员日活动
支持签到、做任务、领积分、对暗号、抽勋章、集齐5勋章抽大奖等

更新说明:
### 2026.03.28
v1.0.8:
- 🔧 对暗号答案优先从API获取，仅当天无答案时读环境变量
- ✨ 新增暗号开奖结果及奖励详情展示

### 2026.03.22
v1.0.7:
- ✨ 新增会员日活动（每月26-28号自动执行）
- 🎁 会员日支持抽奖、做任务、领奖励、红包合成与提取
- 🎛️ 会员日做成子开关 ENABLE_MEMBER_DAY 控制

### 2026.03.19
v1.0.6:
- ✨ 新增邀请初始化功能（随机选择邀请码）
- ✨ 新增领取寄件会员权益专用接口
- ✨ 新增倒计时奖励领取（每日免费抽勋章机会）
- 🔧 修正积分兑换接口参数
- 📊 增强奖励领取和勋章抽取的日志显示
- 🎛️ 积分兑换抽勋章做成子开关控制

### 2026.03.18
v1.0.5:
- 🔗 整合日常积分任务、33周年庆活动、33周年庆抽奖三合一
- 🔌 集成品赞代理系统，支持固定IP代理和API动态代理
- 🔄 引入代理自动续期与故障转移机制
- 🎛️ 子任务开关控制（日常任务/周年活动/周年抽奖）

配置说明:
1. 账号变量 (sfsyUrl):
    格式: CK值或登录URL[#代理地址]
    示例: sessionId=xxx;_login_mobile_=xxx;_login_user_id_=xxx#http://127.0.0.1:1080
    多账号用 & 分隔

2. 如何抓取 sfsyUrl:
    - 前置条件: 需要先用手机号登录顺丰小程序以及APP
    方法A: 这个网站用微信扫码登录即可获取
      https://sm.9999.blue/
    方法B: 手动抓包
      ① 微信打开「顺丰速运」小程序
      ② 使用抓包工具（如 HttpCanary）抓取请求
      ③ 找到 Cookie 中的 sessionId / _login_mobile_ / _login_user_id_ 字段
      ④ 拼接为 sessionId=xxx;_login_mobile_=xxx;_login_user_id_=xxx
      ⑤ 将拼接后的值设为环境变量 sfsyUrl
    注意: CK 过期后需重新抓取

3. 代理设置 (可选，不用代理就不用管):
    - 固定代理：填在 sfsyUrl 账号变量中 CK 最后，用 # 分隔
    - 动态代理：添加环境变量 SF_PROXY_API_URL = 你的代理提取链接
    - 代理类型：添加环境变量 SF_PROXY_TYPE = http 或 socks5 (默认 socks5)

4. 暗号变量 (sfsyah, 可选):
    格式: 每行一个暗号，按日期顺序对应（空行=从API自动获取）
    不设置则全部自动从API获取答案

5. 任务开关与并发:
    在下方「配置区域」修改
    ENABLE_DAILY_TASK    = True/False  日常积分任务
    ENABLE_ANNIVERSARY   = True/False  33周年庆活动
    ENABLE_LOTTERY       = True/False  33周年庆抽奖
    ENABLE_POINT_EXCHANGE = True/False  积分兑换抽勋章次数
    ENABLE_MEMBER_DAY    = True/False  会员日活动 (每月26-28号)
    CONCURRENT_NUM       = 1~20       并发数量

6. 推送通知 (可选):
    环境变量 SFSY_PUSH = 1 开启推送 (默认), 0 关闭
    依赖青龙自带的 notify.py 模块

定时规则建议 (Cron):
11 6-18/3 * * *

From: 爱学习的呆子 (原作者) | YaoHuo8648 (二改)
Email: zheyizzf@188.com
Update: 2026.03.28
"""

import hashlib
import json
import os
import random
import time
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from urllib.parse import unquote, urlparse, parse_qs, quote as url_encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

PUSH_SWITCH = os.getenv("SFSY_PUSH", "1")
try:
    from notify import send as notify_send
    print("✅ 成功加载青龙notify推送模块")
except ImportError:
    print("⚠️ 未找到notify模块，推送功能不可用（本地运行可忽略）")
    notify_send = None

# ==================== 配置区域 ====================
# 功能开关 (True=开启, False=关闭)
ENABLE_DAILY_TASK = True         # 日常积分任务 (签到+做任务+领积分)
ENABLE_ANNIVERSARY = True        # 33周年庆活动 (做任务+对暗号+抽勋章)
ENABLE_LOTTERY = True            # 33周年庆抽奖 (集齐5勋章抽大奖)
ENABLE_POINT_EXCHANGE = True     # 积分兑换抽勋章次数 (10积分兑1次)
ENABLE_MEMBER_DAY = True         # 会员日活动 (每月26-28号自动执行)
CONCURRENT_NUM = 1               # 并发数量 (1~20)

# 周年活动配置
ACTIVITY_CODE = "ANNIVERSARY_2026"
TOKEN = 'wwesldfs29aniversaryvdld29'
inviteId = []
SYS_CODE = 'MCS-MIMP-CORE'

# 暗号环境变量
GUESS_ANSWER_ENV = 'sfsyah'

# 5种勋章
CARD_CURRENCIES = ['FA_CAI', 'GAN_FAN', 'GAO_YA', 'KAI_XIANG', 'DAN_GAO']
CARD_NAMES = {
    'FA_CAI': '马上有钱', 'GAN_FAN': '全能吃货', 'GAO_YA': '高雅人士',
    'KAI_XIANG': '拆箱达人', 'DAN_GAO': '甜度超标',
}

# 日常任务跳过列表
DAILY_SKIP_TASKS = [
    '用行业模板寄件下单', '用积分兑任意礼品', '参与积分活动',
    '每月累计寄件', '完成每月任务', '去使用AI寄件',
]

# 周年活动跳过任务类型
ANNIVERSARY_SKIP_TASK_TYPES = [
    'BUY_ADD_VALUE_SERVICE_PACKET', 'SEND_INTERNATIONAL_PACKAGE',
    'LOOK_BIG_PACKAGE_GET_CASH', 'SEND_SUCCESS_RECALL',
    'CHARGE_NEW_EXPRESS_CARD', 'CHARGE_COLLECT_ALL',
    'OPEN_FAMILY_HOME_MUTUAL', 'BUY_ANNIVERSARY_LIMITED_PACKET',
]

# 会员日跳过任务类型
MEMBER_DAY_SKIP_TASK_TYPES = [
    'SEND_SUCCESS', 'INVITEFRIENDS_PARTAKE_ACTIVITY', 'OPEN_SVIP',
    'OPEN_NEW_EXPRESS_CARD', 'OPEN_FAMILY_CARD', 'CHARGE_NEW_EXPRESS_CARD',
    'INTEGRAL_EXCHANGE',
]

# 代理配置
PROXY_API_URL = os.getenv("SF_PROXY_API_URL", "")
PROXY_TYPE = os.getenv("SF_PROXY_TYPE", "socks5")
PROXY_TIMEOUT = 15
MAX_PROXY_RETRIES = 5
REQUEST_RETRY_COUNT = 3
PROXY_RETRY_DELAY = 2
PROXY_CONTEXT = {'last_fetch_ts': 0}
PROXY_LOCK = threading.Lock()
print_lock = Lock()
# =================================================


class Logger:
    def __init__(self):
        self.messages: List[str] = []
        self.lock = Lock()

    def _log(self, icon: str, msg: str):
        line = f"{icon} {msg}"
        with print_lock:
            print(line)
        with self.lock:
            self.messages.append(line)

    def info(self, msg): self._log('📝', msg)
    def success(self, msg): self._log('✅', msg)
    def warning(self, msg): self._log('⚠️', msg)
    def error(self, msg): self._log('❌', msg)
    def task(self, msg): self._log('🎯', msg)
    def medal(self, msg): self._log('🏅', msg)
    def points(self, pts, prefix="当前积分"): self._log('💰', f"{prefix}: 【{pts}】")


# ==================== 代理管理器 ====================
def _log_global(msg: str):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


def _build_proxy_url(ip: str, port: int, username: str = "", password: str = "") -> str:
    """构建标准代理URL，认证信息自动URL编码"""
    if username and password:
        safe_user = url_encode(username, safe='')
        safe_pass = url_encode(password, safe='')
        return f"{PROXY_TYPE}://{safe_user}:{safe_pass}@{ip}:{port}"
    return f"{PROXY_TYPE}://{ip}:{port}"


def parse_proxy_response(text: str) -> Optional[Tuple[str, str]]:
    """解析代理API响应，返回(代理URL, 显示用字符串)，支持JSON和纯文本格式"""
    text = text.strip()
    try:
        data = json.loads(text)
        def extract(d: dict) -> Optional[Tuple[str, str]]:
            if 'ip' not in d or 'port' not in d:
                return None
            ip, port = str(d['ip']), int(d['port'])
            user = str(d.get('account', d.get('user', '')) or '')
            pwd = str(d.get('password', d.get('pass', '')) or '')
            url = _build_proxy_url(ip, port, user, pwd)
            display = f"{ip}:{port}" + (" (认证)" if user else "")
            return url, display
        if isinstance(data, dict):
            if 'ip' in data and 'port' in data:
                return extract(data)
            if 'data' in data:
                pd = data['data']
                if isinstance(pd, dict) and 'list' in pd:
                    pl = pd['list']
                    if isinstance(pl, list) and pl:
                        return extract(pl[0])
                if isinstance(pd, list) and pd:
                    return extract(pd[0])
                if isinstance(pd, dict) and 'ip' in pd:
                    return extract(pd)
            if 'result' in data:
                r = data['result']
                if isinstance(r, dict) and 'ip' in r:
                    return extract(r)
    except (json.JSONDecodeError, ValueError):
        pass
    if ':' in text:
        segments = text.split()
        addr_parts = segments[0].split(':')
        if len(addr_parts) == 2 and addr_parts[1].isdigit():
            ip, port = addr_parts[0], int(addr_parts[1])
            user = segments[1] if len(segments) > 1 else ""
            pwd = segments[2] if len(segments) > 2 else ""
            url = _build_proxy_url(ip, port, user, pwd)
            display = f"{ip}:{port}" + (" (认证)" if user else "")
            return url, display
    return None


def get_api_proxy() -> Optional[Tuple[Dict[str, str], str]]:
    """从API获取代理，返回(代理字典, 显示用字符串)"""
    if not PROXY_API_URL:
        return None
    with PROXY_LOCK:
        elapsed = time.time() - PROXY_CONTEXT['last_fetch_ts']
        if elapsed < 3:
            time.sleep(3 - elapsed)
        for i in range(MAX_PROXY_RETRIES):
            try:
                resp = requests.get(PROXY_API_URL, timeout=10)
                if resp.status_code == 200:
                    result = parse_proxy_response(resp.text)
                    if result:
                        proxy_url, display = result
                        PROXY_CONTEXT['last_fetch_ts'] = time.time()
                        _log_global(f"✅ 代理获取成功: {display}")
                        return {'http': proxy_url, 'https': proxy_url}, display
                _log_global(f"⚠️ 第{i+1}次代理格式无效")
            except Exception as e:
                _log_global(f"⚠️ 第{i+1}次获取代理异常: {str(e)[:80]}")
            if i < MAX_PROXY_RETRIES - 1:
                time.sleep(PROXY_RETRY_DELAY)
        PROXY_CONTEXT['last_fetch_ts'] = time.time()
        _log_global(f"❌ 代理获取失败：已重试{MAX_PROXY_RETRIES}次")
        return None


def parse_fixed_proxy(fixed_proxy: str) -> Optional[Dict[str, str]]:
    """解析固定代理字符串为代理字典"""
    if not fixed_proxy:
        return None
    if '://' not in fixed_proxy:
        fixed_proxy = f'{PROXY_TYPE}://{fixed_proxy}'
    return {'http': fixed_proxy, 'https': fixed_proxy}


# ==================== HTTP客户端 ====================
class SFHttpClient:
    def __init__(self, fixed_proxy: str = ""):
        self.session = requests.Session()
        self.session.verify = False
        self.proxy_display = '无代理'
        self._setup_proxy(fixed_proxy)
        self.headers = {
            'Host': 'mcs-mimp-web.sf-express.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254173b) XWEB/19027',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'channel': 'xcxpart',
            'platform': 'MINI_PROGRAM',
            'accept-language': 'zh-CN,zh;q=0.9',
        }

    def _setup_proxy(self, fixed_proxy: str):
        if fixed_proxy:
            proxy_dict = parse_fixed_proxy(fixed_proxy)
            if proxy_dict:
                self.session.proxies = proxy_dict
                display = fixed_proxy
                if '@' in fixed_proxy:
                    parts = fixed_proxy.split('@')
                    display = f"***@{parts[-1]}"
                self.proxy_display = display
                return
        result = get_api_proxy()
        if result:
            self.session.proxies = result[0]
            self.proxy_display = result[1]

    def _generate_sign(self) -> Dict[str, str]:
        timestamp = str(int(round(time.time() * 1000)))
        data = f'token={TOKEN}&timestamp={timestamp}&sysCode={SYS_CODE}'
        signature = hashlib.md5(data.encode()).hexdigest()
        return {'syscode': SYS_CODE, 'timestamp': timestamp, 'signature': signature}

    def request(self, url: str, data: Optional[Dict] = None) -> Optional[Dict]:
        proxy_retry_count = 0
        retry_count = 0
        while proxy_retry_count < MAX_PROXY_RETRIES:
            sign_data = self._generate_sign()
            headers = {**self.headers, **sign_data}
            try:
                resp = self.session.post(url, headers=headers, json=data or {}, timeout=PROXY_TIMEOUT)
                resp.raise_for_status()
                try:
                    result = resp.json()
                    if result is not None:
                        return result
                except (json.JSONDecodeError, ValueError):
                    pass
                retry_count += 1
                if retry_count < REQUEST_RETRY_COUNT:
                    time.sleep(2)
                    continue
                return None
            except requests.exceptions.RequestException as e:
                retry_count += 1
                error_str = str(e)
                if 'ProxyError' in error_str or 'SSLError' in error_str or 'ConnectionError' in error_str:
                    proxy_retry_count += 1
                    if proxy_retry_count < MAX_PROXY_RETRIES:
                        result = get_api_proxy()
                        if result:
                            self.session.proxies = result[0]
                            self.proxy_display = result[1]
                        retry_count = 0
                    time.sleep(2)
                    continue
                if retry_count < REQUEST_RETRY_COUNT:
                    time.sleep(2)
                    continue
                return None
            except Exception:
                return None
        return None

    def request_app(self, url: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """APP平台请求"""
        original = self.headers.get('platform', 'MINI_PROGRAM')
        self.headers['platform'] = 'SFAPP'
        try:
            return self.request(url, data)
        finally:
            self.headers['platform'] = original

    def login(self, url: str) -> Tuple[bool, str, str]:
        try:
            decoded = unquote(url)
            if decoded.startswith('sessionId=') or '_login_mobile_=' in decoded:
                cookie_dict = {}
                for item in decoded.split(';'):
                    item = item.strip()
                    if '=' in item:
                        k, v = item.split('=', 1)
                        cookie_dict[k] = v
                for k, v in cookie_dict.items():
                    self.session.cookies.set(k, v, domain='mcs-mimp-web.sf-express.com')
                user_id = cookie_dict.get('_login_user_id_', '')
                phone = cookie_dict.get('_login_mobile_', '')
                return (True, user_id, phone) if phone else (False, '', '')
            else:
                self.session.get(decoded, headers=self.headers, timeout=PROXY_TIMEOUT)
                cookies = self.session.cookies.get_dict()
                user_id = cookies.get('_login_user_id_', '')
                phone = cookies.get('_login_mobile_', '')
                return (True, user_id, phone) if phone else (False, '', '')
        except Exception:
            return False, '', ''


# ==================== 日常积分任务执行器 ====================
class DailyTaskExecutor:
    def __init__(self, http: SFHttpClient, logger: Logger, user_id: str):
        self.http = http
        self.logger = logger
        self.user_id = user_id
        self.total_points = 0
        self.taskId = ""
        self.taskCode = ""
        self.strategyId = 0
        self.title = ""
        self.point = 0

    @staticmethod
    def generate_device_id() -> str:
        result = ''
        for char in 'xxxxxxxx-xxxx-xxxx':
            result += random.choice('abcdef0123456789') if char == 'x' else char
        return result

    def _extract_task_id_from_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if '_ug_view_param' in params:
                ug_params = json.loads(unquote(params['_ug_view_param'][0]))
                if 'taskId' in ug_params:
                    return str(ug_params['taskId'])
            if url.startswith('com.sf-express://'):
                json_str = url.split('_ug_view_param=')[1]
                ug_params = json.loads(unquote(json_str))
                if 'taskId' in ug_params:
                    return str(ug_params['taskId'])
        except Exception:
            pass
        return ''

    def _set_task_attrs(self, task: Dict):
        self.taskId = str(task.get('taskId', ''))
        self.taskCode = str(task.get('taskCode', ''))
        self.strategyId = int(task.get('strategyId', 0))
        self.title = str(task.get('title', '未知任务'))
        self.point = int(task.get('point', 0))
        if not self.taskCode and 'buttonRedirect' in task:
            extracted = self._extract_task_id_from_url(task['buttonRedirect'])
            if extracted:
                self.taskCode = extracted

    def app_sign_in(self) -> Tuple[bool, str]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskSignPlusService~getUnFetchPointAndDiscount'
        resp = self.http.request_app(url, {})
        if resp and resp.get('success'):
            obj = resp.get('obj', [])
            if obj and isinstance(obj, list) and len(obj) > 0:
                names = [item.get('packetName', '未知') for item in obj]
                self.logger.success(f'[APP签到] 获得【{", ".join(names)}】')
            else:
                self.logger.info('[APP签到] 今日已签到')
            return True, ''
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        if '没有待领取礼包' in error_msg:
            time.sleep(1)
            resp2 = self.http.request_app(url, {})
            if resp2 and resp2.get('success'):
                obj2 = resp2.get('obj', [])
                if obj2 and isinstance(obj2, list) and len(obj2) > 0:
                    names = [item.get('packetName', '未知') for item in obj2]
                    self.logger.success(f'[APP签到] 二次领取【{", ".join(names)}】')
                else:
                    self.logger.info('[APP签到] 今日已签到，无待领取奖励')
                return True, ''
            self.logger.info('[APP签到] 今日已签到')
            return True, ''
        self.logger.error(f'[APP签到] 失败: {error_msg}')
        return False, error_msg

    def sign_in(self) -> Tuple[bool, str]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage'
        resp = self.http.request(url, {"comeFrom": "vioin", "channelFrom": "WEIXIN"})
        if resp and resp.get('success'):
            obj = resp.get('obj', {})
            count_day = obj.get('countDay', 0)
            packets = obj.get('integralTaskSignPackageVOList', [])
            if packets:
                self.logger.success(f'签到成功，获得【{packets[0].get("packetName", "未知")}】，累计签到【{count_day + 1}】天')
            else:
                self.logger.info(f'今日已签到，累计签到【{count_day + 1}】天')
            return True, ''
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        self.logger.error(f'签到失败: {error_msg}')
        return False, error_msg

    def get_task_list(self) -> List[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES'
        all_tasks = []
        seen = set()
        for ct in ['1', '2', '3', '4', '01', '02', '03', '04']:
            data = {'channelType': ct, 'deviceId': self.generate_device_id()}
            resp = self.http.request(url, data)
            if resp and resp.get('success') and resp.get('obj'):
                if ct == '1':
                    self.total_points = resp['obj'].get('totalPoint', 0)
                for task in resp['obj'].get('taskTitleLevels', []):
                    tc = task.get('taskCode', '')
                    if not tc and 'buttonRedirect' in task:
                        tc = self._extract_task_id_from_url(task['buttonRedirect'])
                        if tc:
                            task['taskCode'] = tc
                    if tc and tc not in seen:
                        seen.add(tc)
                        all_tasks.append(task)
        return all_tasks

    def execute_task(self) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonRoutePost/memberEs/taskRecord/finishTask'
        resp = self.http.request(url, {'taskCode': self.taskCode})
        return bool(resp and resp.get('success'))

    def receive_task_reward(self) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~fetchIntegral'
        data = {
            "strategyId": self.strategyId, "taskId": self.taskId,
            "taskCode": self.taskCode, "deviceId": self.generate_device_id()
        }
        resp = self.http.request(url, data)
        if resp and resp.get('success'):
            self.logger.success(f'领取奖励: {self.title}')
            return True
        return False

    def get_welfare_list(self) -> List[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberGoods~mallGoodsLifeService~list'
        data = {"memGrade": 3, "categoryCode": "SHTQ", "showCode": "SHTQWNTJ"}
        resp = self.http.request(url, data)
        if resp and resp.get('success'):
            result = []
            for module in resp.get('obj', []):
                for goods in module.get('goodsList', []):
                    if goods.get('exchangeStatus') == 1:
                        result.append({
                            'goodsNo': goods.get('goodsNo'),
                            'goodsName': goods.get('goodsName'),
                            'showName': goods.get('showName', ''),
                        })
            return result
        return []

    def receive_welfare(self, goods_no: str, goods_name: str) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberGoods~pointMallService~createOrder'
        data = {
            "from": "Point_Mall", "orderSource": "POINT_MALL_EXCHANGE",
            "goodsNo": goods_no, "quantity": 1, "taskCode": self.taskCode
        }
        resp = self.http.request(url, data)
        if resp and resp.get('success'):
            self.logger.success(f'领取特权: {goods_name}')
            return True
        return False

    def handle_welfare_task(self) -> bool:
        welfare_list = self.get_welfare_list()
        if not welfare_list:
            return False
        for w in welfare_list:
            name = f"{w['showName']} - {w['goodsName']}" if w['showName'] else w['goodsName']
            if self.receive_welfare(w['goodsNo'], name):
                return True
            time.sleep(1)
        return False

    def run(self) -> Tuple[int, int]:
        self.logger.info('正在获取日常任务列表...')
        tasks = self.get_task_list()
        if not tasks:
            self.logger.error('获取任务列表失败')
            return 0, 0
        points_before = self.total_points
        self.logger.points(points_before, "执行前积分")
        for task in tasks:
            title = task.get('title', '未知')
            status = task.get('status')
            if status == 3:
                continue
            if title in DAILY_SKIP_TASKS:
                continue
            self._set_task_attrs(task)
            if not self.taskCode:
                if 'buttonRedirect' in task:
                    extracted = self._extract_task_id_from_url(task['buttonRedirect'])
                    if extracted:
                        self.taskCode = extracted
                    else:
                        continue
                else:
                    continue
            self.logger.task(f'发现任务: {title} (状态: {status})')
            if '领任意生活特权福利' in title:
                if self.handle_welfare_task():
                    time.sleep(2)
                    if self.execute_task():
                        time.sleep(2)
                        self.receive_task_reward()
                time.sleep(3)
                continue
            if status == 1:
                if '连签7天' in title and 'process' in task:
                    cur, tot = map(int, task['process'].split('/'))
                    if cur < tot:
                        self.logger.info(f'【{title}】进度: {task["process"]}')
                        continue
                if self.execute_task():
                    self.logger.success(f'[{title}] 提交成功')
                    time.sleep(2)
                    status = 2
                else:
                    continue
            if status == 2:
                if self.receive_task_reward():
                    continue
                if self.execute_task():
                    time.sleep(2)
                    self.receive_task_reward()
            time.sleep(3)
        tasks = self.get_task_list()
        points_after = self.total_points if tasks else points_before
        self.logger.points(points_after, "执行后积分")
        return points_before, points_after


# ==================== 33周年庆活动执行器 ====================
class AnniversaryExecutor:
    def __init__(self, http: SFHttpClient, logger: Logger, user_id: str = ''):
        self.http = http
        self.logger = logger
        self.user_id = user_id

    def get_activity_index(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026IndexService~index'
        resp = self.http.request(url, {})
        return resp.get('obj', {}) if resp and resp.get('success') else None

    def get_task_list(self) -> Optional[List[Dict]]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~activityTaskService~taskList'
        data = {"activityCode": ACTIVITY_CODE, "channelType": "MINI_PROGRAM"}
        resp = self.http.request(url, data)
        if resp and resp.get('success'):
            return resp.get('obj', [])
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        self.logger.error(f'获取活动任务列表失败: {error_msg}')
        return None

    def finish_task(self, task_code: str) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonRoutePost/memberEs/taskRecord/finishTask'
        resp = self.http.request(url, {"taskCode": task_code})
        return bool(resp and resp.get('success'))

    def fetch_tasks_reward(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026TaskService~fetchTasksReward'
        data = {"channelType": "MINI_PROGRAM", "activityCode": ACTIVITY_CODE}
        resp = self.http.request(url, data)
        return resp.get('obj', {}) if resp and resp.get('success') else None

    def get_card_status(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026CardService~cardStatus'
        resp = self.http.request(url, {})
        return resp.get('obj', {}) if resp and resp.get('success') else None

    def receive_vip_benefit(self) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberManage~memberEquity~commonEquityReceive'
        resp = self.http.request(url, {"key": "surprise_benefit"})
        if resp and resp.get('success'):
            self.logger.success('[领取寄件会员权益] 完成成功')
            return True
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        self.logger.warning(f'[领取寄件会员权益] 完成失败: {error_msg}')
        return False

    def claim_medal(self, batch: bool = False) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026CardService~claim'
        resp = self.http.request(url, {"batchClaim": batch})
        if resp and resp.get('success'):
            return resp.get('obj', {})
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        self.logger.error(f'抽勋章失败: {error_msg}')
        return None

    def give_countdown_chance(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026CardService~giveClaimChance'
        resp = self.http.request(url, {})
        if resp and resp.get('success'):
            return resp.get('obj', {})
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        self.logger.warning(f'领取倒计时奖励失败: {error_msg}')
        return None

    def get_guess_title_list(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026GuessService~titleList'
        resp = self.http.request(url, {})
        return resp.get('obj', {}) if resp and resp.get('success') else None

    def submit_guess_answer(self, answer: str, period: str = '') -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026GuessService~answer'
        data = {"answerInfo": answer}
        if period:
            data["period"] = period
        resp = self.http.request(url, data)
        if resp and resp.get('success'):
            obj = resp.get('obj', {})
            if isinstance(obj, dict) and obj.get('answerStatus') == 0:
                self.logger.warning('[对暗号] 答案错误')
                return None
            return obj
        return None

    def get_user_rest_integral(self) -> int:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~activityTaskService~getUserRestIntegral'
        resp = self.http.request(url, {})
        if resp and resp.get('success'):
            return resp.get('obj', 0)
        return 0

    def exchange_points_for_chance(self) -> bool:
        points = self.get_user_rest_integral()
        if points < 10:
            self.logger.warning(f'积分不足10（当前: {points}）')
            return False
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026TaskService~integralExchange'
        data = {"exchangeNum": 1, "activityCode": ACTIVITY_CODE}
        resp = self.http.request(url, data)
        if resp and resp.get('success'):
            self.logger.success('积分兑换成功，获得1次抽勋章次数')
            return True
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        self.logger.warning(f'积分兑换失败: {error_msg}')
        return False

    def do_guess_game(self) -> bool:
        self.logger.task('[对暗号赢免单] 开始...')
        guess_info = self.get_guess_title_list()
        if not guess_info:
            self.logger.warning('[对暗号] 获取题目失败')
            return False
        current_period = guess_info.get('currentPeriod', '')
        title_list = guess_info.get('guessTitleInfoList', [])
        if not title_list:
            return False
        title_list.sort(key=lambda x: x.get('period', ''))
        self.logger.info(f'[对暗号] 共 {len(title_list)} 天题目，当前: {current_period}')
        any_success = False
        for title in title_list:
            period = title.get('period', '')
            if title.get('answerStatus') == 1:
                self.logger.success(f'[对暗号] {period} 已作答: {title.get("answerInfo", "")}')
                any_success = True
                continue
            if period > current_period:
                continue
            answer = title.get('answerInfo', '')
            if not answer and period == current_period:
                env_answer = os.getenv(GUESS_ANSWER_ENV, '').strip()
                if env_answer:
                    answer = env_answer
                    self.logger.info(f'[对暗号] {period} 使用环境变量答案: {answer}')
            if not answer:
                self.logger.warning(f'[对暗号] {period} 无法获取答案（提示: {title.get("tip", "")}）')
                continue
            self.logger.info(f'[对暗号] {period} 提交: {answer}')
            result = self.submit_guess_answer(answer, period)
            if result is not None:
                time.sleep(1)
                verify = self.get_guess_title_list()
                if verify:
                    for t in verify.get('guessTitleInfoList', []):
                        if t.get('period') == period:
                            if t.get('answerStatus') == 1:
                                self.logger.success(f'[对暗号] {period} 验证通过')
                                any_success = True
                            else:
                                self.logger.warning(f'[对暗号] {period} 验证失败 (status={t.get("answerStatus")})')
                            break
                else:
                    any_success = True
            else:
                self.logger.warning(f'[对暗号] {period} 提交失败')
            time.sleep(1)
        return any_success

    def show_guess_results(self):
        guess_info = self.get_guess_title_list()
        if not guess_info:
            return
        title_list = guess_info.get('guessTitleInfoList', [])
        if not title_list:
            return
        title_list.sort(key=lambda x: x.get('period', ''))
        self.logger.info('=' * 20 + '  暗号开奖结果  ' + '=' * 20)
        for title in title_list:
            period = title.get('period', '')
            answer_status = title.get('answerStatus')
            answer_info = title.get('answerInfo', '')
            answer_analysis = title.get('answerAnalysis', '')
            award_list = title.get('awardList', [])
            if answer_status == 1:
                self.logger.success(f'日期: {period}  答案: {answer_info}')
                if answer_analysis:
                    self.logger.info(f'解析: {answer_analysis}')
                if award_list:
                    for award in award_list:
                        product_name = award.get('productName') or award.get('couponName', '未知奖品')
                        amount = award.get('amount', 1)
                        denomination = award.get('denomination', '')
                        limit_money = award.get('limitMoney', '')
                        desc = product_name
                        if denomination and limit_money:
                            desc = f'{denomination}折寄件券（最高抵扣{limit_money}元）' if '折' in product_name else product_name
                        coupon_no = award.get('couponNo', '')
                        coupon_info = f'（券号: {coupon_no}）' if coupon_no else ''
                        self.logger.info(f'  奖励: {desc} x{amount} {coupon_info}')
                else:
                    self.logger.info('暂无奖励信息')
            elif answer_info:
                self.logger.warning(f'日期: {period}  答案: {answer_info}（未作答）')
            else:
                self.logger.info(f'日期: {period}  提示: {title.get("tip", "")}（答案未公布）')
        self.logger.info('=' * 56)

    def do_invite(self):
        try:
            available_invites = [inv for inv in inviteId if inv != self.user_id]
            if not available_invites:
                return
            random_invite = random.choice(available_invites)
            url = "https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026IndexService~index"
            self.http.request(url, {"inviteType": 1, "inviteUserId": random_invite})
        except Exception as e:
            self.logger.error(f"邀请初始化异常: {str(e)}")

    def do_tasks(self, result: Dict):
        self.logger.info('获取周年活动任务列表...')
        tasks = self.get_task_list()
        if not tasks:
            return
        self.logger.info(f'共 {len(tasks)} 个活动任务')
        for task in tasks:
            name = task.get('taskName', '未知')
            task_type = task.get('taskType', '')
            task_code = task.get('taskCode', '')
            status = task.get('status')
            rest_finish = task.get('restFinishTime', 0)
            vt = task.get('virtualTokenNum', 0)
            if task_type == 'GUESS_GAME_TIP':
                if self.do_guess_game():
                    result['tasks_completed'] += 1
                continue
            if status == 3 or (status == 1 and rest_finish <= 0):
                can_receive = task.get('canReceiveTokenNum', 0)
                if can_receive > 0:
                    self.logger.info(f'[{name}] 待领取 {can_receive} 次抽勋章')
                continue
            if task_type in ANNIVERSARY_SKIP_TASK_TYPES:
                continue
            if task_type == 'INTEGRAL_EXCHANGE':
                if not ENABLE_POINT_EXCHANGE:
                    continue
                self.logger.task(f'[{name}] 尝试用积分兑换抽勋章次数...')
                if self.exchange_points_for_chance():
                    self.logger.success(f'[{name}] 积分兑换成功')
                    result['tasks_completed'] += 1
                continue
            if task_type == 'RECEIVE_VIP_BENEFIT':
                self.logger.task(f'[{name}] 尝试专用接口领取...')
                if self.receive_vip_benefit():
                    result['tasks_completed'] += 1
                continue
            if task_code:
                self.logger.task(f'[{name}] 完成任务')
                if self.finish_task(task_code):
                    self.logger.success(f'[{name}] 成功，+{vt}次抽勋章')
                    result['tasks_completed'] += 1
                time.sleep(1)

    def do_fetch_rewards(self):
        self.logger.info('领取活动任务奖励...')
        time.sleep(1)
        reward = self.fetch_tasks_reward()
        if reward:
            received = reward.get('receivedAccountList', [])
            if received:
                for item in received:
                    currency = item.get('currency', '')
                    amount = item.get('amount', 0)
                    task_type = item.get('taskType', '')
                    self.logger.success(f'领取奖励: {currency} x{amount} (来自: {task_type})')
            else:
                self.logger.info('无新奖励可领取')
            accrued = reward.get('accruedTaskAward', {})
            progress = accrued.get('currentProgress', 0)
            config = accrued.get('progressConfig', {})
            if config:
                milestones = ', '.join([f'{k}个任务得{v}次' for k, v in sorted(config.items(), key=lambda x: int(x[0]))])
                self.logger.info(f'累计完成任务数: {progress} (里程碑: {milestones})')

    def do_countdown_chance(self):
        self.logger.info('领取倒计时奖励...')
        time.sleep(1)
        resp = self.give_countdown_chance()
        if resp:
            if resp.get('todayCountdownChanceGiven'):
                received = resp.get('receivedAccountList', [])
                if received:
                    for item in received:
                        self.logger.success(f'倒计时奖励: {item.get("currency", "")} x{item.get("amount", 0)}')
                else:
                    self.logger.success('倒计时奖励已领取')
            else:
                self.logger.info('今日倒计时奖励未到领取时间')

    def do_claim_medals(self, result: Dict):
        card_status = self.get_card_status()
        if card_status:
            claim_balance = 0
            for acc in card_status.get('currentAccountList', []):
                if acc.get('currency') == 'CLAIM_CHANCE':
                    claim_balance = acc.get('balance', 0)
                    break
            self.logger.info(f'可抽勋章次数: {claim_balance}')
            medals = [f'{a.get("currency")}x{a.get("balance")}' for a in card_status.get('currentAccountList', [])
                      if a.get('currency') != 'CLAIM_CHANCE' and a.get('balance', 0) > 0]
            if medals:
                self.logger.info(f'已有勋章: {", ".join(medals)}')
            if claim_balance <= 0:
                self.logger.info('无抽勋章次数，跳过')
                return
        self.logger.info('开始抽勋章...')
        count = 0
        while count < 30:
            time.sleep(1)
            claim_result = self.claim_medal()
            if not claim_result:
                break
            received = claim_result.get('receivedAccountList', [])
            if not received:
                self.logger.info('没有抽到勋章或无抽取次数')
                break
            for item in received:
                c = item.get('currency', '未知')
                a = item.get('amount', 0)
                self.logger.medal(f'抽到: {c} x{a}')
                result['medals_detail'].append({'type': c, 'amount': a})
                result['medals_claimed'] += a
            count += 1
            bal = 0
            for acc in claim_result.get('currentAccountList', []):
                if acc.get('currency') == 'CLAIM_CHANCE':
                    bal = acc.get('balance', 0)
                    break
            self.logger.info(f'剩余抽取次数: {bal}')
            if bal <= 0:
                break
        self.logger.info(f'抽勋章完成，共抽取 {result["medals_claimed"]} 个')

    def run(self) -> Dict[str, Any]:
        result = {'tasks_completed': 0, 'medals_claimed': 0, 'medals_detail': []}
        self.do_invite()
        index_info = self.get_activity_index()
        if index_info:
            self.logger.info(f'活动时间: {index_info.get("acStartTime", "")} ~ {index_info.get("acEndTime", "")}')
            self.logger.info(f'历史寄件数: {index_info.get("sendNum", 0)}，累计支付: {index_info.get("payAmount", 0)}元')
        self.do_tasks(result)
        self.do_fetch_rewards()
        self.do_countdown_chance()
        self.do_claim_medals(result)
        self.show_guess_results()
        return result


# ==================== 33周年庆抽奖执行器 ====================
class LotteryExecutor:
    def __init__(self, http: SFHttpClient, phone: str, logger: Logger):
        self.http = http
        self.phone = phone
        self.masked = phone[:3] + "****" + phone[7:] if len(phone) >= 7 else phone
        self.logger = logger

    def get_card_status(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026CardService~cardStatus'
        resp = self.http.request(url, {})
        return resp.get('obj', {}) if resp and resp.get('success') else None

    def get_prize_pool(self) -> Optional[List]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026LotteryService~prizePool'
        resp = self.http.request(url, {})
        return resp.get('obj', []) if resp and resp.get('success') else None

    def prize_draw(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~anniversary2026LotteryService~prizeDraw'
        resp = self.http.request(url, {"currencyList": CARD_CURRENCIES})
        if resp and resp.get('success'):
            return resp.get('obj', {})
        error_msg = resp.get('errorMessage', '未知错误') if resp else '请求失败'
        self.logger.error(f'抽奖失败: {error_msg}')
        return None

    def get_card_balances(self, card_status: Dict) -> Dict[str, int]:
        return {acc.get('currency', ''): acc.get('balance', 0)
                for acc in card_status.get('currentAccountList', [])
                if acc.get('currency', '') in CARD_CURRENCIES}

    def format_card_status(self, balances: Dict[str, int]) -> str:
        return ' | '.join(f"{CARD_NAMES.get(c, c)}:{balances.get(c, 0)}" for c in CARD_CURRENCIES)

    def run(self) -> List[Dict]:
        prizes = []
        card_status = self.get_card_status()
        if not card_status:
            self.logger.error('获取勋章状态失败')
            return prizes
        balances = self.get_card_balances(card_status)
        self.logger.info(f'🎴 {self.format_card_status(balances)}')
        remain = card_status.get('remainCardSet', 0)
        self.logger.info(f'可抽大奖次数(5卡): {remain}')
        if not all(balances.get(c, 0) >= 1 for c in CARD_CURRENCIES):
            self.logger.warning('勋章不足5种，无法抽奖')
            return prizes
        pool = self.get_prize_pool()
        if pool:
            for p in pool:
                if p.get('shouldNum') == 5:
                    self.logger.info(f'5卡奖池: 已抽{p.get("lotteryNum", 0)}/{p.get("limitLotteryNum", 0)}次')
        draw_count = 0
        while all(balances.get(c, 0) >= 1 for c in CARD_CURRENCIES):
            draw_count += 1
            time.sleep(random.uniform(1, 2))
            result = self.prize_draw()
            if not result:
                break
            gift_name = result.get('giftBagName', '未知')
            gift_worth = result.get('giftBagWorth', 0)
            prizes.append({
                'phone': self.phone, 'masked_phone': self.masked,
                'gift_name': gift_name, 'gift_worth': gift_worth,
                'gift_code': result.get('giftBagCode', ''),
            })
            self.logger.success(f'第{draw_count}次 → 🎉 {gift_name} (价值{gift_worth}元)')
            time.sleep(1)
            card_status = self.get_card_status()
            if not card_status:
                break
            balances = self.get_card_balances(card_status)
            if not all(balances.get(c, 0) >= 1 for c in CARD_CURRENCIES):
                self.logger.info(f'{self.format_card_status(balances)} → 勋章不足，结束')
        self.logger.info(f'共抽奖 {draw_count} 次')
        return prizes


# ==================== 会员日活动执行器 ====================
class MemberDayExecutor:
    MAX_LEVEL = 8

    def __init__(self, http: SFHttpClient, logger: Logger, user_id: str):
        self.http = http
        self.logger = logger
        self.user_id = user_id
        self.black = False
        self.red_packet_map: Dict[int, int] = {}
        self.packet_threshold = 1 << (self.MAX_LEVEL - 1)

    def _check_black(self, error_message: str) -> bool:
        if '没有资格参与活动' in error_message:
            self.black = True
            self.logger.info('会员日任务风控')
            return True
        return False

    def get_index(self) -> Optional[Dict]:
        available = [inv for inv in inviteId if inv != self.user_id]
        invite_user_id = random.choice(available) if available else ''
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~memberDayIndexService~index'
        resp = self.http.request(url, {'inviteUserId': invite_user_id})
        if resp and resp.get('success'):
            return resp.get('obj', {})
        error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
        self.logger.info(f'查询会员日失败: {error_msg}')
        self._check_black(error_msg)
        return None

    def receive_invite_award(self, invite_user_id: str):
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~memberDayIndexService~receiveInviteAward'
        resp = self.http.request(url, {'inviteUserId': invite_user_id})
        if resp and resp.get('success'):
            product_name = resp.get('obj', {}).get('productName', '空气')
            self.logger.success(f'会员日邀请奖励: {product_name}')
        else:
            error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
            self.logger.info(f'领取会员日邀请奖励失败: {error_msg}')
            self._check_black(error_msg)

    def lottery(self) -> Optional[str]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~memberDayLotteryService~lottery'
        resp = self.http.request(url, {})
        if resp and resp.get('success'):
            product_name = resp.get('obj', {}).get('productName', '空气')
            self.logger.success(f'会员日抽奖: {product_name}')
            return product_name
        error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
        self.logger.info(f'会员日抽奖失败: {error_msg}')
        self._check_black(error_msg)
        return None

    def get_task_list(self) -> Optional[List[Dict]]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~activityTaskService~taskList'
        resp = self.http.request(url, {'activityCode': 'MEMBER_DAY', 'channelType': 'MINI_PROGRAM'})
        if resp and resp.get('success'):
            return resp.get('obj', [])
        error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
        self.logger.info(f'查询会员日任务失败: {error_msg}')
        self._check_black(error_msg)
        return None

    def finish_task(self, task: Dict) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberEs~taskRecord~finishTask'
        resp = self.http.request(url, {'taskCode': task['taskCode']})
        if resp and resp.get('success'):
            self.logger.success(f'完成会员日任务[{task["taskName"]}]')
            self.fetch_mix_task_reward(task)
            return True
        error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
        self.logger.info(f'完成会员日任务[{task["taskName"]}]失败: {error_msg}')
        self._check_black(error_msg)
        return False

    def fetch_mix_task_reward(self, task: Dict):
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~activityTaskService~fetchMixTaskReward'
        data = {'taskType': task['taskType'], 'activityCode': 'MEMBER_DAY', 'channelType': 'MINI_PROGRAM'}
        resp = self.http.request(url, data)
        if resp and resp.get('success'):
            self.logger.success(f'领取会员日任务[{task["taskName"]}]奖励')
        else:
            error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
            self.logger.info(f'领取会员日任务[{task["taskName"]}]奖励失败: {error_msg}')
            self._check_black(error_msg)

    def do_tasks(self):
        tasks = self.get_task_list()
        if not tasks:
            return
        for task in tasks:
            if self.black:
                return
            if task['status'] == 1:
                self.fetch_mix_task_reward(task)
        for task in tasks:
            if self.black:
                return
            if task['status'] == 2:
                if task['taskType'] in MEMBER_DAY_SKIP_TASK_TYPES:
                    continue
                for _ in range(task.get('restFinishTime', 0)):
                    if self.black:
                        return
                    self.finish_task(task)

    def red_packet_status(self):
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~memberDayPacketService~redPacketStatus'
        resp = self.http.request(url, {})
        if not (resp and resp.get('success')):
            error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
            self.logger.info(f'查询会员日合成失败: {error_msg}')
            self._check_black(error_msg)
            return
        for packet in resp.get('obj', {}).get('packetList', []):
            self.red_packet_map[packet['level']] = packet['count']
        for level in range(1, self.MAX_LEVEL):
            count = self.red_packet_map.get(level, 0)
            while count >= 2:
                self.red_packet_merge(level)
                count -= 2
        summary = [f"[{lv}级]X{ct}" for lv, ct in self.red_packet_map.items() if ct > 0]
        self.logger.info(f'会员日合成列表: {", ".join(summary)}')
        if self.red_packet_map.get(self.MAX_LEVEL):
            self.logger.success(f'会员日已拥有[{self.MAX_LEVEL}级]红包X{self.red_packet_map[self.MAX_LEVEL]}')
            self.red_packet_draw(self.MAX_LEVEL)
        else:
            remaining_needed = sum(
                1 << (int(lv) - 1) for lv, ct in self.red_packet_map.items()
                if ct > 0 and int(lv) < self.MAX_LEVEL
            )
            remaining = self.packet_threshold - remaining_needed
            self.logger.info(f'会员日距离[{self.MAX_LEVEL}级]红包还差: [1级]红包X{remaining}')

    def red_packet_merge(self, level: int):
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~memberDayPacketService~redPacketMerge'
        resp = self.http.request(url, {'level': level, 'num': 2})
        if resp and resp.get('success'):
            self.logger.success(f'会员日合成: [{level}级]红包X2 -> [{level + 1}级]红包')
            self.red_packet_map[level] -= 2
            self.red_packet_map[level + 1] = self.red_packet_map.get(level + 1, 0) + 1
        else:
            error_msg = resp.get('errorMessage', '无返回') if resp else '请求失败'
            self.logger.info(f'会员日合成[{level}级]红包失败: {error_msg}')
            self._check_black(error_msg)

    def red_packet_draw(self, level: int):
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~memberDayPacketService~redPacketDraw'
        resp = self.http.request(url, {'level': str(level)})
        if resp and resp.get('success'):
            coupon_names = [item['couponName'] for item in resp.get('obj', [])] or []
            self.logger.success(f'会员日提取[{level}级]红包: {", ".join(coupon_names) or "空气"}')
        else:
            error_msg = resp.get('errorMessage', '') if resp else '无返回'
            self.logger.info(f'会员日提取[{level}级]红包失败: {error_msg}')
            self._check_black(error_msg)

    def run(self) -> Dict[str, Any]:
        result = {'lottery_prizes': [], 'tasks_done': 0}
        index_info = self.get_index()
        if not index_info or self.black:
            return result
        available = [inv for inv in inviteId if inv != self.user_id]
        invite_user_id = random.choice(available) if available else ''
        if index_info.get('canReceiveInviteAward') and invite_user_id:
            self.receive_invite_award(invite_user_id)
        self.red_packet_status()
        lottery_num = index_info.get('lotteryNum', 0)
        self.logger.info(f'会员日可抽奖 {lottery_num} 次')
        for _ in range(lottery_num):
            if self.black:
                break
            prize = self.lottery()
            if prize:
                result['lottery_prizes'].append(prize)
        if not self.black:
            self.do_tasks()
        if not self.black:
            self.red_packet_status()
        return result


# ==================== 账号执行 ====================
def run_account(account_raw: str, index: int) -> Dict[str, Any]:
    logger = Logger()
    if '#' in account_raw and (':' in account_raw.split('#')[-1]):
        last_hash = account_raw.rfind('#')
        account_url = account_raw[:last_hash].strip()
        fixed_proxy = account_raw[last_hash + 1:].strip()
    else:
        account_url = account_raw
        fixed_proxy = ""
    http = SFHttpClient(fixed_proxy)
    login_success = False
    phone = ''
    user_id = ''
    for attempt in range(MAX_PROXY_RETRIES):
        if attempt > 0:
            http = SFHttpClient(fixed_proxy)
        success, user_id, phone = http.login(account_url)
        if success:
            login_success = True
            break
        time.sleep(2)
    if not login_success:
        logger.error(f'账号{index + 1} 登录失败')
        return {'success': False, 'phone': '', 'index': index,
                'points_before': 0, 'points_after': 0, 'points_earned': 0,
                'tasks_completed': 0, 'medals_claimed': 0, 'prizes': []}
    masked = phone[:3] + "****" + phone[7:] if len(phone) >= 7 else phone
    logger.success(f'账号{index + 1}: 【{masked}】登录成功 | 🌐 {http.proxy_display}')
    time.sleep(random.uniform(1, 3))
    result = {
        'success': True, 'phone': phone, 'index': index,
        'points_before': 0, 'points_after': 0, 'points_earned': 0,
        'tasks_completed': 0, 'medals_claimed': 0, 'medals_detail': [],
        'prizes': [],
    }
    # 日常积分任务
    if ENABLE_DAILY_TASK:
        logger.info('━━━ 日常积分任务 ━━━')
        daily = DailyTaskExecutor(http, logger, user_id)
        daily.app_sign_in()
        time.sleep(1)
        sign_ok, sign_err = daily.sign_in()
        if not sign_ok and '活动太火爆' in sign_err:
            for retry in range(3):
                logger.warning(f'签到IP问题，重试({retry + 1}/3)...')
                time.sleep(2)
                http = SFHttpClient(fixed_proxy)
                s, user_id, phone = http.login(account_url)
                if s:
                    daily.http = http
                    daily.user_id = user_id
                    sign_ok, sign_err = daily.sign_in()
                    if sign_ok or '活动太火爆' not in sign_err:
                        break
        pb, pa = daily.run()
        result['points_before'] = pb
        result['points_after'] = pa
        result['points_earned'] = pa - pb
    # 33周年庆活动
    if ENABLE_ANNIVERSARY:
        logger.info('━━━ 33周年庆活动 ━━━')
        ann = AnniversaryExecutor(http, logger, user_id)
        ann_result = ann.run()
        result['tasks_completed'] = ann_result['tasks_completed']
        result['medals_claimed'] = ann_result['medals_claimed']
        result['medals_detail'] = ann_result['medals_detail']
    # 33周年庆抽奖
    if ENABLE_LOTTERY:
        logger.info('━━━ 33周年庆抽奖 ━━━')
        lot = LotteryExecutor(http, phone, logger)
        result['prizes'] = lot.run()
    # 会员日活动 (每月26-28号)
    if ENABLE_MEMBER_DAY:
        current_day = datetime.now().day
        if 26 <= current_day <= 28:
            logger.info('━━━ 会员日活动 ━━━')
            md = MemberDayExecutor(http, logger, user_id)
            md_result = md.run()
            result['member_day_prizes'] = md_result.get('lottery_prizes', [])
        else:
            logger.info('⏰ 未到会员日(26-28号)，跳过')
    return result


# ==================== 主程序 ====================
def main():
    env_name = 'sfsyUrl'
    env_value = os.getenv(env_name)
    if not env_value:
        print(f"❌ 未找到环境变量 {env_name}")
        return
    account_list = [u.strip() for u in env_value.split('&') if u.strip()]
    if not account_list:
        print(f"❌ 环境变量 {env_name} 为空")
        return
    guess_answer = os.getenv(GUESS_ANSWER_ENV, '')
    if guess_answer:
        lines = [a.strip() for a in guess_answer.strip().split('\n') if a.strip()]
        print(f"🔑 已设置暗号 {len(lines)} 个")
    random.shuffle(account_list)
    task_map = {
        "日常任务": ENABLE_DAILY_TASK,
        "周年活动": ENABLE_ANNIVERSARY,
        "周年抽奖": ENABLE_LOTTERY,
        "会员日": ENABLE_MEMBER_DAY,
    }
    enabled = [f"{k}✓" for k, v in task_map.items() if v]
    print("=" * 60)
    print("🎉 顺丰速运自动任务 v1.0.8")
    print(f"👨‍💻 原作者: 爱学习的呆子 | 二改: YaoHuo8648")
    print(f"📱 共 {len(account_list)} 个账号")
    print(f"⚙️ 并发: {CONCURRENT_NUM} | 📋 {' '.join(enabled)}")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if PROXY_API_URL:
        _log_global(f"🔌 代理已开启: {PROXY_API_URL[:40]}...")
    print("=" * 60)
    all_results = []
    if CONCURRENT_NUM <= 1:
        for idx, raw in enumerate(account_list):
            result = run_account(raw, idx)
            all_results.append(result)
            if idx < len(account_list) - 1:
                time.sleep(2)
    else:
        with ThreadPoolExecutor(max_workers=CONCURRENT_NUM) as pool:
            futures = {pool.submit(run_account, raw, idx): idx for idx, raw in enumerate(account_list)}
            for f in as_completed(futures):
                all_results.append(f.result())
    all_results.sort(key=lambda x: x['index'])
    # 汇总
    print(f"\n{'='*70}")
    print("📊 执行汇总")
    print("=" * 70)
    total_earned = 0
    total_draws = 0
    all_prizes = []
    for r in all_results:
        phone = r['phone'][:3] + "****" + r['phone'][7:] if r.get('phone') and len(r['phone']) >= 7 else r.get('phone', '未登录')
        earned = r.get('points_earned', 0)
        total_earned += earned
        prizes = r.get('prizes', [])
        total_draws += len(prizes)
        all_prizes.extend(prizes)
        medals = r.get('medals_claimed', 0)
        detail = ', '.join(f"{d['type']}x{d['amount']}" for d in r.get('medals_detail', [])) or ''
        if not r['success']:
            print(f"❌ {phone}: 登录失败")
        else:
            parts = [f"积分+{earned}"]
            if medals > 0:
                parts.append(f"勋章+{medals}({detail})")
            if prizes:
                parts.append(f"奖品: {', '.join(p['gift_name'] for p in prizes)}")
            md_prizes = r.get('member_day_prizes', [])
            if md_prizes:
                parts.append(f"会员日: {', '.join(md_prizes)}")
            print(f"✅ {phone}: {' | '.join(parts)}")
    print("-" * 70)
    print(f"📱 总账号: {len(all_results)} | 💰 总积分+{total_earned} | 🎲 总抽奖: {total_draws}次")
    if all_prizes:
        total_worth = sum(p['gift_worth'] for p in all_prizes)
        print(f"🎁 总奖品: {len(all_prizes)}个 | 💰 总价值: {total_worth}元")
        gift_count = {}
        for p in all_prizes:
            gift_count[p['gift_name']] = gift_count.get(p['gift_name'], 0) + 1
        print(f"📋 奖品: {', '.join(f'{n}x{c}' for n, c in sorted(gift_count.items(), key=lambda x: -x[1]))}")
    print("=" * 70)
    print("🎊 执行完成!")
    push_lines = []
    for r in all_results:
        phone = r['phone'][:3] + "****" + r['phone'][7:] if r.get('phone') and len(r['phone']) >= 7 else r.get('phone', '未登录')
        if not r['success']:
            push_lines.append(f"❌ {phone}: 登录失败")
        else:
            earned = r.get('points_earned', 0)
            medals = r.get('medals_claimed', 0)
            detail = ', '.join(f"{d['type']}x{d['amount']}" for d in r.get('medals_detail', [])) or ''
            prizes = r.get('prizes', [])
            parts = [f"积分+{earned}"]
            if medals > 0:
                parts.append(f"勋章+{medals}({detail})")
            if prizes:
                parts.append(f"奖品: {', '.join(p['gift_name'] for p in prizes)}")
            md_prizes = r.get('member_day_prizes', [])
            if md_prizes:
                parts.append(f"会员日: {', '.join(md_prizes)}")
            push_lines.append(f"✅ {phone}: {' | '.join(parts)}")
    push_lines.append(f"📱 总账号: {len(all_results)} | 💰 总积分+{total_earned} | 🎲 总抽奖: {total_draws}次")
    if all_prizes:
        total_worth = sum(p['gift_worth'] for p in all_prizes)
        push_lines.append(f"🎁 总奖品: {len(all_prizes)}个 | 💰 总价值: {total_worth}元")
    notify_content = "\n".join(push_lines)
    if PUSH_SWITCH == "1" and notify_content:
        print("📤 准备推送消息...")
        try:
            if notify_send:
                notify_send("顺丰速运自动任务", notify_content)
                print("✅ 推送发送成功")
            else:
                print("⚠️ 未找到notify模块，无法推送")
        except Exception as e:
            print(f"❌ 推送发送失败: {e}")
    elif PUSH_SWITCH == "0":
        print("ℹ️ 推送开关未开启 (SFSY_PUSH=0)")


if __name__ == '__main__':
    main()
