import requests
import json
import time


def ChinaUnicom_login():
    url = 'https://m.client.10010.com/mobileService/onLine.htm'
    data = f"netWay=Wifi&version=android%4010.0100&token_online={i['online']}&provinceChanel=general&appId={i['appid']}&deviceModel=SM-S908U&step=bindlist&deviceBrand=&flushkey=1"
    headers = {"content-type": "application/x-www-form-urlencoded",
               "user-agent": 'ChinaUnicom4.x/10.1 (com.chinaunicom.mobilebusiness; build:69; iOS 15.6.0) Alamofire/10.1 unicom{version:iphone_c@10.0100}'}
    r = requests.post(url, headers=headers, data=data)
    Set_Cookie = (r.headers['Set-Cookie'])
    # print(Set_Cookie)
    if 'ecs_token' in Set_Cookie:
        ecs_token = r.json()['ecs_token']
        return ecs_token
    else:
        print('online失效')


def game_login():
    url = "https://game.wostore.cn/api/app//user/v2/login"
    body = {"identityType": "esToken",
            "code": ChinaUnicom_login()}
    # print(body)
    headers = {"content-type": "application/json;charset=utf-8", "channelid": "GAMELTAPP_90006"}
    data = json.dumps(body)
    r = requests.post(url, headers=headers, data=data)
    # print(r.text)#code=4002
    if r.json()['code'] == 200:
        access_token = (r.json()['data']['access_token'])
        return access_token
    else:
        print(r.json()['msg'])


def task():
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 unicom{version:iphone_c@10.0100}',
        'Authorization': game_login(), 'Content-Type': 'application/json;charset=utf-8'}
    # print(headers)

    url_1 = 'https://game.wostore.cn/api/app/user/v2/signIn'  # 签到
    url_2 = 'https://game.wostore.cn/api/app/user/v2/benefit/lottery?id=1'  # 抽奖
    url_3 = 'https://game.wostore.cn/api/app/user/v2/play/save'  # 游戏
    url_4 = 'https://game.wostore.cn/api/app/user/v2/task/receive?productId=803779160669851649&taskId=207188'
    url_5 = 'https://game.wostore.cn/api/app/user/v2/task/receive?productId=803779160665657346&taskId=207186'
    url_6 = 'https://game.wostore.cn/api/app/user/v2/task/receive?productId=803779160665657345&taskId=207185'
    url_7 = 'https://game.wostore.cn/api/app/user/v2/getMemberInfo'
    r_3 = requests.post(url_3, headers=headers, data=json.dumps({"cpGameId": "1500020299"}))
    time.sleep(1)
    r_1 = requests.get(url_1, headers=headers).json()['msg']
    # print(r_1)
    time.sleep(1)
    r_2 = requests.get(url_2, headers=headers).json()
    msg_2 = '每日抽奖:' + r_2['msg']
    time.sleep(1)
    r_4 = requests.get(url_4, headers=headers).json()
    msg_4 = '游戏体验:' + r_4['msg']
    time.sleep(1)
    r_5 = requests.get(url_5, headers=headers).json()
    msg_5 = '宝箱抽奖:' + r_5['msg']
    time.sleep(1)
    r_6 = requests.get(url_6, headers=headers).json()
    msg_6 = '每日签到:' + r_6['msg']
    time.sleep(1)
    r_7 = requests.get(url_7, headers=headers).json()
    # print(r_7)
    if r_7['code'] == 200:
        userIntegral = r_7['data']['userIntegral']
        name = r_7['data']['mobile']
        msg_7 = f'{name}当前金币:{userIntegral}'
    else:
        msg_7 = r_7['msg']
    msg = f'{msg_2}\n{msg_4}\n{msg_5}\n{msg_6}\n{msg_7}\n'
    print(msg)
    print('-------------------------')
    if requests.get(f'http://www.pushplus.plus/send?token={pushplus_token}&title=联通畅游_&content={msg}&template=html').json()['code'] == 200:
        print('推送成功!')
    else:
        print('???')




if __name__ == '__main__':
    pushplus_token = ''
    online_appid = [
        {'online': '1111111', 'appid': '2222222'},
        # {'online': '', 'appid': ''},
        # {'online': '', 'appid': ''},
        # {'online': '', 'appid': ''},
        # {'online': '', 'appid': ''},
    ]

    for i in online_appid:
        task()