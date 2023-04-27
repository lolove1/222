'''
cron: 15 9 * * * haluo.py
new Env('哈啰签到');
'''

import requests
import os
from notify import send
from os import environ

def qiandao(token):
    msg = ""
    url = "https://api.hellobike.com/api?common.welfare.signAndRecommend"
    headers = {
        'Host': 'api.hellobike.com',
        'origin': 'https://m.hellobike.com',
        'user-agent': 'Mozilla/5.0 (Linux; Android 12; 22081212C Build/SKQ1.220303.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/110.0.5481.153 Mobile Safari/537.36; app=easybike; version=6.36.0',
        'referer': 'https://m.hellobike.com/AppPlatformH5/latest/pr_index_bounty.html',
        'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    data = f'{{"from":"h5","systemCode":62,"platform":4,"version":"6.36.0","action":"common.welfare.signAndRecommend","token":"{token}"}}'
    response = requests.post(url=url, headers = headers, data = data)
    result = response.json()
#   print(type(result), result)
    if result['code'] == 0:
        bountyCountToday = result['data']['bountyCountToday']
        msg += f"签到获得奖励金: {bountyCountToday}\n"
        print(msg)
        msg +=chaxun(token)
    elif result['code'] == 103:
        msg += "token过期\n"
        print(msg)
    return msg

def chaxun(token):
    msg = ""
    url = "https://api.hellobike.com/api?user.taurus.pointInfo"
    headers = {
        'Host': 'api.hellobike.com',
        'user-agent': 'Mozilla/5.0 (Linux; Android 12; 22081212C Build/SKQ1.220303.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/110.0.5481.153 Mobile Safari/537.36; app=easybike; version=6.36.0',
        'origin': 'https://m.hellobike.com',
        'referer': 'https://m.hellobike.com/',
        'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    data = f'{{"from":"h5","systemCode":62,"platform":4,"version":"6.36.0","action":"user.taurus.pointInfo","token":"{token}","pointType":1}}'
    response = requests.post(url=url, headers = headers, data = data)
    result = response.json()
#        print(type(result1), result1)
    points = result['data']['points']
    expiring = result['data']['expiring']
    msg += f"当前奖励金: {points}， 月底将过期: {expiring}\n\n"
    print(msg)
    return msg
    
def ql_env():
    if "haluotoken" in os.environ:
        token_list = os.environ['haluotoken'].split('#')
        if len(token_list) > 0:
            return token_list
        else:
            print("haluotoken变量未启用")
            sys.exit(1)
    else:
        print("未添加haluotoken变量")
        sys.exit(0)

if __name__ == '__main__':
    msg = ""
    index = 1
    quantity = ql_env()
    print (f"共找到{len(quantity)}个账号")
    for token in quantity:
        print (f"------------正在执行第{index}个账号----------------")
        msg += f"第{str(index)}个账号运行结果: \n"
        msg += qiandao(token)
        index += 1
  #  print(msg)
    send('哈啰', msg)
