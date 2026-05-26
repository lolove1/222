#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Date: 2025-09-21
# @LastEditTime: 2025-09-21

"""
🚀 吾爱破解论坛自动签到脚本 - 多账号支持版-v1.1
变量名：PJ52_COOKIE  多账号 @ 或 换行 
每个cookie需包含 htVC_2132_saltkey 和 htVC_2132_auth字段，否则该账号会被自动跳过。
From:yaohuo28507
cron: 10 8,20 * * *
"""
import os
import re
import sys
from datetime import datetime
import execjs  # pip install pyexecjs
import requests
import urllib3
from bs4 import BeautifulSoup


js_content = """function fp_info_generate(e){var a={errors:{}};for(var i in e){var r=e[i],t=r.key,n=r.value;"string"==typeof n&&-1!=n.indexOf("Error: ")?a.errors[t]=n:a[t]=n}var o=new Date;return a.dateTime={timestamp:o.getTime()},a.fp="bd5db91d97ce71f00bf0b3eb63790c74",a.protocol="https",setVerify(a),a}function setVerify(e){var a=e.dateTime.timestamp%10||10;for(var i in e){var r=e[i];if("object"==typeof r){var t=0;for(var n in r){var o=r[n];"number"==typeof o?t+=parseInt(o):"string"==typeof o?t+=o.length:t+=a}t&&(e[i].verify=t*a)}}}function anwser_gernerate(){for(var e=0,a=1,i=0;i<LZ.length;i++)e=2*(e+LZ.charCodeAt(i)),a=2*(a+i+1);return e*=LJ,"WZWS_CONFIRM_PREFIX_LABEL"+(e+=a)}function encodebody(e){e=JSON.stringify(e);var a,i,r,t,n,o,f=LE;for(r=e.length,i=0,a="";i<r;){if(t=255&e.charCodeAt(i++),i==r){a+=f.charAt(t>>2),a+=f.charAt((3&t)<<4),a+="==";break}if(n=e.charCodeAt(i++),i==r){a+=f.charAt(t>>2),a+=f.charAt((3&t)<<4|(240&n)>>4),a+=f.charAt((15&n)<<2),a+="=";break}o=e.charCodeAt(i++),a+=f.charAt(t>>2),a+=f.charAt((3&t)<<4|(240&n)>>4),a+=f.charAt((15&n)<<2|(192&o)>>6),a+=f.charAt(63&o)}return a}function getData(){return encodebody(encodeData)}encodeData={fp_infos:fp_info_generate(b=[{key:"plugins",value:{details:[{name:"PDF Viewer",description:"Portable Document Format",filename:"internal-pdf-viewer",mimetypes:[{type:"application/pdf",suffixes:"pdf"},{type:"text/pdf",suffixes:"pdf"}]},{name:"Chrome PDF Viewer",description:"Portable Document Format",filename:"internal-pdf-viewer",mimetypes:[{type:"application/pdf",suffixes:"pdf"},{type:"text/pdf",suffixes:"pdf"}]},{name:"Chromium PDF Viewer",description:"Portable Document Format",filename:"internal-pdf-viewer",mimetypes:[{type:"application/pdf",suffixes:"pdf"},{type:"text/pdf",suffixes:"pdf"}]},{name:"Microsoft Edge PDF Viewer",description:"Portable Document Format",filename:"internal-pdf-viewer",mimetypes:[{type:"application/pdf",suffixes:"pdf"},{type:"text/pdf",suffixes:"pdf"}]},{name:"WebKit built-in PDF",description:"Portable Document Format",filename:"internal-pdf-viewer",mimetypes:[{type:"application/pdf",suffixes:"pdf"},{type:"text/pdf",suffixes:"pdf"}]}],names:["Chrome PDF Viewer","Chromium PDF Viewer","Microsoft Edge PDF Viewer","PDF Viewer","WebKit built-in PDF"],fp:"9772d5556d57fcc8177f76029bfd92ef"}},{key:"fonts",value:{names:["Arial","Arial Black","Arial Narrow","Calibri","Cambria","Cambria Math","Comic Sans MS","Consolas","Courier","Courier New","Georgia","Helvetica","Impact","Lucida Console","Lucida Sans Unicode","Microsoft Sans Serif","MS Gothic","MS PGothic","MS Sans Serif","MS Serif","Palatino Linotype","Segoe Print","Segoe Script","Segoe UI","Segoe UI Light","Segoe UI Semibold","Segoe UI Symbol","Tahoma","Times","Times New Roman","Trebuchet MS","Verdana","Wingdings"],fp:"f730c0cc627b3b3d7db9f459836db692"}},{key:"screenObject",value:{screenResolution:[1920,1080],availableScreenResolution:[1920,1050],colorDepth:24,isExtended:void 0,availTop:0,availLeft:0,pixelDepth:24,top:0,left:0,orientation:{angle:0,type:"landscape-primary"}}},{key:"intlObject",value:{locale:"zh-Hans-CN",calendar:"gregory",numberingSystem:"latn",timeZone:"Asia/Shanghai",year:"numeric",month:"numeric",day:"numeric",timezoneOffset:-480}},{key:"touchSupport",value:[0,!1,!1]},{key:"audio",value:"35.749968223273754"},{key:"webdriver",value:!1},{key:"webGL",value:{webgl_version:"WebGL 1.0",webgl_vendor_and_renderer:"Google Inc. (Intel)~ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0), or similar",webgl_unmasked_renderer:"ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0), or similar",webgl_unmasked_vendor:"Google Inc. (Intel)",webgl_aliased_point_size_range:[1,1024],webgl_fragment_shader_medium_int_precision_rangeMax:30,webgl_fragment_shader_medium_int_precision_rangeMin:31,fp:"9631a557b3fdf1c28cfbd6500ad35bc8"}},{key:"canvas",value:{canvas_winding:!0,fp:"da766c3ea7221c96d06cf280d3a4e60a"}},{key:"deviceInfos",value:{deviceMemory:void 0,hardwareConcurrency:8}},{key:"storageObject",value:{localStorage:!0,openDatabase:!1,indexedDb:!0,sessionStorage:!0,addBehavior:!1}},{key:"navigatorObject",value:{userAgent:"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",platform:"Win32",vendor:"",language:"zh-CN",languages:["zh-CN","zh","zh-TW","zh-HK","en-US","en"],productSub:"20100101",oscpu:"Windows NT 10.0; Win64; x64"}},{key:"functions",value:{eval_tostring_length:37}}]),answer:anwser_gernerate(),hostname:"www.52pojie.cn",scheme:"https"};"""

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

proxies = None

def start_qiandao(session, url, headers, cookies, print_fn):
    print_fn("INFO", "开始签到")
    try:
        resp = session.get(url, headers=headers, cookies=cookies, proxies=proxies, verify=False)
        text = resp.text
        pattern_numbers = r".*='([0-9]{4,})'.*='([0-9]{4,})'.*"
        result = re.search(pattern_numbers, text, re.S)
        if not result:
            raise InterruptedError("没找到特征数字")
        para = f"var LZ ='{result.group(1)}',LJ='{result.group(2)}',"
        pattern_encryption = r".*='([a-zA-Z0-9/+]{40,})'.*"
        result = re.search(pattern_encryption, text, re.S)
        if not result:
            raise InterruptedError("没找到加密特征")
        para += f"LE='{result.group(1)}';"
        js = para + js_content
        result = execjs.compile(js).call("getData")
        resp = session.post("https://www.52pojie.cn/waf_zw_verify", headers=headers, cookies=cookies, proxies=proxies, data=result, verify=False)
        print_fn("INFO", f"签到结果: {resp.text}")
        session.get(url, headers=headers, cookies=cookies, proxies=proxies, verify=False)
        home(print_fn, cookies, check=True)
    except Exception as e:
        print_fn("ERROR", f"签到过程出错: {e}")

def home(print_fn, cookie_dict, check=False):
    session = requests.session()
    site_url = "https://www.52pojie.cn/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://www.52pojie.cn/",
    }
    try:
        response = session.get(url=site_url, cookies=cookie_dict, headers=headers, proxies=proxies, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        login_button = soup.find('button', class_="pn vm")
        if login_button is None:
            qiandao_imgs = [img for img in soup.find_all('img', class_="qq_bind") if img.get("src").endswith(("qds.png", "wbs.png"))]
            if not qiandao_imgs:
                print_fn("ERROR", "获取签到标志失败")
                return
            qiandao_img = qiandao_imgs[0]
            if qiandao_img.get("src").endswith("qds.png"):
                print_fn("INFO", "未签到")
                if not check:
                    start_qiandao(session, site_url + qiandao_img.parent.get("href"), headers, cookie_dict, print_fn)
            else:
                print_fn("INFO", "已签到")
        else:
            print_fn("ERROR", "登录失效，请更新 cookie 中的 htVC_2132_auth、htVC_2132_saltkey")
    except Exception as e:
        print_fn("ERROR", f"获取主页信息出错: {e}")

def parse_cookie(cookie):
    cookie_dict = {}
    for item in cookie.split(";"):
        if "=" in item:
            key, value = item.strip().split("=", 1)
            if key in ["htVC_2132_saltkey", "htVC_2132_auth"]:
                cookie_dict[key] = value
    return cookie_dict

if __name__ == "__main__":
    raw_cookie = os.getenv('PJ52_COOKIE')
    if not raw_cookie:
        print("未找到环境变量 PJ52_COOKIE，请检查环境变量设置。")
        sys.exit()
    
    # 支持 @ 或换行分割
    cookie_strs = [c.strip() for c in re.split(r'@|\n', raw_cookie) if c.strip()]
    
    # --- 新增：用于统计和生成美化后消息的变量 ---
    start_time = datetime.now()
    account_results = []
    success_count = 0
    already_signed_in_count = 0
    failure_count = 0
    
    for idx, cookie in enumerate(cookie_strs, 1):
        log_lines = []
        # 将日志消息暂存，而不是立即打印
        def print_fn(level, msg):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            line = f"{now} {level} {msg}"
            # 可以在这里打印到控制台，方便调试
            print(line)
            log_lines.append(line)

        cookie_dict = parse_cookie(cookie)
        account_name = f"账号{idx}"
        status_icon = "⚪" # 默认状态
        status_text = "处理中..."
        error_info = ""

        if not all(k in cookie_dict for k in ["htVC_2132_saltkey", "htVC_2132_auth"]):
            failure_count += 1
            status_icon = "❌"
            status_text = "配置错误"
            error_info = "Cookie 缺少必要字段"
            print_fn("ERROR", f"{account_name} {error_info}")
        else:
            print_fn("INFO", f"==== 开始处理 {account_name} ====")
            try:
                home(print_fn, cookie_dict)
                # --- 分析日志来判断最终状态 ---
                log_str = "\n".join(log_lines)
                if "登录失效" in log_str or "ERROR" in log_str:
                    failure_count += 1
                    status_icon = "❌"
                    status_text = "执行失败"
                    # 提取最后一条错误信息
                    last_error = next((line for line in reversed(log_lines) if "ERROR" in line), "未知错误")
                    error_info = last_error.split("ERROR", 1)[-1].strip()
                elif "签到结果: ok" in log_str:
                    success_count += 1
                    status_icon = "✅"
                    status_text = "签到成功"
                elif "已签到" in log_str:
                    already_signed_in_count += 1
                    status_icon = "✔️"
                    status_text = "今日已签"
                else:
                    failure_count += 1
                    status_icon = "❓"
                    status_text = "状态未知"
                    error_info = "未能确定签到状态，请检查日志"
            except Exception as e:
                failure_count += 1
                status_icon = "❌"
                status_text = "执行异常"
                error_info = str(e)
                print_fn("ERROR", f"{account_name} 处理异常: {e}")
            print_fn("INFO", f"==== {account_name} 处理结束 ====")
        
        # 构建单个账号的结果行
        result_line = f"👤 {account_name}: {status_icon} {status_text}"
        if error_info:
            result_line += f"\n   └ 详情: {error_info}"
        account_results.append(result_line)

    end_time = datetime.now()
    duration = (end_time - start_time).seconds
    
    # --- 构建最终的推送消息 ---
    total_accounts = len(cookie_strs)
    
    # 标题
    push_title = "吾爱破解论坛 - 签到报告"
    
    # 内容
    summary = (
        f"📊 **签到概览**\n"
        f"总计: {total_accounts} | "
        f"成功: {success_count} | "
        f"已签: {already_signed_in_count} | "
        f"失败: {failure_count}\n"
        #f"🕒 **执行耗时**: {duration}秒\n"
        f"--------------------\n"
    )
    
    details = "\n\n".join(account_results)
    
    final_message = summary + details
    
    # 发送通知
    try:
        import notify
        notify.send(push_title, final_message)
    except ImportError:
        print("\n" + "="*50)
        print(f"📢 {push_title}")
        print("="*50)
        print(final_message)
        print("="*50)
        print("\n💡 提示: 如需推送通知功能，请安装 notify 模块")
