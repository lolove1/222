// 当前脚本来自于 https://jb.3add.cn 脚本分享下载！
// 更多脚本获取 https://pan.quark.cn/s/9dd555d3210d
// 脚本库交流QQ群: 480383815
// 脚本呆瓜QQ群: 958310806
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。

﻿// 当前脚本来自于 https://jb.3add.cn 脚本分享下载！
// 更多脚本获取 https://pan.quark.cn/s/9dd555d3210d
// 脚本库交流QQ群: 480383815
// 脚本呆瓜QQ群: 958310806
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。

/*
使用说明：
1. 在运行前设置环境变量名称 ZSP，值：定义备注#secretId#secretKey#deviceId。
3. 数值入口：面板进入“商户密匙”模块获取 SecretId#SecretKey，并填写设备码。
4. 多账号请使用换行分隔。
5. 可选环境变量：ZSP_MAX_ADS 控制单账号最大执行次数，默认 50；ZSP_TIMEOUT 控制请求超时时间，默认 15000 毫秒。
6. 运行命令：node 中视频.js。
7. 注册链接：https://zsp.99panel.top/#/register?inviteCode=MxlrzRo0
8. 下载：https://apka.o3oh4.com/new_apk/download.html?id=zsp/1
9. 免责声明：本内容仅为互联网项目资讯分享，不构成任何投资建议。平台规则、奖励机制、活动内容可能随时调整，请以官方公告为准。参与者需自行判断风险，理性参与。请勿借贷、充值或投入超出自身承受能力的资金。本人仅作信息分享，不对平台后续运营及相关结果承担责任。
https://nos.netease.com/ysf/5decaf27413783c65d0dfe0b422dc7ed.png
*/

const http = require("http");
const https = require("https");

const ENV_NAME = "中视频";
const BASE_URL = "https://x1.zsptv.online";
const USER_AGENT = "Mozilla/5.0 (Linux; Android 15; 23013RK75C Build/AQ3A.250226.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.260 Mobile Safari/537.36 (Immersed/39.42857) Html5Plus/1.0";
const REQUEST_TIMEOUT = readPositiveInteger(process.env.ZSP_TIMEOUT, 15000);
const MAX_ADS = readPositiveInteger(process.env.ZSP_MAX_ADS, 50);
const ACCOUNT_ENV_NAMES = ["ZSP", "AD_WATCH_ACCOUNTS"];

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function readPositiveInteger(value, fallback) {
  const num = Number.parseInt(value, 10);
  return Number.isFinite(num) && num > 0 ? num : fallback;
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function createRequestId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function maskValue(value) {
  if (!value) return "";
  const text = String(value);
  if (text.length <= 8) return "***";
  return `${text.slice(0, 4)}***${text.slice(-4)}`;
}

function sanitizeErrorMessage(message) {
  return String(message || "未知错误")
    .replace(/Bearer\s+[A-Za-z0-9._\-]+/gi, "Bearer ***")
    .replace(/secretKey[=:]\s*[^\s,#&]+/gi, "secretKey=***")
    .replace(/token[=:]\s*[^\s,#&]+/gi, "token=***");
}

function log(level, message, meta = {}) {
  const safeMeta = { ...meta };
  for (const key of Object.keys(safeMeta)) {
    if (/token|authorization|cookie|secret/i.test(key)) {
      safeMeta[key] = maskValue(safeMeta[key]);
    }
  }
  const suffix = Object.keys(safeMeta).length ? ` ${JSON.stringify(safeMeta)}` : "";
  console.log(`[${new Date().toISOString()}] [${level}] ${message}${suffix}`);
}

function decodeUnicode(str) {
  if (!str) return "";
  return String(str).replace(/\\u[\dA-F]{4}/gi, match => String.fromCharCode(Number.parseInt(match.replace(/\\u/g, ""), 16)));
}

function parseJson(text, fallback = null) {
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

function buildDeviceHeader(account) {
  return JSON.stringify({
    id: account.deviceId,
    brand: "xiaomi",
    model: "23013RK75C",
    platform: "android",
    system: "Android 15"
  });
}

function buildHeaders(account, token = "") {
  const headers = {
    Accept: "*/*",
    "User-Agent": USER_AGENT,
    "app-device": buildDeviceHeader(account),
    "Content-Type": "application/json",
    Host: "x1.zsptv.online"
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

async function httpRequest(options) {
  const requestId = options.requestId || createRequestId();
  const url = new URL(options.url);
  const transport = url.protocol === "https:" ? https : http;
  const body = options.body || "";

  return new Promise((resolve, reject) => {
    const req = transport.request({
      hostname: url.hostname,
      port: url.port || (url.protocol === "https:" ? 443 : 80),
      path: url.pathname + url.search,
      method: options.method || "GET",
      headers: options.headers || {},
      timeout: options.timeout || REQUEST_TIMEOUT
    }, res => {
      let data = "";

      res.setEncoding("utf8");
      res.on("data", chunk => {
        data += chunk;
      });
      res.on("end", () => {
        resolve({
          requestId,
          statusCode: res.statusCode,
          headers: res.headers,
          body: data
        });
      });
    });

    req.on("timeout", () => {
      req.destroy(new Error(`请求超时 ${REQUEST_TIMEOUT}ms`));
    });

    req.on("error", err => {
      err.requestId = requestId;
      reject(err);
    });

    if (body) {
      req.write(body);
    }

    req.end();
  });
}

async function requestJson(options) {
  const requestId = createRequestId();
  try {
    const response = await httpRequest({ ...options, requestId });
    const data = parseJson(response.body);
    const summary = response.body ? response.body.slice(0, 160) : "";

    log("INFO", "请求完成", {
      requestId,
      method: options.method || "GET",
      path: new URL(options.url).pathname,
      statusCode: response.statusCode
    });

    if (response.statusCode < 200 || response.statusCode >= 300) {
      log("WARNING", "响应状态异常", {
        requestId,
        statusCode: response.statusCode,
        summary: sanitizeErrorMessage(summary)
      });
    }

    if (!data) {
      return {
        ok: false,
        requestId,
        statusCode: response.statusCode,
        data: null,
        message: "响应不是有效 JSON"
      };
    }

    return {
      ok: response.statusCode >= 200 && response.statusCode < 300,
      requestId,
      statusCode: response.statusCode,
      data,
      message: decodeUnicode(data.message || "")
    };
  } catch (error) {
    log("ERROR", "请求异常", {
      requestId,
      message: sanitizeErrorMessage(error.message)
    });
    return {
      ok: false,
      requestId,
      statusCode: 0,
      data: null,
      message: sanitizeErrorMessage(error.message)
    };
  }
}

function loadAccounts() {
  const accounts = [];
  let envValue = "";
  let matchedEnvName = "";

  for (const envName of ACCOUNT_ENV_NAMES) {
    if (process.env[envName]) {
      envValue = process.env[envName];
      matchedEnvName = envName;
      break;
    }
  }

  if (!envValue) {
    log("WARNING", "请设置环境变量 ZSP 或 AD_WATCH_ACCOUNTS");
    return accounts;
  }

  log("INFO", "读取账号配置", { envName: matchedEnvName });

  const rows = envValue.split("\n").map(item => item.trim()).filter(Boolean);

  rows.forEach((row, index) => {
    const parts = row.split("#").map(item => item.trim());
    if (parts.length < 4 || !parts[1] || !parts[2] || !parts[3]) {
      log("WARNING", "忽略格式错误的账号配置", { index: index + 1 });
      return;
    }

    accounts.push({
      remark: parts[0] || `账号${index + 1}`,
      secretId: parts[1],
      secretKey: parts[2],
      deviceId: parts[3]
    });

    log("INFO", "账号配置已加载", {
      index: index + 1,
      remark: parts[0] || `账号${index + 1}`,
      secretId: maskValue(parts[1]),
      deviceId: maskValue(parts[3])
    });
  });

  return accounts;
}

async function login(account) {
  const result = await requestJson({
    url: `${BASE_URL}/api/app/v1/auth/secretKeyLogin`,
    method: "POST",
    headers: buildHeaders(account),
    body: JSON.stringify({
      secretId: account.secretId,
      secretKey: account.secretKey
    })
  });

  if (!result.ok) {
    log("ERROR", "登录请求失败", {
      requestId: result.requestId,
      remark: account.remark,
      statusCode: result.statusCode,
      message: result.message
    });
    return "";
  }

  if (result.data.code === 0 && result.data.data && result.data.data.token) {
    log("INFO", "登录成功", {
      requestId: result.requestId,
      remark: account.remark,
      token: result.data.data.token
    });
    return result.data.data.token;
  }

  log("ERROR", "登录失败", {
    requestId: result.requestId,
    remark: account.remark,
    message: result.message || "未知错误"
  });
  return "";
}

async function checkAndSign(token, account) {
  const result = await requestJson({
    url: `${BASE_URL}/api/app/v1/device/userSign`,
    method: "POST",
    headers: buildHeaders(account, token),
    body: "{}"
  });

  if (!result.ok) {
    log("ERROR", "签到请求失败", {
      requestId: result.requestId,
      remark: account.remark,
      statusCode: result.statusCode,
      message: result.message
    });
    return false;
  }

  if (result.data.code === 0) {
    log("INFO", "签到成功", {
      requestId: result.requestId,
      remark: account.remark,
      message: result.message,
      reward: result.data.data?.qiandao_money || 0,
      continuousDays: result.data.data?.continuousDays || 1
    });
    return true;
  }

  if (result.message.includes("已签到")) {
    log("INFO", "今日已签到", {
      requestId: result.requestId,
      remark: account.remark
    });
    return true;
  }

  log("ERROR", "签到失败", {
    requestId: result.requestId,
    remark: account.remark,
    message: result.message || "未知错误"
  });
  return false;
}

async function getNextAd(token, account) {
  const result = await requestJson({
    url: `${BASE_URL}/api/app/v1/ad/next`,
    method: "GET",
    headers: buildHeaders(account, token)
  });

  if (!result.ok) {
    log("ERROR", "获取广告失败", {
      requestId: result.requestId,
      remark: account.remark,
      statusCode: result.statusCode,
      message: result.message
    });
    return null;
  }

  if (result.data.code !== 0 || !result.data.data || !result.data.data.result) {
    log("WARNING", "未获取到广告数据", {
      requestId: result.requestId,
      remark: account.remark,
      message: result.message || "未知错误"
    });
    return null;
  }

  const ad = result.data.data.result;
  return {
    id: ad.id,
    title: decodeUnicode(ad.title),
    description: decodeUnicode(ad.description),
    duration: readPositiveInteger(ad.video?.duration, 30),
    videoUrl: ad.video?.url || "",
    playUrl: ad.video?.play_url || "",
    reward: ad.reward || 0
  };
}

async function startVideoPlay(token, account, adId, playTime) {
  const result = await requestJson({
    url: `${BASE_URL}/api/app/v1/ad/video/play`,
    method: "POST",
    headers: buildHeaders(account, token),
    body: JSON.stringify({
      clientIp: "",
      deviceInfo: {
        deviceId: account.deviceId,
        platform: "android"
      },
      id: String(adId),
      playTime
    })
  });

  if (!result.ok) {
    log("ERROR", "开始播放请求失败", {
      requestId: result.requestId,
      remark: account.remark,
      statusCode: result.statusCode,
      message: result.message
    });
    return null;
  }

  if (result.data.code === 0 && result.data.data && result.data.data.id) {
    return {
      playRecordId: result.data.data.id,
      initialReward: result.data.data.reward || 0,
      reward: result.data.data.reward || 0
    };
  }

  log("ERROR", "开始播放失败", {
    requestId: result.requestId,
    remark: account.remark,
    message: result.message || "未知错误"
  });
  return null;
}

async function endVideoPlay(token, account, playRecordId) {
  const result = await requestJson({
    url: `${BASE_URL}/api/app/v1/ad/video/ended`,
    method: "POST",
    headers: buildHeaders(account, token),
    body: JSON.stringify({
      clientIp: "",
      deviceInfo: {
        deviceId: account.deviceId,
        platform: "android"
      },
      id: String(playRecordId),
      playTime: new Date().toISOString()
    })
  });

  if (!result.ok) {
    log("WARNING", "结束确认请求失败", {
      requestId: result.requestId,
      remark: account.remark,
      statusCode: result.statusCode,
      message: result.message
    });
    return false;
  }

  if (result.data.code === 0) {
    return true;
  }

  log("WARNING", "结束确认返回异常", {
    requestId: result.requestId,
    remark: account.remark,
    message: result.message || "未知错误"
  });
  return false;
}

async function claimReward(token, account, adInfo) {
  const startTime = new Date().toISOString();

  log("INFO", "开始播放广告", {
    remark: account.remark,
    adId: adInfo.id,
    title: adInfo.title,
    duration: adInfo.duration,
    reward: adInfo.reward
  });

  const playResult = await startVideoPlay(token, account, adInfo.id, startTime);
  if (!playResult || !playResult.playRecordId) {
    return { success: false, reward: 0 };
  }

  log("INFO", "播放记录已创建", {
    remark: account.remark,
    playRecordId: playResult.playRecordId,
    initialReward: playResult.initialReward
  });

  await wait(adInfo.duration * 1000);

  const ended = await endVideoPlay(token, account, playResult.playRecordId);
  if (!ended) {
    return {
      success: false,
      reward: 0,
      playRecordId: playResult.playRecordId
    };
  }

  return {
    success: true,
    reward: playResult.reward || 0,
    playRecordId: playResult.playRecordId
  };
}

async function processAccount(account) {
  let token = await login(account);
  if (!token) {
    log("ERROR", "登录失败，跳过账号", { remark: account.remark });
    return;
  }

  const signed = await checkAndSign(token, account);
  if (!signed) {
    log("ERROR", "签到未完成，跳过账号", { remark: account.remark });
    return;
  }

  let successCount = 0;
  let failCount = 0;
  let totalReward = 0;
  let consecutiveErrors = 0;

  for (let adCount = 0; adCount < MAX_ADS; adCount++) {
    log("INFO", "开始处理任务", {
      remark: account.remark,
      current: adCount + 1,
      total: MAX_ADS
    });

    if (consecutiveErrors >= 3) {
      log("WARNING", "连续失败，尝试刷新登录状态", { remark: account.remark });
      token = await login(account);
      if (!token) {
        log("ERROR", "刷新登录状态失败，停止当前账号", { remark: account.remark });
        break;
      }
      consecutiveErrors = 0;
    }

    const adInfo = await getNextAd(token, account);
    if (!adInfo) {
      failCount++;
      consecutiveErrors++;
      await wait(randomInt(2500, 5000));
      continue;
    }

    const playResult = await claimReward(token, account, adInfo);
    if (playResult.success) {
      successCount++;
      totalReward += Number.parseInt(playResult.reward, 10) || 0;
      consecutiveErrors = 0;
      log("INFO", "任务完成", {
        remark: account.remark,
        reward: playResult.reward || 0,
        playRecordId: playResult.playRecordId
      });
    } else {
      failCount++;
      consecutiveErrors++;
      log("WARNING", "任务失败", { remark: account.remark });
    }

    if (adCount < MAX_ADS - 1) {
      const delay = randomInt(3000, 6000);
      log("INFO", "等待后继续", {
        remark: account.remark,
        delaySeconds: Math.round(delay / 1000)
      });
      await wait(delay);
    }
  }

  log("INFO", "账号处理完成", {
    remark: account.remark,
    successCount,
    failCount,
    totalReward,
    successRate: `${((successCount / MAX_ADS) * 100).toFixed(1)}%`
  });
}

async function main() {
  log("INFO", "脚本开始运行", {
    envName: ENV_NAME,
    maxAds: MAX_ADS,
    timeout: REQUEST_TIMEOUT
  });

  const accounts = loadAccounts();
  if (accounts.length === 0) {
    log("ERROR", "未找到有效账号配置");
    return;
  }

  for (let i = 0; i < accounts.length; i++) {
    const account = accounts[i];
    log("INFO", "开始处理账号", {
      index: i + 1,
      total: accounts.length,
      remark: account.remark
    });

    try {
      await processAccount(account);
    } catch (error) {
      log("ERROR", "账号处理异常", {
        remark: account.remark,
        message: sanitizeErrorMessage(error.message)
      });
    }

    if (i < accounts.length - 1) {
      await wait(5000);
    }
  }

  log("INFO", "所有账号处理完成");
}

if (require.main === module) {
  main().catch(error => {
    log("ERROR", "脚本异常退出", {
      message: sanitizeErrorMessage(error.message)
    });
    process.exitCode = 1;
  });
}


// 当前脚本来自于 https://jb.3add.cn 脚本分享下载！
// 更多脚本获取 https://pan.quark.cn/s/9dd555d3210d
// 脚本库交流QQ群: 480383815
// 脚本呆瓜QQ群: 958310806
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。



// 当前脚本来自于 https://jb.3add.cn 脚本分享下载！
// 更多脚本获取 https://pan.quark.cn/s/9dd555d3210d
// 脚本库交流QQ群: 480383815
// 脚本呆瓜QQ群: 958310806
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。

