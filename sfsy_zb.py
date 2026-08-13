"""
顺丰速运日常积分任务
Author: 爱学习的呆子
Version: 1.3.0
Date: 2026-04-04
"""

import hashlib
import json
import os
import sys
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import unquote, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import requests
import xml.etree.ElementTree as ET
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 禁用SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ==================== 代理相关配置常量 ====================
PROXY_TIMEOUT = 15  # 代理超时时间（秒）
MAX_PROXY_RETRIES = 5  # 最大代理重试次数
REQUEST_RETRY_COUNT = 3  # 请求重试次数


def xml_to_dict(element):
    """把 ElementTree 元素递归转成 dict；重复子标签自动聚为 list（兼容顺丰 XML 响应）。"""
    children = list(element)
    if not children:
        text = (element.text or "").strip()
        return text
    result = {}
    for child in children:
        val = xml_to_dict(child)
        tag = child.tag
        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(val)
        else:
            result[tag] = val
    return result


def parse_response_body(text: str):
    """顺丰部分老接口返回 XML（如 coupon/available/list），统一在此兼容：
    JSON 优先，失败且内容像 XML 时解析为 dict，并把 <obj> 单券包成 list 以兼容下游逻辑。
    """
    text = (text or "").strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    if text.startswith("<"):
        try:
            root = ET.fromstring(text)
            d = xml_to_dict(root)
            if isinstance(d, dict) and "obj" in d and not isinstance(d["obj"], list):
                d["obj"] = [d["obj"]]
            return d
        except ET.ParseError:
            return None
    return None

# ==================== 并发配置常量 ====================
CONCURRENT_NUM = int(os.getenv('SFBF', '1'))  # 并发数量，默认为1（串行），最大20
if CONCURRENT_NUM > 20:
    CONCURRENT_NUM = 20
    print(f'⚠️ 并发数量超过最大值20，已自动调整为20')
elif CONCURRENT_NUM < 1:
    CONCURRENT_NUM = 1
    print(f'⚠️ 并发数量小于1，已自动调整为1（串行模式）')

# 全局线程锁
print_lock = Lock()  # 用于保护打印输出


# ==================== 配置类 ====================
@dataclass
class Config:
    """全局配置"""
    APP_NAME: str = "顺丰速运"
    VERSION: str = "1.2.0"
    ENV_NAME: str = "sfsyUrl"
    PROXY_API_URL: str = os.getenv('SF_PROXY_API_URL', '')
    
    # 代理相关配置常量
    PROXY_TIMEOUT = 15  # 代理时间（秒）
    MAX_PROXY_RETRIES = 5  # 最大代理重试次数
    REQUEST_RETRY_COUNT = 3  # 请求重试次数
    
    # API签名配置
    TOKEN: str = 'wwesldfs29aniversaryvdld29'
    SYS_CODE: str = 'MCS-MIMP-CORE'
    
    # 顺丰红包大派送（每天免费抽奖一次）
    ENABLE_RED_PACKET: bool = True
    # 我的优惠券查询
    ENABLE_COUPON_QUERY: bool = True
    # 会员日活动（每月26-28号自动执行）
    ENABLE_MEMBER_DAY: bool = True
    
    # API 域名（搬自 sfsy.py）
    REDPACKET_API: str = "https://mcs-mimp-web.sf-express.com"       # 顺丰红包大派送API
    REDPACKET_ACTIVITY_CODE: str = "RED_PACKET_GAME_00001"           # 大派送活动代码
    COUPON_API: str = "https://mcs-mimp-web.sf-express.com"          # 优惠券查询API
    MEMBER_DAY_API: str = "https://mcs-mimp-web.sf-express.com"      # 会员日活动API
    
    # 任务跳过列表
    SKIP_TASKS: List[str] = None
    
    def __post_init__(self):
        if self.SKIP_TASKS is None:
            # 尝试直接提交所有任务，看看能否领取奖励
            # 原本跳过的任务：'用行业模板寄件下单'、'去新增一个收件偏好'
            self.SKIP_TASKS = ['用行业模板寄件下单','用积分兑任意礼品','参与积分活动','每月累计寄件','完成每月任务','去使用AI寄件']


# ==================== 日志系统 ====================
class Logger:
    """
    日志管理器 - 实现图片中的日志风格
    """
    
    # 日志图标
    ICONS = {
        'task_found': '🎯',      # 发现任务
        'task_skip': '⏭️',       # 跳过任务
        'task_complete': '✅',   # 任务完成
        'reward_get': '🎁',      # 奖励领取
        'info': '📝',            # 普通信息
        'success': '✨',         # 成功
        'error': '❌',           # 错误
        'warning': '⚠️',         # 警告
        'user': '👤',            # 用户信息
        'money': '💰',           # 积分/金币
        'gift': '🎁',            # 礼物
        'target': '🎯',          # 目标
    }
    
    def __init__(self):
        self.messages: List[str] = []
        self.current_account_msg: List[str] = []
        self.lock = Lock()  # 每个Logger实例独立的锁
    
    def _format_msg(self, icon: str, content: str) -> str:
        """格式化消息"""
        return f"{icon} {content}"
    
    def _safe_print(self, msg: str):
        """线程安全的打印"""
        with print_lock:
            print(msg)

    def raw(self, content: str):
        """裸打印：不加任何图标前缀，仍记录到消息列表（用于自定义前缀格式）。"""
        msg = content
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def task_found(self, task_name: str, status: int = 2):
        """发现任务"""
        msg = self._format_msg(self.ICONS['task_found'], f"发现任务: {task_name} (状态: {status})")
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def task_skip(self, task_name: str):
        """跳过任务"""
        msg = self._format_msg(self.ICONS['task_skip'], f"[{task_name}] 已跳过")
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def task_complete(self, task_name: str):
        """任务完成"""
        msg = self._format_msg(self.ICONS['task_complete'], f"[{task_name}] 提交成功")
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def reward_get(self, task_name: str):
        """奖励领取成功"""
        msg = self._format_msg(self.ICONS['reward_get'], f"[{task_name}] 奖励领取成功")
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def info(self, content: str):
        """普通信息"""
        msg = self._format_msg(self.ICONS['info'], content)
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def success(self, content: str):
        """成功信息"""
        msg = self._format_msg(self.ICONS['success'], content)
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def error(self, content: str):
        """错误信息"""
        msg = self._format_msg(self.ICONS['error'], content)
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def warning(self, content: str):
        """警告信息"""
        msg = self._format_msg(self.ICONS['warning'], content)
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def user_info(self, account_index: int, mobile: str):
        """用户信息"""
        msg = self._format_msg(self.ICONS['user'], f"账号{account_index}: 【{mobile}】登录成功")
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def points_info(self, points: int, prefix: str = "当前积分"):
        """积分信息"""
        msg = self._format_msg(self.ICONS['money'], f"{prefix}: 【{points}】")
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def coupon(self, content: str):
        """优惠券信息"""
        msg = self._format_msg(self.ICONS['gift'], content)
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def section(self, content: str):
        """分区标题"""
        msg = f"\n{'=' * 30} {content} {'=' * 30}"
        self._safe_print(msg)
        with self.lock:
            self.current_account_msg.append(msg)
            self.messages.append(msg)
    
    def warn(self, content: str):
        """警告信息（warning 的简写别名）"""
        self.warning(content)
    
    def reset_account_msg(self):
        """重置当前账号消息"""
        self.current_account_msg = []
    
    def get_all_messages(self) -> str:
        """获取所有消息"""
        return '\n'.join(self.messages)
    
    def get_account_messages(self) -> str:
        """获取当前账号消息"""
        return '\n'.join(self.current_account_msg)


# ==================== 代理管理器 ====================
class ProxyManager:
    """代理管理器"""
    
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.logger = Logger()
    
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """获取代理
        返回格式：{'http': 'http://ip:port', 'https': 'http://ip:port'}
        """
        try:
            if not self.api_url:
                print('⚠️ 未配置代理API地址，将不使用代理')
                return None
            
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                proxy_text = response.text.strip()
                if ':' in proxy_text:
                    # 构建代理URL
                    if proxy_text.startswith('http://') or proxy_text.startswith('https://'):
                        proxy = proxy_text
                    else:
                        proxy = f'http://{proxy_text}'
                    
                    # 隐藏认证信息用于显示（如果有的话）
                    display_proxy = proxy
                    if '@' in proxy:
                        # 格式: http://user:pass@ip:port
                        parts = proxy.split('@')
                        if len(parts) == 2:
                            display_proxy = f"http://***:***@{parts[1]}"
                    
                    print(f"✅ 成功获取代理: {display_proxy}")
                    return {'http': proxy, 'https': proxy}
            
            print(f'❌ 获取代理失败: {response.text}')
            return None
        except Exception as e:
            print(f'❌ 获取代理异常: {str(e)}')
            return None


# ==================== HTTP客户端 ====================
class SFHttpClient:
    """顺丰HTTP客户端"""
    
    def __init__(self, config: Config, proxy_manager: ProxyManager):
        self.config = config
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self.session.verify = False
        
        # 设置代理
        proxy = self.proxy_manager.get_proxy()
        if proxy:
            self.session.proxies = proxy
        
        # 默认请求头
        self.headers = {
            'Host': 'mcs-mimp-web.sf-express.com',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090551) XWEB/6945 Flue',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'sec-fetch-site': 'none',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'sec-fetch-dest': 'document',
            'accept-language': 'zh-CN,zh',
            'platform': 'MINI_PROGRAM',
        }
    
    def _generate_sign(self) -> Dict[str, str]:
        """生成API签名"""
        timestamp = str(int(round(time.time() * 1000)))
        data = f'token={self.config.TOKEN}&timestamp={timestamp}&sysCode={self.config.SYS_CODE}'
        signature = hashlib.md5(data.encode()).hexdigest()
        
        return {
            'sysCode': self.config.SYS_CODE,
            'timestamp': timestamp,
            'signature': signature
        }
    
    def request(
        self, 
        url: str, 
        method: str = 'POST', 
        data: Optional[Dict] = None,
        max_retries: int = REQUEST_RETRY_COUNT,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """发送HTTP请求，带双层重试机制
        
        Args:
            url: 请求URL
            method: 请求方法 GET/POST
            data: 请求数据
            max_retries: 最大重试次数
            
        Returns:
            响应JSON数据或None
        """
        # 更新签名
        sign_data = self._generate_sign()
        self.headers.update(sign_data)
        
        # 合并额外请求头（如活动专属 channel/sysCode/referer 等）
        req_headers = dict(self.headers)
        if extra_headers:
            req_headers.update({k: str(v) for k, v in extra_headers.items()})
        
        retry_count = 0
        proxy_retry_count = 0
        
        while proxy_retry_count < MAX_PROXY_RETRIES:
            try:
                # 如果请求重试次数达到2次，尝试切换代理
                if retry_count >= 2:
                    print('请求已失败2次，尝试切换代理IP')
                    new_proxy = self.proxy_manager.get_proxy()
                    if new_proxy:
                        self.session.proxies = new_proxy
                    else:
                        print('⚠️ 切换代理失败，无可用代理')
                    retry_count = 0  # 重置请求重试计数
                
                try:
                    if method.upper() == 'GET':
                        response = self.session.get(url, headers=req_headers, timeout=PROXY_TIMEOUT)
                    elif method.upper() == 'POST':
                        response = self.session.post(url, headers=req_headers, json=data or {}, timeout=PROXY_TIMEOUT)
                    else:
                        raise ValueError(f'不支持的请求方法: {method}')
                    
                    # 检查响应状态码
                    response.raise_for_status()
                    
                    try:
                        res = parse_response_body(response.text)
                        if res is None:
                            print(f'响应内容为空，正在重试 ({retry_count + 1}/{max_retries})')
                            retry_count += 1
                            time.sleep(2)
                            continue
                        return res
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f'JSON解析失败: {str(e)}, 响应内容: {response.text[:200]}')
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f'正在进行第{retry_count + 1}次重试...')
                            time.sleep(2)
                            continue
                        return None
                
                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    print(f'请求失败，正在重试 ({retry_count}/{max_retries}): {str(e)}')
                    # 如果是代理错误或SSL错误，增加代理重试计数
                    if 'ProxyError' in str(e) or 'SSLError' in str(e):
                        proxy_retry_count += 1
                        print(f'代理连接失败，尝试切换代理 ({proxy_retry_count}/{MAX_PROXY_RETRIES})')
                        if proxy_retry_count < MAX_PROXY_RETRIES:
                            new_proxy = self.proxy_manager.get_proxy()
                            if new_proxy:
                                self.session.proxies = new_proxy
                    time.sleep(2)
                    continue
            
            except Exception as e:
                print(f'请求发生异常: {str(e)}')
                proxy_retry_count += 1
                if proxy_retry_count < MAX_PROXY_RETRIES:
                    print(f'尝试切换代理 ({proxy_retry_count}/{MAX_PROXY_RETRIES})')
                    time.sleep(2)
                    continue
                else:
                    print('达到最大代理重试次数，返回None')
                    return None
        
        print('请求最终失败，返回None')
        return None
    
    def login(self, url: str, timeout: int = PROXY_TIMEOUT) -> tuple[bool, str, str]:
        """
        登录（兼容URL和CK格式）

        Args:
            url: 登录URL 或 CK字符串(sessionId=xxx;_login_mobile_=xxx;_login_user_id_=xxx)
            timeout: 超时时间（秒）

        Returns:
            tuple: (是否成功, user_id, 手机号)
        """
        try:
            decoded_input = unquote(url)
            if decoded_input.startswith('sessionId=') or '_login_mobile_=' in decoded_input:
                cookie_dict = {}
                for item in decoded_input.split(';'):
                    item = item.strip()
                    if '=' in item:
                        k, v = item.split('=', 1)
                        cookie_dict[k] = v
                for k, v in cookie_dict.items():
                    self.session.cookies.set(k, v, domain='mcs-mimp-web.sf-express.com')
                user_id = cookie_dict.get('_login_user_id_', '')
                phone = cookie_dict.get('_login_mobile_', '')
                if phone:
                    return True, user_id, phone
                else:
                    return False, '', ''
            else:
                decoded_url = unquote(url)
                self.session.get(decoded_url, headers=self.headers, timeout=timeout)
                cookies = self.session.cookies.get_dict()
                user_id = cookies.get('_login_user_id_', '')
                phone = cookies.get('_login_mobile_', '')
                if phone:
                    return True, user_id, phone
                else:
                    return False, '', ''
        except Exception as e:
            print(f'登录异常: {str(e)}')
            return False, '', ''


# ==================== 任务执行器 ====================
class TaskExecutor:
    """任务执行器"""
    
    def __init__(
        self, 
        http_client: SFHttpClient, 
        logger: Logger,
        config: Config,
        user_id: str
    ):
        self.http = http_client
        self.logger = logger
        self.config = config
        self.user_id = user_id
        self.total_points = 0
        
        # 任务相关属性
        self.taskId = ""
        self.taskCode = ""
        self.strategyId = ""
        self.title = ""
    
    @staticmethod
    def generate_device_id(characters: str = 'abcdef0123456789') -> str:
        """生成设备ID"""
        result = ''
        for char in 'xxxxxxxx-xxxx-xxxx':
            if char == 'x':
                result += random.choice(characters)
            else:
                result += char
        return result
    
    def _extract_task_id_from_url(self, url: str) -> str:
        """从URL中提取taskId"""
        try:
            from urllib.parse import parse_qs, urlparse, unquote
            import json
            
            # 处理_ug_view_param参数
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            if '_ug_view_param' in params:
                ug_params = json.loads(unquote(params['_ug_view_param'][0]))
                if 'taskId' in ug_params:
                    return str(ug_params['taskId'])  # 确保返回字符串类型
                    
            # 如果URL是JSON格式的，尝试解析
            if url.startswith('com.sf-express://'):
                json_str = url.split('_ug_view_param=')[1]
                ug_params = json.loads(unquote(json_str))
                if 'taskId' in ug_params:
                    return str(ug_params['taskId'])  # 确保返回字符串类型
                    
        except Exception as e:
            self.logger.warning(f'从URL提取taskId失败: {e}')
            
        return ''
        
    def _set_task_attrs(self, task: Dict) -> None:
        """设置任务属性"""
        self.taskId = str(task.get('taskId', ''))  # 确保是字符串类型
        self.taskCode = str(task.get('taskCode', ''))  # 确保是字符串类型
        self.strategyId = int(task.get('strategyId', 0))  # 确保是整数类型
        self.title = str(task.get('title', '未知任务'))
        self.point = int(task.get('point', 0))  # 确保是整数类型
        
        # 如果taskCode为空，尝试从buttonRedirect中提取
        if not self.taskCode and 'buttonRedirect' in task:
            extracted_task_id = self._extract_task_id_from_url(task['buttonRedirect'])
            if extracted_task_id:
                self.taskCode = extracted_task_id
                self.logger.info(f'从buttonRedirect中提取到taskId: {self.taskCode}')
    
    def app_sign_in(self) -> tuple[bool, str]:
        """APP每日签到（使用getUnFetchPointAndDiscount接口触发签到+领取）
        
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskSignPlusService~getUnFetchPointAndDiscount'
        data = {}
        
        # 保存原有的platform头
        original_platform = self.http.headers.get('platform', 'MINI_PROGRAM')
        
        # 临时切换为APP平台
        self.http.headers['platform'] = 'SFAPP'
        
        try:
            response = self.http.request(url, data=data)
            if response and response.get('success'):
                obj = response.get('obj', [])
                
                # 响应是一个数组，包含待领取的奖励
                if obj and isinstance(obj, list) and len(obj) > 0:
                    total_points = 0
                    reward_names = []
                    for item in obj:
                        packet_name = item.get('packetName', '未知奖励')
                        detail_value = item.get('detailValue', '0')
                        reward_names.append(packet_name)
                        try:
                            total_points += int(detail_value)
                        except:
                            pass
                    
                    self.logger.success(f'[APP签到] 签到成功，获得【{", ".join(reward_names)}】')
                else:
                    self.logger.info(f'[APP签到] 今日已签到或无可领取奖励')
                
                return True, ''
            else:
                error_msg = response.get('errorMessage', '未知错误') if response else '请求失败'
                
                # 如果返回"没有待领取礼包"，等待1秒后再次调用接口
                if '没有待领取礼包' in error_msg:
                    self.logger.info(f'[APP签到] 检测到需要二次领取，等待1秒后重试...')
                    time.sleep(1)
                    
                    # 再次调用getUnFetchPointAndDiscount接口
                    response2 = self.http.request(url, data=data)
                    if response2 and response2.get('success'):
                        obj2 = response2.get('obj', [])
                        
                        if obj2 and isinstance(obj2, list) and len(obj2) > 0:
                            total_points = 0
                            reward_names = []
                            for item in obj2:
                                packet_name = item.get('packetName', '未知奖励')
                                detail_value = item.get('detailValue', '0')
                                reward_names.append(packet_name)
                                try:
                                    total_points += int(detail_value)
                                except:
                                    pass
                            
                            self.logger.success(f'[APP签到] 二次领取成功，获得【{", ".join(reward_names)}】')
                        else:
                            self.logger.info(f'[APP签到] 二次领取完成，但无可领取奖励')
                        
                        return True, ''
                    else:
                        error_msg2 = response2.get('errorMessage', '未知错误') if response2 else '请求失败'
                        self.logger.error(f'[APP签到] 二次领取失败: {error_msg2}')
                        return False, error_msg2
                else:
                    self.logger.error(f'[APP签到] 失败: {error_msg}')
                    return False, error_msg
        finally:
            # 恢复原有的platform头
            self.http.headers['platform'] = original_platform
    
    def query_total_points(self) -> int:
        """查询当前总积分（签到前基准用）"""
        try:
            url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES'
            data = {
                'channelType': '1',
                'deviceId': self.generate_device_id(),
            }
            response = self.http.request(url, data=data)
            if response and response.get('success') and response.get('obj'):
                return response['obj'].get('totalPoint', 0)
        except Exception as e:
            self.logger.error(f'查询积分失败: {e}')
        return 0
    
    def sign_in(self) -> tuple[bool, str]:
        """小程序每日签到
        
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage'
        data = {"comeFrom": "vioin", "channelFrom": "WEIXIN"}
        
        response = self.http.request(url, data=data)
        if response and response.get('success'):
            count_day = response.get('obj', {}).get('countDay', 0)
            packet_list = response.get('obj', {}).get('integralTaskSignPackageVOList', [])
            
            if packet_list:
                packet_name = packet_list[0].get('packetName', '未知奖励')
                self.logger.success(f'签到成功，获得【{packet_name}】，本周累计签到【{count_day + 1}】天')
            else:
                self.logger.info(f'[小程序签到] 今日已签到，本周累计签到【{count_day + 1}】天')
            return True, ''
        else:
            error_msg = response.get('errorMessage', '未知错误') if response else '请求失败'
            self.logger.error(f'签到失败: {error_msg}')
            return False, error_msg
    
    def new_sign_in(self) -> tuple[bool, str]:
        """签到日历（integralSignV2Service）
        
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralSignV2Service~sign'
        data = {}
        
        original_platform = self.http.headers.get('platform', 'MINI_PROGRAM')
        self.http.headers['platform'] = 'SFAPP'
        
        try:
            response = self.http.request(url, data=data)
            if response and response.get('success'):
                obj = response.get('obj', {})
                signed = obj.get('signed', False)
                day_count = obj.get('dayCount', 0)
                total_count = obj.get('totalCount', 0)
                award = obj.get('award', {})
                award_type = obj.get('awardType', '')
                award_num = obj.get('awardNum', 0)
                
                if signed and award:
                    gift_bag_name = award.get('giftBagName', '未知奖励')
                    self.logger.success(f'[签到日历] 签到成功，连续第{day_count}天，获得【{gift_bag_name}】')
                elif signed:
                    self.logger.info(f'[签到日历] 今日已签到，连续第{day_count}天')
                else:
                    self.logger.info(f'[签到日历] 签到完成')
                
                return True, ''
            else:
                error_msg = response.get('errorMessage', '未知错误') if response else '请求失败'
                self.logger.error(f'[签到日历] 失败: {error_msg}')
                return False, error_msg
        finally:
            self.http.headers['platform'] = original_platform
    
    def get_task_list(self) -> List[Dict]:
        """获取任务列表"""
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES'
        
        all_tasks = []
        task_codes_seen = set() 
        
        for channel_type in ['1', '2', '3', '4','01','02','03','04']:
            data = {
                'channelType': channel_type,
                'deviceId': self.generate_device_id(),
            }
            
            response = self.http.request(url, data=data)
            
            if response and response.get('success') and response.get('obj'):
                # 只在第一次请求时获取总积分
                if channel_type == '1':
                    self.total_points = response['obj'].get('totalPoint', 0)
                
                tasks = response['obj'].get('taskTitleLevels', [])
                
                # 去重添加任务
                for task in tasks:
                    task_code = task.get('taskCode')
                    task_title = task.get('title', '未知任务')
                    
                    # 尝试提取taskId
                    if 'buttonRedirect' in task:
                        extracted_id = self._extract_task_id_from_url(task['buttonRedirect'])
                        if extracted_id and not task_code:
                            task_code = extracted_id
                            task['taskCode'] = extracted_id
                    
                    # 如果taskCode为空，但能从buttonRedirect中提取到taskId，则使用提取的taskId
                    if not task_code and 'buttonRedirect' in task:
                        extracted_id = self._extract_task_id_from_url(task['buttonRedirect'])
                        if extracted_id:
                            task['taskCode'] = extracted_id
                            task_code = extracted_id
                    
                    # 如果taskCode仍然为空，则跳过
                    if not task_code:
                        continue
                        
                    # 检查是否已存在相同taskCode的任务
                    if task_code not in task_codes_seen:
                        task_codes_seen.add(task_code)
                        all_tasks.append(task)
            else:
                error_msg = response.get('errorMessage', '未知错误') if response else '请求失败'
                self.logger.warning(f'获取 channelType={channel_type} 的任务失败: {error_msg}')
        
        return all_tasks
    
    def execute_task(self) -> bool:
        """执行单个任务"""
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonRoutePost/memberEs/taskRecord/finishTask'
        data = {'taskCode': self.taskCode}
        
        response = self.http.request(url, data=data)
        if response and response.get('success'):
            return True
        return False
    
    def _update_points(self):
        """更新积分显示"""
        tasks = self.get_task_list()
        if tasks:
            self.logger.points_info(self.total_points, "当前积分")
    
    def receive_task_reward(self) -> bool:
        """领取任务奖励"""
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~fetchIntegral'
        data = {
            "strategyId": self.strategyId,
            "taskId": self.taskId,
            "taskCode": self.taskCode,
            "deviceId": self.generate_device_id()
        }
        
        response = self.http.request(url, data=data)
        if response:
            if response.get('success'):
                self.logger.success(f'成功领取任务奖励: {self.title}')
                return True
        return False
    
    def get_welfare_list(self) -> List[Dict]:
        """获取生活特权列表"""
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberGoods~mallGoodsLifeService~list'
        data = {
            "memGrade": 3,
            "categoryCode": "SHTQ",
            "showCode": "SHTQWNTJ"
        }
        
        response = self.http.request(url, data=data)
        if response and response.get('success'):
            obj_list = response.get('obj', [])
            # 收集所有可领取的特权
            welfare_list = []
            for module in obj_list:
                goods_list = module.get('goodsList', [])
                for goods in goods_list:
                    # exchangeStatus=1 表示可以领取
                    if goods.get('exchangeStatus') == 1:
                        welfare_list.append({
                            'goodsId': goods.get('goodsId'),
                            'goodsNo': goods.get('goodsNo'),
                            'goodsName': goods.get('goodsName'),
                            'showName': goods.get('showName', ''),
                            'id': goods.get('id')
                        })
            return welfare_list
        return []
    
    def receive_welfare(self, goods_no: str, goods_name: str, task_code: str) -> bool:
        """领取生活特权"""
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberGoods~pointMallService~createOrder'
        data = {
            "from": "Point_Mall",
            "orderSource": "POINT_MALL_EXCHANGE",
            "goodsNo": goods_no,
            "quantity": 1,
            "taskCode": task_code
        }
        
        response = self.http.request(url, data=data)
        if response and response.get('success'):
            order_no = response.get('obj', {}).get('orderNo', '')
            self.logger.success(f'成功领取生活特权: {goods_name} (订单号: {order_no})')
            return True
        else:
            error_msg = response.get('errorMessage', '未知错误') if response else '请求失败'
            self.logger.error(f'领取生活特权失败: {goods_name} - {error_msg}')
            return False
    
    def handle_welfare_task(self, task_title: str) -> bool:
        """处理领取生活特权任务"""
        self.logger.info('正在获取生活特权列表...')
        
        welfare_list = self.get_welfare_list()
        if not welfare_list:
            self.logger.warning('没有可领取的生活特权')
            return False
        
        self.logger.info(f'找到 {len(welfare_list)} 个可领取的生活特权')
        
        # 尝试领取第一个可用的特权
        for welfare in welfare_list:
            goods_no = welfare.get('goodsNo')
            goods_name = welfare.get('goodsName')
            show_name = welfare.get('showName')
            
            if not goods_no:
                continue
            
            display_name = f"{show_name} - {goods_name}" if show_name else goods_name
            
            # 使用任务的 taskCode
            if self.receive_welfare(goods_no, display_name, self.taskCode):
                return True
            
            # 如果领取失败,等待一下再尝试下一个
            time.sleep(1)
        
        return False
    
    def run_all_tasks(self) -> tuple[int, int]:
        """执行所有任务
        
        Returns:
            tuple: (执行前积分, 执行后积分)
        """
        print('-'*50)
        
        # 只在这里显示一次任务列表更新信息
        self.logger.info('正在获取任务列表...')
        tasks = self.get_task_list()
        if not tasks:
            self.logger.error('获取任务列表失败')
            return (0, 0)
        
        points_before = self.total_points
        self.logger.points_info(points_before, "任务前积分")
        
        for task in tasks:
            task_title = task.get('title', '未知任务')
            task_status = task.get('status')
            
            # 状态3表示已完成
            if task_status == 3:
                self.logger.success(f'{task_title} - 已完成')
                continue
            
            # 跳过特定任务
            if task_title in self.config.SKIP_TASKS:
                self.logger.task_skip(task_title)
                continue
            
            # 提取任务属性
            self._set_task_attrs(task)
            
            # 检查是否成功提取 taskCode
            if not self.taskCode:
                # 如果taskCode为空，尝试从buttonRedirect中提取
                if 'buttonRedirect' in task:
                    self.logger.info(f'尝试从buttonRedirect中提取taskCode: {task_title}')
                    extracted_task_id = self._extract_task_id_from_url(task['buttonRedirect'])
                    if extracted_task_id:
                        self.taskCode = extracted_task_id
                        self.logger.info(f'成功从buttonRedirect中提取到taskCode: {self.taskCode}')
                    else:
                        self.logger.warning(f'{task_title} - 无法从buttonRedirect提取taskCode，跳过')
                        continue
                else:
                    self.logger.warning(f'{task_title} - 无法提取taskCode，跳过')
                    continue
            
            # 发现任务
            self.logger.task_found(task_title, task_status)
            
            # 特殊任务处理 - 需要在状态判断之前处理
            if '领任意生活特权福利' in task_title:
                # 先处理生活特权领取
                if self.handle_welfare_task(task_title):
                    time.sleep(2)
                    # 然后执行任务提交
                    if self.execute_task():
                        self.logger.task_complete(task_title)
                        time.sleep(2)
                        # 领取奖励
                        if self.receive_task_reward():
                            self.logger.reward_get(task_title)
                            self._update_points()
                    else:
                        self.logger.warning(f'任务执行失败: {task_title}')
                else:
                    self.logger.warning(f'{task_title} - 无法完成,跳过')
                time.sleep(3)
                continue
            
            # 状态1表示需要先执行任务
            if task_status == 1:
                # 特殊处理连签7天任务
                if '连签7天' in task_title and 'process' in task:
                    current, total = map(int, task['process'].split('/'))
                    if current < total:
                        self.logger.info(f'【{task_title}】进度: {task["process"]}，还需{total - current}天')
                        continue
                
                if self.execute_task():
                    self.logger.task_complete(task_title)
                    time.sleep(2)
                    # 执行成功后，将状态更新为2（可领取奖励）
                    task_status = 2
                else:
                    self.logger.warning(f'任务执行失败: {task_title}')
                    continue
            
            # 状态2表示可领取奖励
            if task_status == 2:
                # 先尝试直接领取奖励
                if self.receive_task_reward():
                    self.logger.reward_get(task_title)
                    # 更新积分
                    self._update_points()
                    continue
                
                # 如果直接领取失败，尝试先执行任务再领取
                if self.execute_task():
                    self.logger.task_complete(task_title)
                    time.sleep(2)
                    # 再次尝试领取奖励
                    if self.receive_task_reward():
                        self.logger.reward_get(task_title)
                        self._update_points()
                else:
                    self.logger.warning(f'任务执行失败: {task_title}')
                continue
            
            time.sleep(3)
        
        # 获取最新积分
        tasks = self.get_task_list()
        points_after = self.total_points if tasks else points_before
        if tasks:
            self.logger.points_info(points_after, "执行后积分")
        
        return (points_before, points_after)


# ==================== 账号管理器 ====================
class AccountManager:
    """账号管理器"""
    
    def __init__(self, account_url: str, account_index: int, config: Config):
        self.account_url = account_url
        self.account_index = account_index + 1
        self.config = config
        self.logger = Logger()
        self.proxy_manager = ProxyManager(config.PROXY_API_URL)
        
        # 登录重试机制（参考顺丰代理.py的实现）
        self.login_success = False
        self.user_id = None
        self.phone = None
        self.http_client = None
        
        retry_count = 0
        while retry_count < MAX_PROXY_RETRIES and not self.login_success:
            try:
                # 每次重试都重新获取代理和创建HTTP客户端
                self.http_client = SFHttpClient(config, self.proxy_manager)
                
                # 尝试登录（带超时）
                success, self.user_id, self.phone = self.http_client.login(account_url)
                
                if success:
                    masked_phone = self.phone[:3] + "*" * 4 + self.phone[7:]
                    self.logger.user_info(self.account_index, masked_phone)
                    self.login_success = True
                    break
                else:
                    if retry_count < MAX_PROXY_RETRIES - 1:
                        print(f'账号{self.account_index} 登录失败，尝试重新获取代理 ({retry_count + 1}/{MAX_PROXY_RETRIES})')
                        time.sleep(2)
            except Exception as e:
                print(f'账号{self.account_index} 登录异常: {str(e)[:100]}')
            
            retry_count += 1
        
        # 如果所有代理重试都失败，记录错误
        if not self.login_success:
            self.logger.error(f'账号{self.account_index} 登录失败，已重试{MAX_PROXY_RETRIES}次，所有代理均不可用')
    
    def run(self) -> Dict[str, Any]:
        """运行账号任务
        
        Returns:
            Dict: 包含账号统计信息的字典
        """
        if not self.login_success:
            return {
                'success': False,
                'phone': '',
                'points_before': 0,
                'points_after': 0,
                'points_earned': 0
            }
        
        # 随机延迟
        wait_time = random.randint(1000, 3000) / 1000.0
        time.sleep(wait_time)
        
        # 初始化任务执行器
        executor = TaskExecutor(self.http_client, self.logger, self.config, self.user_id)
        
        # 签到前先查一次积分基准，避免把签到奖励算进"执行前积分"
        points_base = executor.query_total_points()
        self.logger.points_info(points_base, "执行前积分")
        
        # 先执行APP签到
        app_sign_success, app_error_msg = executor.app_sign_in()
        time.sleep(1)
        
        # 再执行小程序签到
        sign_success, error_msg = executor.sign_in()
        
        # 执行签到日历
        new_sign_success, new_sign_error = executor.new_sign_in()
        time.sleep(1)
        
        # 如果签到失败且错误信息包含“活动太火爆”，尝试重新登录
        if not sign_success and '活动太火爆' in error_msg:
            max_retries = 3
            for retry in range(max_retries):
                self.logger.warning(f'签到失败（代理IP问题），{2}秒后重新获取代理并重试（第{retry + 1}次）...')
                time.sleep(2)
                
                try:
                    # 重新创建HTTP客户端（会自动获取新代理）
                    self.http_client = SFHttpClient(self.config, self.proxy_manager)
                    
                    # 重新登录
                    success, self.user_id, self.phone = self.http_client.login(self.account_url)
                    
                    if success:
                        # 更新执行器的HTTP客户端
                        executor.http = self.http_client
                        executor.user_id = self.user_id
                        
                        # 重试签到
                        sign_success, error_msg = executor.sign_in()
                        
                        if sign_success:
                            self.logger.success('重新登录后签到成功')
                            break
                        elif '活动太火爆' not in error_msg:
                            # 如果不是代理问题，则不再重试
                            break
                    else:
                        if retry == max_retries - 1:
                            self.logger.error(f'重新登录失败，已重试{max_retries}次')
                except Exception as e:
                    if retry == max_retries - 1:
                        self.logger.error(f'重新登录异常: {str(e)[:100]}，已重试{max_retries}次')
        
        # 执行其他任务（run_all_tasks 第一步会再查一次积分，作为 points_before=签到后积分）
        points_before, points_after = executor.run_all_tasks()
        points_earned = points_after - points_before
        
        # 顺丰红包大派送
        redpacket_result = None
        if self.config.ENABLE_RED_PACKET:
            try:
                self.logger.raw("🎯 开始执行顺丰红包大派送（每天免费抽奖一次）")
                rp_executor = RedPacketExecutor(self.http_client, self.logger)
                redpacket_result = rp_executor.run()
            except Exception as e:
                self.logger.error(f"顺丰红包大派送失败: {e}")
        
        # 我的优惠券查询
        coupons_result = None
        if self.config.ENABLE_COUPON_QUERY:
            try:
                self.logger.raw("🎟️ 开始查询我的优惠券")
                coupon_executor = CouponQueryExecutor(self.http_client, self.logger)
                coupons_result = coupon_executor.run()
            except Exception as e:
                self.logger.error(f"优惠券查询失败: {e}")
        
        # 会员日活动（每月26-28号自动执行）
        member_day_result = None
        if self.config.ENABLE_MEMBER_DAY:
            try:
                from datetime import datetime
                now = datetime.now()
                if now.day in (26, 27, 28):
                    self.logger.section(f"账号 {self.user_id} - 会员日活动（{now.month}月{now.day}日）")
                    member_executor = MemberDayExecutor(self.logger, self.http_client, self.config)
                    member_day_result = member_executor.execute()
            except Exception as e:
                self.logger.error(f"会员日活动失败: {e}")
        
        # 本次执行总获得积分 = 最终积分 - 签到前基准（含签到+任务+大派送）
        total_earned = (points_after or 0) - (points_base or 0)
        
        # 返回统计信息
        return {
            'success': True,
            'phone': self.phone,
            'points_before': points_before,
            'points_after': points_after,
            'points_earned': points_earned,
            'points_base': points_base,
            'total_earned': total_earned,
            'redpacket': redpacket_result,
            'coupons': coupons_result,
            'member_day': member_day_result
        }


# ==================== 顺丰红包大派送（抽奖）执行器 ====================
class RedPacketExecutor:
    """顺丰红包大派送 (mid-platform, activityType=MID_JGGCJ)，官方每天免费抽奖一次。

    端点：
      - getUserAcRuleInfo : 查询活动规则 / 剩余抽奖次数 surplusLotteryNum / ruleCode
      - lotteryPrize      : 抽奖发放接口，点击"抽奖"按钮调用，服务端随机发券
    lotteryPrize 必须带 body: {acId, ruleCode, secendChannel, md5Sign}，且 Referer 为
    nineBlockDraw 抽奖页（含 acId 与 token）。md5Sign 为固定常量。
    必须先查 getUserAcRuleInfo 的 surplusLotteryNum，为 0 时直接跳过。
    """

    BASE_URL = 'https://mcs-mimp-web.sf-express.com/mcs-mimp'
    AC_ID = '1D2532575D49438FA3D63842BF53F6EB'
    SECEND_CHANNEL = 'MBHD_BASIC20260409160224813'
    # lotteryPrize 所需的 ruleCode（来自 getUserAcRuleInfo 响应 obj.ruleCode，对所有账号固定）；
    # md5Sign 为固定三元组(acId+ruleCode+secendChannel)的常量签名，与账号/session/timestamp 无关。
    RULE_CODE = 'SFGZ20260409160224757'
    MD5_SIGN = 'f196f7a1db74f90f84bf03b8d54fc006'
    RULE_INFO_PATH = '/commonNoLoginPost/~actMiddlePlat~midActivity~getUserAcRuleInfo'
    LOTTERY_PATH = '/commonPost/~actMiddlePlat~midActivity~lotteryPrize'
    DRAW_REFERER_TPL = (
        'https://mcs-mimp-web.sf-express.com/origin/g/mid-platform/main-active/'
        'nineBlockDraw'
        '?redirectUri=/origin/g/mid-platform/main-active/activityCenterEntry'
        '&mobile={mobile_mask}&userId={user_id}&scene=676&memberType=0&token={session_id}'
        '&acId={ac_id}&from={secend_channel}'
        '&activityType=MID_JGGCJ&source=CX&isFinishActivity=true'
    )
    DRAW_ORIGIN = 'https://mcs-mimp-web.sf-express.com'
    ACT_HEADERS = {
        'channel': SECEND_CHANNEL,
        'sysCode': 'MCS-MIMP-CORE',
        'platform': 'MINI_PROGRAM',
    }

    def __init__(self, http: SFHttpClient, logger: Logger):
        self.http = http
        self.logger = logger

    def _rule_info(self):
        url = f'{self.BASE_URL}{self.RULE_INFO_PATH}'
        return self.http.request(
            url,
            data={'acId': self.AC_ID, 'empNum': '', 'shareUserId': '',
                  'shareRuleCode': '', 'shareTaskId': ''},
            extra_headers=self.ACT_HEADERS,
        )

    def _draw(self):
        """执行一次免费抽奖，调用抽奖发放接口 lotteryPrize。"""
        url = f'{self.BASE_URL}{self.LOTTERY_PATH}'
        body = {
            'acId': self.AC_ID,
            'ruleCode': self.RULE_CODE,
            'secendChannel': self.SECEND_CHANNEL,
            'md5Sign': self.MD5_SIGN,
        }
        sid = ''
        uid = ''
        phone = ''
        try:
            ck = self.http.session.cookies.get_dict()
            sid = ck.get('sessionId', '')
            uid = ck.get('_login_user_id_', '')
            phone = ck.get('_login_mobile_', '')
        except Exception:
            pass
        mask = f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 7 else phone
        referer = self.DRAW_REFERER_TPL.format(
            mobile_mask=mask, user_id=uid, session_id=sid,
            ac_id=self.AC_ID, secend_channel=self.SECEND_CHANNEL,
        )
        draw_headers = dict(self.ACT_HEADERS)
        draw_headers['referer'] = referer
        draw_headers['origin'] = self.DRAW_ORIGIN
        return self.http.request(url, data=body, extra_headers=draw_headers)

    def run(self):
        prizes = []
        rule = None
        surplus = None
        try:
            rule = self._rule_info()
            if rule and rule.get('success'):
                obj = rule.get('obj') or {}
                rule_name = obj.get('acName') or obj.get('name') or '顺丰红包大派送'
                self.logger.raw(f'📝 [顺丰红包大派送] 活动: {rule_name}')
                if 'surplusLotteryNum' in obj:
                    try:
                        surplus = int(obj.get('surplusLotteryNum'))
                    except (TypeError, ValueError):
                        surplus = None
                if surplus is not None:
                    self.logger.raw(f'📝 [顺丰红包大派送] 剩余免费抽奖次数: {surplus}（每天限1次）')
            else:
                self.logger.raw('📝 [顺丰红包大派送] 查询活动规则未返回成功，仍尝试抽奖')
        except Exception:
            pass

        if surplus == 0:
            self.logger.raw('📝 [顺丰红包大派送] 今日免费抽奖次数已用完（暂无抽奖次数），跳过抽奖。')
        else:
            try:
                resp = self._draw()
            except Exception as e:
                self.logger.error(f'[顺丰红包大派送] 抽奖请求异常: {str(e)[:80]}')
                resp = None

            if resp and resp.get('success'):
                obj = resp.get('obj') or {}
                draw_records = obj.get('userWinPrizeList')
                if not isinstance(draw_records, list):
                    draw_records = obj.get('midAcAwardRecords')
                if not isinstance(draw_records, list):
                    draw_records = []

                if draw_records:
                    for rec in draw_records:
                        if not isinstance(rec, dict):
                            continue
                        name = (rec.get('prizeName') or rec.get('packetName')
                                or rec.get('couponName') or rec.get('commodityName')
                                or rec.get('productName') or '未解析奖品')
                        amount = rec.get('prizeAmount') or rec.get('couponAmount') or ''
                        eff = rec.get('effectTm') or ''
                        inv = rec.get('invalidTm') or ''
                        extra = ''
                        if amount:
                            extra += f' 面额={amount}元'
                        if eff and inv:
                            extra += f' 有效期={eff}~{inv}'
                        self.logger.raw(f'🎉 [顺丰红包大派送] 免费抽奖成功 ➔ 获得: {name}{extra}')
                        prizes.append(name)
                else:
                    self.logger.raw('📝 [顺丰红包大派送] 抽奖受理成功，但本次未抽中奖品。')
            else:
                code = resp.get('errorCode') if resp else None
                msg = (resp or {}).get('errorMsg') or (resp or {}).get('msg') or '未知错误'
                if any(k in str(msg) for k in ('已', '次数', '今日', '重复', 'limit', 'Limit', '暂无')):
                    self.logger.raw('📝 [顺丰红包大派送] 今日免费抽奖已完成或次数不足，跳过抽奖。')
                else:
                    self.logger.error(f'[顺丰红包大派送] 抽奖失败: code={code} msg={msg}')

        return prizes


# ==================== 我的优惠券查询执行器 ====================
class CouponQueryExecutor:
    """查询当前账户【已持有】的优惠券列表（"我的优惠券"页 = couponCollection）。

    接口：
        POST https://mcs-mimp-web.sf-express.com/mcs-mimp/coupon/available/list
    body: {"type":"1","pageSize":10,"pageNum":1,"couponType":"","labelCode":"0","channel":"SFAPP"}
    """
    DEFAULT_URL = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/coupon/available/list'
    REQ_BODY = {
        "type": "1",
        "pageSize": 50,
        "pageNum": 1,
        "couponType": "",
        "labelCode": "0",
        "channel": "SFAPP",
    }
    ACT_HEADERS = {
        'channel': 'HOME_COUPON',
        'syscode': 'MCS-MIMP-CORE',
        'platform': 'SFAPP',
        'content-type': 'application/json',
        'referer': (
            'https://mcs-mimp-web.sf-express.com/home'
            '?redirectUri=/couponCollection&from=HOME_COUPON'
        ),
    }

    def __init__(self, http: SFHttpClient, logger: Logger):
        self.http = http
        self.logger = logger
        self.force_url = os.environ.get('COUPON_QUERY_URL', '').strip() or None

    @staticmethod
    def _fmt_coupon(c):
        name = c.get('couponName') or '未命名券'
        amt = c.get('pledgeAmt')
        try:
            amt_s = f"¥{float(amt):.2f}" if amt is not None else ''
        except (TypeError, ValueError):
            amt_s = f"¥{amt}" if amt is not None else ''
        eff = c.get('effectTm', '')
        inv = c.get('invalidTm', '')
        status = c.get('status', '')
        status_s = '有效' if status == 'EFFE' else (status or '未知')
        return f"{name}({amt_s})[{status_s} {eff}~{inv}]"

    def run(self):
        url = self.force_url or self.DEFAULT_URL
        try:
            resp = self.http.request(url, data=self.REQ_BODY,
                                     extra_headers=self.ACT_HEADERS)
        except Exception as e:
            self.logger.error(f"优惠券查询请求异常: {str(e)[:80]}")
            return []

        if not resp:
            self.logger.error("优惠券查询无响应（接口可能已下线）")
            return []

        if not resp.get('success'):
            self.logger.error(f"优惠券查询失败: {resp.get('msg') or resp.get('message') or resp}")
            return []

        obj = resp.get('obj')
        if not isinstance(obj, list):
            self.logger.raw("📝 [优惠券查询] 优惠券列表为空")
            return []

        coupons = [self._fmt_coupon(c) for c in obj if isinstance(c, dict)]
        self.logger.raw(f"📝 [优惠券查询] 查询到 {len(coupons)} 张优惠券")
        for c in coupons:
            self.logger.raw(f"🎟️ {c}")
        return coupons


# ==================== 会员日活动执行器 ====================
class MemberDayExecutor:
    """会员日活动执行器（搬自 sfsy.py，每月26-28号自动执行）"""
    
    def __init__(self, logger: Logger, http_client: SFHttpClient, config: Config):
        self.logger = logger
        self.http = http_client
        self.config = config
    
    def execute(self) -> Dict:
        """执行会员日活动，返回结果摘要"""
        success = False
        tasks_done: List[str] = []
        error = None
        try:
            # 会员日活动：领取任务 + 完成任务 + 领取奖励
            self.logger.info('开始执行会员日活动...')
            
            # 1. 获取会员日任务列表
            url = f'{self.config.MEMBER_DAY_API}/mcs-mimp/commonPost/~memberNonactivity~memberDayActivity~getActivityInfo'
            data = {'channelType': '1'}
            response = self.http.request(url, data=data)
            
            if not (response and response.get('success')):
                error = response.get('errorMessage', '未知错误') if response else '请求失败'
                self.logger.warn(f'获取会员日活动失败: {error}')
                return {'success': success, 'tasks_done': tasks_done, 'error': error}
            
            obj = response.get('obj', {})
            task_list = obj.get('taskList', [])
            if not task_list:
                self.logger.info('会员日暂无可执行任务')
                return {'success': True, 'tasks_done': tasks_done, 'error': None}
            
            # 2. 逐个完成任务
            for task in task_list:
                task_code = task.get('taskCode', '')
                task_name = task.get('taskName', '未知任务')
                if not task_code:
                    continue
                
                # 完成任务
                finish_url = f'{self.config.MEMBER_DAY_API}/mcs-mimp/commonPost/~memberNonactivity~memberDayActivity~finishTask'
                finish_data = {'taskCode': task_code, 'channelType': '1'}
                finish_resp = self.http.request(finish_url, data=finish_data)
                
                if finish_resp and finish_resp.get('success'):
                    self.logger.success(f'会员日任务完成: {task_name}')
                    tasks_done.append(task_name)
                    
                    # 领取奖励
                    fetch_url = f'{self.config.MEMBER_DAY_API}/mcs-mimp/commonPost/~memberNonactivity~memberDayActivity~fetchPrize'
                    fetch_data = {'taskCode': task_code, 'channelType': '1'}
                    fetch_resp = self.http.request(fetch_url, data=fetch_data)
                    if fetch_resp and fetch_resp.get('success'):
                        self.logger.success(f'会员日奖励领取: {task_name}')
                    else:
                        self.logger.info(f'会员日奖励领取失败(可能已领): {task_name}')
                else:
                    self.logger.info(f'会员日任务跳过: {task_name}')
            
            success = True
            return {'success': success, 'tasks_done': tasks_done, 'error': None}
        except Exception as e:
            self.logger.error(f'会员日活动异常: {e}')
            return {'success': False, 'tasks_done': tasks_done, 'error': str(e)}


# ==================== 单账号执行函数 ====================
def run_single_account(account_info: str, index: int, config: Config) -> Dict[str, Any]:
    """
    执行单个账号的任务（线程安全）
    
    Args:
        account_info: 账号信息
        index: 账号索引
        config: 配置对象
    
    Returns:
        Dict: 包含账号统计信息的字典
    """
    try:
        with print_lock:
            print(f"🚀 开始执行账号{index + 1}")
        
        account = AccountManager(account_info, index, config)
        result = account.run()
        
        if result['success']:
            with print_lock:
                print(f"✅ 账号{index + 1}执行完成")
        else:
            with print_lock:
                print(f"❌ 账号{index + 1}执行失败")
        
        result['index'] = index
        return result
    except Exception as e:
        error_msg = f"账号{index + 1}执行异常: {str(e)}"
        with print_lock:
            print(f"❌ {error_msg}")
        return {
            'index': index,
            'success': False,
            'phone': '',
            'points_before': 0,
            'points_after': 0,
            'points_earned': 0,
            'error': error_msg
        }


# ==================== 主程序 ====================

def _disp_width(s: str) -> int:
    """计算字符串显示宽度（中文等宽字符按2计）"""
    w = 0
    for ch in s:
        w += 2 if ord(ch) > 0x2E7F else 1
    return w


def _pad(s: str, width: int) -> str:
    """右侧补空格到指定显示宽度"""
    return s + ' ' * max(0, width - _disp_width(s))


def _table_border(widths, left: str = '+', mid: str = '+', right: str = '+') -> str:
    """生成表格分隔线（+---+---+），纯 ASCII 字符，渲染宽度确定。"""
    segs = ['-' * (w + 2) for w in widths]
    return left + mid.join(segs) + right


def _table_row(cells, widths) -> str:
    """生成表格数据行（| 内容 | 内容 |），纯 ASCII 竖线。"""
    segs = [f' {_pad(c, w)} ' for c, w in zip(cells, widths)]
    return '|' + '|'.join(segs) + '|'


def main():
    """主函数"""
    # Windows 控制台默认 GBK，emoji 会触发 UnicodeEncodeError，强制 UTF-8 输出
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8', 'utf_8'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

    config = Config()

    env_value = os.getenv(config.ENV_NAME)
    if not env_value:
        print(f"❌ 未找到环境变量 {config.ENV_NAME}，请检查配置")
        return

    account_urls = [url.strip() for url in env_value.split('&') if url.strip()]
    if not account_urls:
        print(f"❌ 环境变量 {config.ENV_NAME} 为空或格式错误")
        return

    # 随机打乱账号顺序
    random.shuffle(account_urls)
    print(f"🔀 已随机打乱账号执行顺序")

    print("=" * 50)
    print(f"🎉 {config.APP_NAME} v{config.VERSION}")
    print(f"👨‍💻 作者: 爱学习的呆子")
    print(f"📱 共获取到 {len(account_urls)} 个账号")
    print(f"⚙️ 并发数量: {CONCURRENT_NUM}")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 收集所有账号的统计信息
    all_results = []
    
    if CONCURRENT_NUM <= 1:
        # 串行执行模式
        print("🔄 使用串行模式执行...")
        for index, account_url in enumerate(account_urls):
            account = AccountManager(account_url, index, config)
            result = account.run()
            result['index'] = index
            all_results.append(result)
            
            if index < len(account_urls) - 1:
                print("=" * 50)
                print(f"⏳ 等待 2 秒后执行下一个账号...")
                time.sleep(2)
    else:
        # 并发执行模式
        print(f"🔄 使用并发模式执行，并发数: {CONCURRENT_NUM}")
        
        # 使用线程池执行
        with ThreadPoolExecutor(max_workers=CONCURRENT_NUM) as executor:
            # 提交所有任务
            future_to_index = {
                executor.submit(run_single_account, account_url, index, config): index 
                for index, account_url in enumerate(account_urls)
            }
            
            # 等待任务完成
            for future in as_completed(future_to_index):
                result = future.result()
                all_results.append(result)
    
    # 按索引排序结果
    all_results.sort(key=lambda x: x['index'])
    
    # 统计成功和失败数量
    success_count = sum(1 for r in all_results if r['success'])
    fail_count = len(all_results) - success_count
    total_earned = sum(r['points_earned'] for r in all_results if r['success'])
    total_all_earned = sum(r.get('total_earned', 0) for r in all_results if r['success'])
    
    # 显示汇总统计表格（纯 ASCII 表头 + 等宽表格，避开中文宽度在青龙面板不对齐）
    # 列宽（字符数，全 ASCII 故每个字符严格 1 列，等宽日志下必然对齐）
    # No / Phone / Total(含签到获得) / Task(任务获得) / After(总积分) / Status
    widths = [4, 13, 12, 8, 9, 7]

    top = _table_border(widths)
    mid = _table_border(widths)
    bottom = _table_border(widths)

    print()
    print("📊 积分统计汇总")
    print(top)
    print(_table_row(['No', 'Phone', 'Total', 'Task', 'After', 'Status'], widths))
    print(mid)

    for result in all_results:
        index = result['index'] + 1
        phone = result['phone'][:3] + "****" + result['phone'][7:] if result['phone'] else "N/A"
        all_earned = result.get('total_earned', result['points_earned'])
        earned = result['points_earned']
        total = result['points_after']
        status = "OK" if result['success'] else "FAIL"

        print(_table_row(
            [str(index), phone, str(all_earned), str(earned), str(total), status],
            widths,
        ))

    print(mid)
    print(_table_row(
        ['SUM', 'Accounts: ' + str(len(all_results)),
         'Total: ' + str(total_all_earned), 'Task: ' + str(total_earned),
         '', 'OK: ' + str(success_count)],
        widths,
    ))
    print(bottom)
    
    # 顺丰红包大派送 / 优惠券 汇总
    any_rp = False
    any_cp = False
    for result in all_results:
        if result.get('redpacket'):
            any_rp = True
        if result.get('coupons'):
            any_cp = True
    if any_rp:
        print("\n🧧 顺丰红包大派送中奖汇总")
        for result in all_results:
            rp_prizes = result.get('redpacket') or []
            if rp_prizes:
                phone = result['phone'][:3] + "****" + result['phone'][7:] if result['phone'] else "N/A"
                print(f"  🧧 {phone}: {', '.join(str(p) for p in rp_prizes)}")
    if any_cp:
        print("\n🎟️ 优惠券统计汇总")
        first_block = True
        for result in all_results:
            coupons = result.get('coupons') or []
            if not coupons:
                continue
            if not first_block:
                print()  # 账号块之间空行分隔
            first_block = False
            phone = result['phone'][:3] + "****" + result['phone'][7:] if result['phone'] else "N/A"
            print(f"  👤 {phone}（{len(coupons)}张优惠券）")
            # 拆分「名称(¥金额)」与「[有效 ...]」，按最大显示宽度对齐列
            parsed = []
            max_w = 0
            for c in coupons:
                m = re.match(r'(.*?)(\s*\[.*)$', c)
                if m:
                    prefix, suffix = m.group(1), m.group(2)
                else:
                    prefix, suffix = c, ''
                parsed.append((prefix, suffix))
                max_w = max(max_w, _disp_width(prefix))
            for prefix, suffix in parsed:
                print(f"     🎟️ {_pad(prefix, max_w)}{suffix}")

    print("\n🎊 所有账号任务执行完成!")


if __name__ == '__main__':
    main()
