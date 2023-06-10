import datetime
import json
import execjs
import requests
import time
import os
from json import dumps as jsonDumps
couponReferIds3 = '419967B3A4064140BA78E6A046DF0FC1'#10.30.25-12
couponReferIds2 = '687D57731F804A2CAE1F455331F83524'#15.00.25-12
couponReferIds = 'DBFA760914E34AFF9D8B158A7BC4D706'#10.00.30-15

# h5指纹
def mt_getMTFingerprint_example(js):
    now = int(datetime.datetime.now().timestamp() * 1000)
    print(111,js.call("getMTFingerprint", now),2222)


# 签名请求示例
def mt_sign_example(js, cookie: str):
    with requests.session() as session:
        session.headers = {
            "dj-token": "",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/114.0.5735.99 Mobile/15E148 Safari/604.1",
            "Content-Type": "application/json",
            "X-Requested-With": "com.sankuai.meituan",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://market.waimai.meituan.com/",
            "Cookie": _lxsdk_s=188a3063ad4-4fe-f1-f19%7C%7C9
        }
        url = 'https://promotion.waimai.meituan.com/lottery/limitcouponcomponent/fetchcoupon?couponReferId=DBFA760914E34AFF9D8B158A7BC4D706&actualLng=113.62493&actualLat=34.74725&geoType=2&gdPageId=306477&pageId=306004&version=1&utmSource=&utmCampaign=&instanceId=16620226080900.11717750606071209&componentId=16620226080900.11717750606071209'
        # data = {"cType": "mtandroid", "fpPlatform": 4, "wxOpenId": "", "appVersion": "12.9.404"}
        req = {
            "url": url,
            "method": "POST",
            "headers": session.headers,
            'data': data
        }

        now = int(datetime.datetime.now().timestamp() * 1000)
        r = js.call("signReq", req, now)
        # print(4577,r,96333)
        session.headers = r['headers']
        response1 = requests.get(url='https://promotion.waimai.meituan.com/lottery/limitcouponcomponent/info?couponReferIds='+couponReferIds,headers = r['headers'],params=data, json=req['data']).text
        response = requests.post(url=url,headers = r['headers'], json=req['data']).text
        print('msg1：',response1) 
        print('msg：',response)
        return response


# if __name__ == '__main__':
#     # 填写完整
#     cookie = '_lxsdk_cuid=
#     # mt_getMTFingerprint_example(js)
msg = ''
url = 'https://promotion.waimai.meituan.com/lottery/limitcouponcomponent/fetchcoupon?couponReferId=DBFA760914E34AFF9D8B158A7BC4D706&actualLng=113.62493&actualLat=34.74725&geoType=2&gdPageId=306477&pageId=306004&version=1&utmSource=&utmCampaign=&instanceId=16620226080900.11717750606071209&componentId=16620226080900.11717750606071209'
js_code = open('mt.js', 'r', encoding='utf-8').read()
data = {"cType": "mtandroid", "fpPlatform": 4, "wxOpenId": "", "appVersion": "12.9.404"}
cookie = ''
js = execjs.compile(js_code)
headers = {
            "dj-token": "",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/114.0.5735.99 Mobile/15E148 Safari/604.1",
            "Content-Type": "application/json",
            "X-Requested-With": "com.sankuai.meituan",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://market.waimai.meituan.com/",
            "Cookie": _lxsdk_s=188a3063ad4-4fe-f1-f19%7C%7C9
        }
# qq = mt_sign_example(js, cookie)
req = {
    "url": url,
    "method": "POST",
    "headers": headers,
    'data': data
}
now = int(datetime.datetime.now().timestamp() * 1000)
r = js.call("signReq", req, now)
print('-------------',r['headers']['mtgsig'])

# # mt_getMTFingerprint_example(js)
# if '已领取' in msg or '来晚了' in msg:
#     print('留点机会给年轻人吧！msg：',msg)
#     break
# time.sleep(0.002)
qlUrl = 'http://10.10.10.103:5700'
ID = '6Gzg_Ue6_PS0'
SECRET = 'sLdtAFHVE5PKh_gmuZ9_a-e3'
qlToken = ''
def login():
        """
        登录
        """
        myUrl = f"{qlUrl}/open/auth/token?client_id={ID}&client_secret={SECRET}"
        try:
            rjson = requests.get(myUrl).json()
            if(rjson['code'] == 200):
                qlToken = f"{rjson['data']['token_type']} {rjson['data']['token']}"
                # getEnvs(qlToken)
                update_environment_variable(qlToken)
            else:
                print(f"登录失败：{rjson}")
        except Exception as e:
            print(f"登录失败：",e)
def update_environment_variable(ql_token):
    url = f"{qlUrl}/open/envs?t={int(time.time() * 1000)}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": ql_token
    }
    data = {
        "id": 227,
        "name": 'mtgsig',
        "value": r['headers']['mtgsig'],
        "remarks": 'gbfdgh',
    }
    response = requests.put(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        print(f"Succeeded to update environment variable ")
    else:
        print(f"Failed to update environment variable ")
        print(response.json())
def getEnvs(ql_token):
    """
    获取环境变量
    """
    url = f"{qlUrl}/open/envs?searchValue=mtaql6666"
    headers = {"Authorization": ql_token}
    try:
        rjson = requests.get(url, headers=headers).json()
        if(rjson['code'] == 200):
            print(rjson)
            return rjson['data']
        else:
            print(f"获取环境变量失败：{rjson['message']}")
    except Exception as e:
        print(f"获取环境变量失败9：{e}")
login()

