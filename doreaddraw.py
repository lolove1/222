"""

"""

import requests
from tools.notify import send
from json import dumps
from tools.ql_api import get_cookie
from uuid import uuid4
from random import randint
import threading
from time import sleep
from tools.tool import get_environ, timestamp
import execjs
import re

message = "------联通阅读抽奖------\n\n"


def parse_cklist(cklist):
    # 将 cklist 列表中的每个字符串分隔成子字符串，然后将它们添加到 user_map 列表中
    user_map = [x for ck in cklist for x in (
        ck.split("&") + ck.split("\n") if "&" in ck else [ck])]
    return user_map


def start_threads(user_map, interval=25):
    print(f"user_map: {user_map}")
    # 遍历 user_map 列表，为每个账号启动一个线程
    threads = []
    for i, unicom_cookie in enumerate(user_map, start=1):
        if not unicom_cookie:
            print("当前账号未填写 CK，跳过")
            print("\n")
            continue
        print(f"开始执行第{i}个账号")
        p = threading.Thread(target=start, args=(unicom_cookie,))
        threads.append(p)
        p.start()
        sleep(interval)  # 每次循环后间隔一段时间
        print("\n")
    return threads


def get_from_cookie(ck, key):
    phone = ''
    kvs = ck.split(";")
    for kv in kvs:
        split = kv.split("=")
        if split[0] == key:
            phone = split[1]
            break
    return phone


def start(unicom_cookie):
    if unicom_cookie == "":
        exit(0)
    Unicom(unicom_cookie).main()
    print("\n")


class Unicom(object):
    def __init__(self, unicom_cookie):
        info = unicom_cookie.split("#")
        self.phone = info[0]
        self.version = "android@10.0200"
        self.ua = "Mozilla/5.0 (Linux; Android 12; V1986A Build/SP1A.210812.003; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/96.0.4664.104 Mobile Safari/537.36; unicom{version:%s,desmobile:%s};devicetype{deviceBrand:vivo,deviceModel:V1986A};{yw_code:}" % (
            self.version,
            self.phone,
        )
        self.session = requests.Session()
        self.session.headers = requests.structures.CaseInsensitiveDict({
            "content-type": "application/x-www-form-urlencoded",
            "user-agent": self.ua,
        })

    def getEncryptMobile(self):
        with open('./tools/security.js', 'r', encoding='utf8') as fr:
            securityJs = fr.read()
        scriptText = '''
        function getEncryptMobile(mobile) {
            var modulus = "00A828DB9D028A4B9FC017821C119DFFB8537ECEF7F91D4BC06DB06CC8B4E6B2D0A949B66A86782D23AA5AA847312D91BE07DC1430C1A6F6DE01A3D98474FE4511AAB7E4E709045B61F17D0DC4E34FB4BE0FF32A04E442EEE6B326D97E11AE8F23BF09926BF05AAF65DE34BB90DEBDCEE475D0832B79586B4B02DEED2FC3EA10B3";
            var exponent = "010001";
            var key = window.RSAUtils.getKeyPair(exponent, '', modulus);
            mobile = window.RSAUtils.encryptedString(key, mobile);
            return mobile
        }
        '''
        scriptText = 'var window = {};' + securityJs + scriptText
        ctx = execjs.compile(scriptText)
        EncryptMobile = ctx.call('getEncryptMobile', self.phone)
        return EncryptMobile

    # 登录
    def loginRead(self):
        global message  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = 'https://10010.woread.com.cn/touchextenernal/common/shouTingLogin.action'
        data = {
            'phonenum': self.getEncryptMobile()
        }
        resp = self.session.post(url=url, data=data)
        print(self.phone + ' ' + resp.text)
        if not self.session.cookies.get('useraccount', False):
            raise Exception('[WoRead]登录失败,结束执行任务')
        drawNum = self.getDraw()
        if drawNum > 0:
            for i in range(1, drawNum+1):
                print(f'账号：{self.phone}:执行第{i}次抽奖')
                # message += f'账号：{self.phone}:执行第{i}次抽奖\n'
                self.doReadDraw()
                sleep(5)
        else:
            print(f'结束')

    def getDraw(self):
        global message  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = f'https://10010.woread.com.cn/touchextenernal/actsub/getDraw.action'
        data = {
            'allactiveindex': 10800,
            'activityId': 6818,
            'channelid': '18000820'
        }
        resp = self.session.post(url, data)
        resp.encoding = 'utf8'

        drawNum = re.findall(
            r'var drawCount = parseInt\("(\d+)"\)', resp.text)[0]
        drawNum = int(drawNum)
        print(f'账号：{self.phone}:还有{drawNum}次抽奖次数')
        return drawNum

    # 转盘
    def doReadDraw(self):
        global message  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = "https://10010.woread.com.cn/touchextenernal/actsub/doDraw.action"
        data = {
            "acticeindex": "OEJFMjJFQjhEQTBDNDFBMkU5RUI3M0Y0MTI3NzA1N0Q=", "t": timestamp()
        }
        self.session.headers.update({
            'Referer': 'https://10010.woread.com.cn/touchextenernal/actsub/getActivity.action?activityId=6818',
        })
        result = self.session.post(url, data).json()
        if result['code'] == "0000":
            if result['message'] == "-1":
                print(f'账号：{self.phone}-抽奖结果：抱歉，您未中奖！')
            else:
                print(f'账号：{self.phone}-抽奖结果：{result["prizedesc"]}')
                message += f'账号：{self.phone}-抽奖结果：{result["prizedesc"]}\n'
        else:
            print(f'请求失败：{result}')

    def main(self):
        if not self.phone:
            self.phone = '你添加手机号码了吗'
            exit(0)
        self.loginRead()


if __name__ == '__main__':

    cklist = get_cookie("PHONE_NUM")
    user_map = parse_cklist(cklist)
    threads = start_threads(user_map)
    for thread in threads:
        thread.join()
    send("联通抽奖", message)
