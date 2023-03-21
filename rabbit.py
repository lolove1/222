#!/usr/bin/python3
 #-- coding: utf-8 --
 #export PHONE_NUM="18638363194#ChinaUnicom4.x/10.2 (com.chinaunicom.mobilebusiness; build:41; iOS 15.5.0) Alamofire/10.2 unicom{version:iphone_c@10.0200}"


from tools.notify import send
from tools.ql_api import get_cookie
from requests import post, get
from time import sleep, time
from datetime import datetime
from hashlib import md5 as md5Encode
from random import randint, uniform, choice
from os import environ
from sys import stdout, exit
from base64 import b64encode
from base64 import b64decode
from json import dumps
from tools.encrypt_symmetric import Crypt
from tools.send_msg import push
from tools.tool import get_environ, random_sleep
import threading
msg_str = "联通话费兑换路径：联通APP搜索阅读--->阅读专区--->我的--->话费红包，可兑换3元或者5元话费抵扣券，最后使用沃钱包支付即可\n\n"

"""主类"""


class China_Unicom:
    def __init__(self, phone_num, run_ua):
        self.phone_num = phone_num
        default_ua = f"Mozilla/5.0 (Linux; Android {randint(8, 13)}; SM-S908U Build/TP1A.220810.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{randint(95, 108)}.0.5359.128 Mobile Safari/537.36; unicom{{version:android@9.0{randint(0,6)}00,desmobile:{self.phone_num}}};devicetype{{deviceBrand:,deviceModel:}};{{yw_code:}}"
        if run_ua is None or run_ua == "":
            run_ua = default_ua

        self.headers = {
            "Host": "10010.woread.com.cn",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json;charset=utf-8",
            "Origin": "https://10010.woread.com.cn",
            "User-Agent": run_ua,
            "Connection": "keep-alive",
            "Referer": "https://10010.woread.com.cn/ng_woread/",
        }
        self.fail_num = 0
        self.activeIndex = '26'

    def timestamp(self):
        return round(time() * 1000)

    def print_now(self, content):
        print(content)
        stdout.flush()

    def md5(self, str):
        m = md5Encode(str.encode(encoding='utf-8'))
        return m.hexdigest()

    def req(self, url, crypt_text, retry_num=5):
        while retry_num > 0:
            body = {
                "sign": b64encode(Crypt(crypt_type="AES", key="update!@#1234567", iv="16-Bytes--String", mode="CBC").encrypt(crypt_text).encode()).decode()
            }
            self.headers["Content-Length"] = str(
                len(dumps(body).replace(" ", "")))
            try:
                res = post(url, headers=self.headers, json=body)
                data = res.json()
                return data
            except Exception as e:
                print(f"本次请求失败, 正在重新发送请求 剩余次数{retry_num}")
                print(f"本次请求失败url------{url}")
                print(f"本次请求失败crypt_text------{crypt_text}")
                print(f"本次请求失败原因------{e}")
                retry_num -= 1
                sleep(10)
                return self.req(url, crypt_text, retry_num)

    def referer_login(self):
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        timestamp = self.timestamp()
        url = f"https://10010.woread.com.cn/ng_woread_service/rest/app/auth/10000002/{timestamp}/{self.md5(f'100000027k1HcDL8RKvc{timestamp}')}"
        crypt_text = f'{{"timestamp":"{date}"}}'
        body = {
            "sign": b64encode(Crypt(crypt_type="AES", key="1234567890abcdef").encrypt(crypt_text).encode()).decode()
        }
        self.headers["Content-Length"] = str(len(str(body)) - 1)
        data = post(url, headers=self.headers, json=body).json()
        if data["code"] == "0000":
            self.headers["accesstoken"] = data["data"]["accesstoken"]
        else:
            self.print_now(f"设备登录失败,日志为{data}")
            exit(0)

    def get_userinfo(self):
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        url = "https://10010.woread.com.cn/ng_woread_service/rest/account/login"
        crypt_text = f'{{"phone":"{self.phone_num}","timestamp":"{date}"}}'
        data = self.req(url, crypt_text)
        print(f"账号{self.phone_num}登录结果------{data}")
        if data["code"] == "0000":
            self.userinfo = data["data"]
        else:
            self.print_now(f"手机号登录失败, 日志为{data}")
            exit(0)

    def read_novel(self):
        global msg_str  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        self.get_cardid()
        self.get_cntindex()
        self.get_chapterallindex()
        # self.print_now(
        #     f"你的账号{self.phone_num} ：正在执行观看300次小说, 此过程较久, 最大时长为70 * 2min = 120min\n")
        for i in range(70):
            date = datetime.today().__format__("%Y%m%d%H%M%S")
            hour = datetime.now().hour  # 获取当前时刻
            if hasattr(self, "activitystatus") and self.activitystatus == 1:
                print(f"当前账号{self.phone_num}活动已完成")
                msg_str += f"当前账号{self.phone_num}活动已完成\n\n"
                break
            if hasattr(self, "totalreadnums") and self.totalreadnums >= 120:
                if hasattr(self, "activitystatus") and self.activitystatus == 0:
                    print(f"当前账号{self.phone_num}去完成活动")
                    msg_str += f"当前账号{self.phone_num}去完成活动\n\n"
                    self.finishActivity()
                else:
                    print(f"当前账号{self.phone_num}阅读满了，跳过")
                    msg_str += f"当前账号{self.phone_num}阅读满了，跳过\n\n"
                break
            if hasattr(self, "readtime") and self.readtime / 600000 > hour/2 and self.status == 0 or hasattr(self, "readtime") and self.readtime > 7200000:
                self.get_activetion_id()
            chapterAllIndex = choice(self.chapterallindex_list)
            url = f"https://10010.woread.com.cn/ng_woread_service/rest/cnt/wordsDetail?catid={self.catid}&pageIndex={self.pageIndex}&cardid={randint(10000, 99999)}&cntindex={self.cntindex}&chapterallindex={chapterAllIndex}&chapterseno=3"
            crypt_text = f'{{"chapterAllIndex":{chapterAllIndex},"cntIndex":{self.cntindex},"cntTypeFlag":"1","timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
            data = self.req(url, crypt_text)
            if self.fail_num == 3:
                self.print_now("当前任务出现异常 且错误次数达到3次 请手动检查")
                msg_str += f"账号{self.phone_num}阅读任务出现异常 且错误次数达到3次 请手动检查\n\n"
                exit(0)
            if data.get("code") != "0000":
                self.print_now("阅读小说发生异常, 正在重新登录执行, 接口返回")
                self.print_now(data)
                return self.main()
            sleep(120)
            if self.status == 1:
                self.wakeRabbit()
            else:
                print(f"账号{self.phone_num}正在执行第{i}次阅读")
                self.addReadTime(chapterAllIndex)

    # 获取活动信息
    def get_activetion_id(self):
        url = "https://10010.woread.com.cn/ng_woread_service/rest/rabbitActivity/queryActivityData"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"activeIndex":"{self.activeIndex}","timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        print(f"获取活动信息：{data}")
        if data["code"] == "0000":
            self.status = data["data"]["status"]
            self.totalreadnums = data["data"]["totalreadnums"]
            self.activitystatus = data["data"]["activitystatus"]
            return True
        else:
            self.print_now(data["message"])
            return False
    # 获取活动List

    def get_activetion_list(self):
        url = "https://10010.woread.com.cn/ng_woread_service/rest/activity/queryActiveList"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        # print(f"获取活动列表信息：{data}")
        if data["code"] == "0000":
            self.activeIndex = next(
                (row["activeIdx"] for row in data["data"]["rows"] if row["activeName"] == "龟兔赛跑"), "")
            gtspActiveInfo = next(
                (row["gtspActiveInfo"] for row in data["data"]["rows"] if row["activeName"] == "龟兔赛跑"), "")
            self.wakeindex = gtspActiveInfo["wakeindex"]
        # else:
        #     self.print_now(f"活动id获取失败 将影响抽奖和查询积分")

    # 加入游戏
    def joinRuning(self):
        global msg_str  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = "https://10010.woread.com.cn/ng_woread_service/rest/rabbitActivity/joinRuning"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"activeIndex":{self.activeIndex},"timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        self.print_now(f"账号：{self.phone_num}{data['data']}")
        msg_str += f"账号：{self.phone_num}{data['data']}\n\n"

    # 滑动次数
    def addDrawTimes(self):
        url = "https://10010.woread.com.cn/ng_woread_service/rest/basics/addDrawTimes"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"userid":"{self.userinfo["userid"]}","activetyindex":"6640","timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        print(f"addDrawTimes:{data}")

    # 上报阅读时间
    def addReadTime(self, chapterallindex):
        global msg_str  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = "https://10010.woread.com.cn/ng_woread_service/rest/history/addReadTime"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"readTime":"2","cntIndex":"{self.cntindex}","cntType":"1","catid":"0","pageIndex":"","cardid":"{self.cardid}","cntindex":"{self.cntindex}","cnttype":"1","chapterallindex":"{chapterallindex}","chapterseno":"3","channelid":"","timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        # print(f"addReadTime_crypt_text:{crypt_text}")
        # print(f"addReadTime_data:{data}")
        if data["code"] == '0000':
            self.readtime = data["data"]["readtime"]
            print(
                f"当前账号{self.phone_num}上报阅读时间成功,当前阅读时间：{data['data']['readtime']}")
            msg_str += f"账号：{self.phone_num}更新时间成功,当前阅读时间：{data['data']['readtime']}\n\n"
        elif data["code"] == '9999':
            self.fail_num += 1
            print(f"当前账号{self.phone_num}上报阅读时间：{data['message']}")
            self.main()

    # 唤醒兔子
    def wakeRabbit(self):
        global msg_str  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = "https://10010.woread.com.cn/ng_woread_service/rest/rabbitActivity/wakeRabbit"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"activeIndex":"{self.activeIndex}","sactivitIndex":"7246","timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        print(f"wakeRabbit:{data}")
        msg_str += f"账号：{self.phone_num}:wakeRabbit:{data}\n\n"
        self.get_activetion_id()

    # 结束活动
    def finishActivity(self):
        global msg_str  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = "https://10010.woread.com.cn/ng_woread_service/rest/rabbitActivity/finishActivity"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"activeIndex":"{self.activeIndex}","timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        print(f"finishActivity:{data}")
        msg_str += f"账号：{self.phone_num}:finishActivity:{data}\n\n"
        # self.get_activetion_id()
        # self.getActivityNumber()

    def get_cardid(self):
        """
        获取cardid
        :return:
        """
        url = "https://10010.woread.com.cn/ng_woread_service/rest/basics/getIntellectRecommend"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"cntsize":8,"recommendsize":5,"recommendid":0,"timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        # print(data)
        self.pageIndex = data["data"]["recommendindex"] if "recommendindex" in data["data"] else "10725"
        self.cardid = data["data"]["catindex"] if "catindex" in data["data"] else "119056"

    def get_cntindex(self):
        url = "https://10010.woread.com.cn/ng_woread_service/rest/basics/recommposdetail/12279"
        self.headers.pop("Content-Length", "no")
        data = get(url, headers=self.headers).json()
        booklist = data["data"]["booklist"]["message"]
        book_num = len(booklist)
        self.catid = booklist[0]["catindex"] if "catindex" in booklist[0] else "119411"
        self.cntindex = booklist[randint(0, book_num - 1)]["cntindex"]

    def get_chapterallindex(self):
        url = f"https://10010.woread.com.cn/ng_woread_service/rest/cnt/chalist?catid=119411&pageIndex=10725&cardid=12279&cntindex={self.cntindex}"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"curPage":1,"limit":30,"index":"{self.cntindex}","sort":0,"finishFlag":1,"timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        chapterallindexlist = data["list"][0]["charptercontent"]
        chapterallindex_num = len(chapterallindexlist)
        self.chapterallindex_list = [0] * chapterallindex_num
        i = 0
        while i < chapterallindex_num:
            self.chapterallindex_list[i] = chapterallindexlist[i]["chapterallindex"]
            i += 1

    def query_red(self):
        global msg_str  # 声明我们在函数内部使用的是在函数外部定义的全局变量msg_str
        url = "https://10010.woread.com.cn/ng_woread_service/rest/phone/vouchers/queryTicketAccount"
        date = datetime.today().__format__("%Y%m%d%H%M%S")
        crypt_text = f'{{"timestamp":"{date}","token":"{self.userinfo["token"]}","userId":"{self.userinfo["userid"]}","userIndex":{self.userinfo["userindex"]},"userAccount":"{self.userinfo["phone"]}","verifyCode":"{self.userinfo["verifycode"]}"}}'
        data = self.req(url, crypt_text)
        if data["code"] == "0000":
            can_use_red = data["data"]["usableNum"] / 100
            if can_use_red >= 3:
                self.print_now(
                    f"账号{self.phone_num}查询成功 你当前有话费红包{can_use_red} 可以去兑换了")
                # push("某通阅读", f"账号{self.phone_num}查询成功 你当前有话费红包{can_use_red} 可以去兑换了")
                msg_str += f"账号{self.phone_num}查询成功 你当前有话费红包{can_use_red} 可以去兑换了\n\n"
            else:
                self.print_now(
                    f"账号{self.phone_num}查询成功 你当前有话费红包{can_use_red} 不足兑换的最低额度")
                # push("某通阅读", f"账号{self.phone_num}查询成功 你当前有话费红包{can_use_red} 不足兑换的最低额度")
                msg_str += f"账号{self.phone_num}查询成功 你当前有话费红包{can_use_red} 不足兑换的最低额度\n\n"

    def main(self):
        self.referer_login()
        self.get_userinfo()
        self.get_activetion_list()
        if not self.get_activetion_id():
            self.joinRuning()
            self.get_activetion_id()
        self.read_novel()
        self.query_red()


def start(phone, run_ua):
    if phone == "":
        print("没有用户")
        exit(0)
    China_Unicom(phone, run_ua).main()
    print("\n")
    print("\n")


if __name__ == "__main__":
    unicom_lotter = ""
    """读取环境变量"""
    l = []
    user_map = []
    cklist = get_cookie("PHONE_NUM")
    for i in range(len(cklist)):
        # 以#分割开的ck
        split1 = cklist[i].split("&")
        if len(split1) > 1:
            for j in range(len(split1)):
                user_map.append(split1[j])
        else:
            user_map.append(cklist[i])

    for i in range(len(user_map)):
        phone = ""
        info = user_map[i].split("&")[0]
        # 以#分割开的ck
        split1 = info.split("#")
        run_ua = ""
        phone = split1[0]
        if len(split1) > 1:
            run_ua = split1[1] + \
                f";devicetype{{deviceBrand:,deviceModel:}};{{yw_code:}}"

        print('开始执行第{}个账号：{}'.format((i+1), phone))
        if phone == "":
            print("当前账号未填写手机号 跳过")
            print("\n")
            continue
        p = threading.Thread(target=start, args=(phone, run_ua))
        l.append(p)
        p.start()
        print("\n")
    for i in l:
        sleep(uniform(20, 80))
        i.join()
    send("联通阅读", msg_str)
