import hashlib
import os
import time
import random
from datetime import datetime
import requests
from typing import List, Dict, Any

# 企业微信机器人模块（优化版，含表情符号）
class WeComRobot:
    @staticmethod
    def send_text_notice(title: str, content: str) -> None:
        webhook = os.getenv("WEWORK_WEBHOOK")  # 从环境变量获取企业微信webhook
        if not webhook:
            print("未配置企业微信机器人webhook ❗")
            return
        
        # 增加表情符号的文本格式化（关键修改）
        formatted_content = f"🎉【{title}】🎉\n"
        formatted_content += "——————————————————————\n"
        # 替换统计项符号为表情（成功/失败/总数）
        formatted_content += content.replace(
            "- 总贴吧数:", "📚 总贴吧数:").replace(
            "- 成功/已签到:", "✅ 成功/已签到:").replace(
            "- 失败数:", "❌ 失败数:").replace(
            "- 失败贴吧:", "🚫 失败贴吧:").replace(
            "- 总用户数:", "👥 总用户数:").replace(
            "- 成功率:", "📊 成功率:")
        formatted_content += "\n——————————————————————"
 
        # 企业微信文本消息格式
        data = {
            "msgtype": "text",
            "text": {
                "content": formatted_content
            }
        }
        
        try:
            response = requests.post(webhook, json=data)
            response.raise_for_status()
            result = response.json()
            if result.get("errcode") == 0:
                print("企业微信消息发送成功 ✅")
            else:
                print(f"企业微信消息发送失败: {result.get('errmsg', '未知错误')} ❌")
        except Exception as e:
            print(f"企业微信消息发送异常: {str(e)} ⚠️")
 
    @staticmethod
    def send_markdown(title: str, content: str) -> None:  # 保留原markdown方法
        webhook = os.getenv("WEWORK_WEBHOOK")
        if not webhook:
            print("未配置企业微信机器人webhook ❗")
            return
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"### {title}\n\n{content}"
            }
        }
        
        try:
            response = requests.post(webhook, json=data)
            response.raise_for_status()
            result = response.json()
            if result.get("errcode") == 0:
                print("企业微信消息发送成功 ✅")
            else:
                print(f"企业微信消息发送失败: {result.get('errmsg', '未知错误')} ❌")
        except Exception as e:
            print(f"企业微信消息发送异常: {str(e)} ⚠️")

# 日志系统
class Logger:
    def __init__(self, name: str):
        self.name = name

    def _format_time(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _log(self, level: str, message: str, prefix: str = "") -> None:
        level_colors = {
            "INFO": "\033[32m",  # 绿色
            "ERROR": "\033[31m",  # 红色
            "WARN": "\033[33m",   # 黄色
            "DEBUG": "\033[36m"   # 青色
        }
        color = level_colors.get(level, "\033[0m")
        reset = "\033[0m"
        print(f"{color}[{self._format_time()}] [{level.ljust(5)}] [{self.name}]{prefix} {message}{reset}")

    def info(self, message: str) -> None:
        self._log("INFO", message)

    def error(self, message: str) -> None:
        self._log("ERROR", message)

    def warn(self, message: str) -> None:
        self._log("WARN", message)

    def debug(self, message: str) -> None:
        self._log("DEBUG", message)

    def group(self, title: str, index: int = None, total: int = None) -> None:
        index_str = f" ({index}/{total})" if index is not None and total is not None else ""
        self._log("INFO", f"{title}{index_str}")

    def group_end(self, title: str) -> None:
        self._log("INFO", title)
        print()  # 空行分隔

    def sign_result(self, forum_name: str, index: int, total: int, result: Dict[str, Any]) -> None:
        code = result.get("error_code", "200")
        status = "成功" if code == "0" else "已签到" if code == "160002" else "失败"
        color = "\033[32m" if code in ("0", "160002") else "\033[31m"
        reset = "\033[0m"
        
        self._log("INFO", f"签到 \"{forum_name}\" 贴吧 ({index}/{total}) {color}[{status}]{reset}")
        self.debug(f"  结果码: {code}")
        self.debug(f"  提示信息: {result.get('error_msg', '无')}")

        if code == "0" and result.get("user_info"):
            user_info = result["user_info"]
            self.info("  用户签到详情:")
            self.info(f"    签到排名: {user_info.get('user_sign_rank', '无')}")
            self.info(f"    连续签到: {user_info.get('cont_sign_num', '无')} 天")
            self.info(f"    总签到数: {user_info.get('total_sign_num', '无')} 次")
            self.info(f"    本次获得经验: {user_info.get('sign_bonus_point', '无')}")
            self.info(f"    当前等级: {user_info.get('level_name', '无')} ({user_info.get('levelup_score', '无')}经验升级)")
        print()

# 常量定义
HEADERS = {
    "Host": "tieba.baidu.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36"
}

SIGN_DATA = {
    "_client_type": "2",
    "_client_version": "9.7.8.0",
    "_phone_imei": "000000000000000",
    "model": "MI+5",
    "net_type": "1"
}

LIKE_URL = "http://c.tieba.baidu.com/c/f/forum/like"
TBS_URL = "http://tieba.baidu.com/dc/common/tbs"
SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"

class TiebaAutoSign:
    logger = Logger("tieba")
    SIGN_KEY = "tiebaclient!!!"

    @staticmethod
    def encode_data(data: Dict[str, str]) -> Dict[str, str]:
        """编码请求数据并生成签名"""
        sorted_keys = sorted(data.keys())
        sign_str = "".join([f"{k}={data[k]}" for k in sorted_keys]) + TiebaAutoSign.SIGN_KEY
        sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()
        return {**data, "sign": sign}

    @staticmethod
    def get_tbs(bduss: str) -> str:
        """获取TBS令牌（含重试机制）"""
        TiebaAutoSign.logger.group("获取TBS令牌")
        for attempt in range(2):
            try:
                response = requests.get(
                    TBS_URL,
                    headers={**HEADERS, "Cookie": f"BDUSS={bduss}"}
                )
                response.raise_for_status()
                data = response.json()
                tbs = data.get("tbs", "")
                TiebaAutoSign.logger.info(f"获取成功，TBS: {tbs[:8]}...")
                TiebaAutoSign.logger.group_end("获取TBS令牌")
                return tbs
            except Exception as e:
                TiebaAutoSign.logger.error(f"操作失败（尝试{attempt+1}/2）: {str(e)}")
        
        TiebaAutoSign.logger.group_end("获取TBS令牌")
        raise Exception("获取TBS令牌失败，已尝试两次")

    @staticmethod
    def get_favorite(bduss: str) -> List[Dict[str, str]]:
        """获取关注的贴吧列表"""
        TiebaAutoSign.logger.group("获取关注的贴吧列表")
        forums = []
        page_no = 1
        has_more = True
        total = 0

        while has_more:
            try:
                data = {
                    "BDUSS": bduss,
                    "_client_id": "wappc_1534235498291_488",
                    "from": "1008621y",
                    "page_no": str(page_no),
                    "page_size": "200",
                    "timestamp": str(int(time.time())),
                    "vcode_tag": "11",
                    **SIGN_DATA
                }
                encoded_data = TiebaAutoSign.encode_data(data)
                response = requests.post(
                    LIKE_URL,
                    headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                    data=encoded_data
                )
                response.raise_for_status()
                res_data = response.json()
                
                forum_list = res_data.get("forum_list", {})
                non_gconforum = forum_list.get("non-gconforum", [])
                gconforum = forum_list.get("gconforum", [])
                page_forums = [{"id": f["id"], "name": f["name"]} 
                              for f in [*non_gconforum, *gconforum] if f.get("id") and f.get("name")]
                
                forums.extend(page_forums)
                total += len(page_forums)
                has_more = res_data.get("has_more") == "1"
                page_no += 1
                TiebaAutoSign.logger.debug(f"第 {page_no-1} 页，获取 {len(page_forums)} 个贴吧")
            except Exception as e:
                TiebaAutoSign.logger.error(f"获取失败: {str(e)}")
                break

        TiebaAutoSign.logger.info(f"成功获取 {total} 个贴吧")
        TiebaAutoSign.logger.group_end("获取关注的贴吧列表")
        return forums

    @staticmethod
    def client_sign(bduss: str, tbs: str, fid: str, kw: str) -> Dict[str, Any]:
        """执行单个贴吧签到"""
        try:
            data = {
                **SIGN_DATA,
                "BDUSS": bduss,
                "fid": fid,
                "kw": kw,
                "tbs": tbs,
                "timestamp": str(int(time.time()))
            }
            encoded_data = TiebaAutoSign.encode_data(data)
            response = requests.post(
                SIGN_URL,
                headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                data=encoded_data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            TiebaAutoSign.logger.error(f"签到异常: {str(e)}")
            return {"error_code": "99999", "error_msg": "签到请求异常"}

    @staticmethod
    def random_delay(min_ms: int = 500, max_ms: int = 2000) -> None:
        """随机延时"""
        delay = random.randint(min_ms, max_ms) / 1000
        TiebaAutoSign.logger.debug(f"等待 {int(delay*1000)}ms 后继续")
        time.sleep(delay)

    @staticmethod
    def sign_for_user(bduss: str) -> Dict[str, Any]:
        """执行单个用户签到流程"""
        TiebaAutoSign.logger.group("用户签到流程")
        user_id = bduss[:8]
        stats = {
            "user_id": user_id,
            "total_forums": 0,
            "successful_signs": 0,
            "failed_signs": 0,
            "failed_forums": []
        }

        try:
            tbs = TiebaAutoSign.get_tbs(bduss)
            favorites = TiebaAutoSign.get_favorite(bduss)
            stats["total_forums"] = len(favorites)

            if not favorites:
                TiebaAutoSign.logger.warn("未获取到关注的贴吧")
                TiebaAutoSign.logger.group_end("用户签到流程")
                return stats

            TiebaAutoSign.logger.info(f"开始签到 {len(favorites)} 个贴吧")
            for idx, forum in enumerate(favorites, 1):
                TiebaAutoSign.random_delay()
                result = TiebaAutoSign.client_sign(bduss, tbs, forum["id"], forum["name"])
                code = result.get("error_code", "200")

                if code in ("0", "160002"):
                    stats["successful_signs"] += 1
                else:
                    stats["failed_signs"] += 1
                    stats["failed_forums"].append(forum["name"])

                TiebaAutoSign.logger.sign_result(forum["name"], idx, len(favorites), result)

            TiebaAutoSign.logger.info("所有贴吧签到完成")
        except Exception as e:
            TiebaAutoSign.logger.error(f"用户签到失败: {str(e)}")
            stats["failed_signs"] = stats["total_forums"]
            stats["failed_forums"] = ["签到过程中发生异常"]
        finally:
            TiebaAutoSign.logger.group_end("用户签到流程")
            return stats

    @staticmethod
    def sign_all_users() -> List[Dict[str, Any]]:
        """执行所有用户签到并收集统计"""
        TiebaAutoSign.logger.group("批量签到任务")
        bduss_list = os.getenv("BDUSS", "").split("#") if os.getenv("BDUSS") else []
        all_stats = []

        if not bduss_list:
            TiebaAutoSign.logger.error("未配置 BDUSS 环境变量")
            TiebaAutoSign.logger.group_end("批量签到任务")
            raise Exception("BDUSS not configured")

        TiebaAutoSign.logger.info(f"发现 {len(bduss_list)} 个用户")
        for idx, bduss in enumerate(bduss_list, 1):
            TiebaAutoSign.logger.group(f"处理用户 #{idx}/{len(bduss_list)}")
            TiebaAutoSign.logger.info(f"用户 #{idx} BDUSS: {bduss[:8]}...")
            try:
                stats = TiebaAutoSign.sign_for_user(bduss)
                all_stats.append(stats)
            except Exception as e:
                TiebaAutoSign.logger.error(f"用户 #{idx} 签到异常: {str(e)}")
                all_stats.append({
                    "user_id": bduss[:8],
                    "total_forums": 0,
                    "successful_signs": 0,
                    "failed_signs": 0,
                    "failed_forums": ["签到过程中发生异常"]
                })
            finally:
                TiebaAutoSign.logger.group_end(f"处理用户 #{idx}/{len(bduss_list)}")

        TiebaAutoSign.logger.info("所有用户签到任务完成")
        TiebaAutoSign.logger.group_end("批量签到任务")
        return all_stats

    @staticmethod
    def generate_summary(stats_list: List[Dict[str, Any]]) -> str:
        """生成签到总结Markdown"""
        summary = "### 贴吧签到总结\n\n#### 今日签到统计\n\n"
        for idx, stats in enumerate(stats_list, 1):
            summary += f"**用户 {idx} ({stats['user_id']})**\n"
            summary += f"- 总贴吧数: {stats['total_forums']}\n"
            summary += f"- 成功/已签到: {stats['successful_signs']}\n"
            summary += f"- 失败数: {stats['failed_signs']}\n"
            if stats["failed_signs"] > 0:
                summary += f"- 失败贴吧: {', '.join(stats['failed_forums'])}\n"
            summary += "\n"

        total_forums = sum(s["total_forums"] for s in stats_list)
        total_success = sum(s["successful_signs"] for s in stats_list)
        total_failed = sum(s["failed_signs"] for s in stats_list)
        success_rate = (total_success / total_forums * 100) if total_forums else 0

        summary += "#### 全局统计\n"
        summary += f"- 总用户数: {len(stats_list)}\n"
        summary += f"- 总贴吧数: {total_forums}\n"
        summary += f"- 成功/已签到数: {total_success}\n"
        summary += f"- 失败数: {total_failed}\n"
        summary += f"- 成功率: {success_rate:.2f}%\n"
        return summary

async def main():
    try:
        stats_list = TiebaAutoSign.sign_all_users()
        summary = TiebaAutoSign.generate_summary(stats_list)
        print(f"\n{summary}")
        # 调用企业微信机器人发送文字版通知（优化后）
        WeComRobot.send_text_notice("贴吧签到提醒", summary)
    except Exception as e:
        error_msg = f"### 贴吧签到异常\n[程序错误] {str(e)}"
        print(f"\033[31m{error_msg}\033[0m")
        try:
            # 错误通知也使用文字版
            WeComRobot.send_text_notice("贴吧签到异常提醒", error_msg)
        except Exception as send_e:
            print(f"发送错误通知失败: {str(send_e)}")
        os._exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())