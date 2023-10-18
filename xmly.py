import time

import requests


class Xmly(object):
    def __init__(self, cookie):
        self.cookie = cookie
            "Cookie": self.cookie,
            'Content-Type': 'application/json'
        }

    def ad_video_get_token(self):
        url = 'http://m.ximalaya.com/web-activity/task/v2/genTaskToken'

        data = {
            "aid": 112,
            "taskId": 252
        }
        headers = self.headers
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            res_json = res.json()
            if res_json['ret'] == 0:
                self.ad_token = res_json['data']['token']
                return True
        return False

    def ad_video_finish(self):
        fail_num = 0
        while True:
            if_ = self.ad_video_get_token()
            if not if_:
                if fail_num >= 10:
                    print('获取token频繁失败,无法完成观看任务')
                    return
                time.sleep(3)
            url = 'http://m.ximalaya.com/web-activity/task/v2/incrTaskProgress'
            headers = self.headers
            data = {"aid": 112, "taskId": 252, "token": f"{self.ad_token}", "progress": 1}
            res = requests.post(url, headers=headers, json=data)
            if res.status_code == 200:
                res_json = res.json()
                if res_json['data']['status'] == 0:
                    print("- 本条视频广告观看已完成, 获得40点奖励")
                elif res_json['data']['status'] == -1:
                    print("🟢 今日视频任务已全部完成 ")
                    break
            time.sleep(3)

    def take_general_task(self, taskId):
        url = 'http://hybrid.ximalaya.com/web-activity/task/v2/refreshClientTask'
        data = {"aid": 112, "taskId": taskId}
        headers = self.headers
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            res_json = res.json()
            if res_json['data']['ret'] == 0:
                print(f'成功接取任务：{taskId}')
            elif res_json['data']['ret'] == -1:
                print(f'{taskId} 任务已接取')
            else:
                print('未知状态')
        else:
            print('！！！通用任务接取失败')

    def hand_in_general_task(self, taskId):
        url = 'http://m.ximalaya.com/web-activity/task/v2/drawTaskAward'
        headers = self.headers
        data = {"aid": 112, "taskId": taskId}
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            res_json = res.json()
            if res_json['ret'] == 0:
                if res_json['data']['status'] == 0:
                    if (173 < taskId > 167) or (taskId in [96, 217]):
                        print('- 交还特殊任务成功, 获得奖励点数')
                    else:
                        print('- 交还通用任务成功, 获得10点奖励')
                    return True
                elif res_json['data']['status'] == 1:
                    print('- 此项任务今日已交还')
                    return True
                elif res_json['data']['status'] == -1:
                    print('--- !!!此任务尚未完成,不能交还')
                    return False
                else:
                    print('--- !!!未知交还状态')
                    return False
            else:
                print('--- !!!交还任务失败')

    def common_tasks(self):
        common_task_list = [101, 143, 176, 177, 180, 260, 264]
        error_list = []
        success_list = []
        for common_task in common_task_list:
            self.take_general_task(common_task)
            if_ = self.hand_in_general_task(common_task)
            if if_:
                success_list.append(common_task)
            else:
                error_list.append(common_task)
        print('运行成功任务：', success_list)
        print('运行失败任务：', error_list)


if __name__ == '__main__':
    cookie = 'channel=ios-b1; 1&_device=iPhone&1B5C2B30-E0E7-4898-A6DA-2B4E2CE89D9C&9.1.76; impl=com.gemd.iting; 1&_token=257653107&EDA68460240CA205DD528182718AA26F7922936F54BED1EEBC6AB56F1FD8256E71F6608E0D5253M5076BE9CD94A14A_'
    xm = Xmly(cookie)
    xm.ad_video_finish()
    xm.common_tasks()
