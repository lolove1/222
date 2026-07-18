// ===== SCRIPT HUB NOTICE BEGIN =====
// 当前脚本来自于 https://jb.3add.cn 脚本分享下载！
// 更多脚本获取 https://pan.quark.cn/s/9dd555d3210d
// 脚本库交流QQ群: 480383815
// 脚本呆瓜QQ群: 958310806
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。
// ===== SCRIPT HUB NOTICE END =====

// 使用说明：
// 1. 在运行前设置环境变量名称 ZSP，值：定义备注#secretId#secretKey#deviceId。
// 2. 数值入口：面板进入"商户密匙"模块获取 SecretId#SecretKey，并填写设备码。
// 3. 多账号请使用换行分隔。
// 4. 可选环境变量：ZSP_MAX_ADS 控制单账号最大执行次数，默认 50；ZSP_TIMEOUT 控制请求超时时间，默认 15000 毫秒。
// 5. PUSH PLUS 推送：设置环境变量 PUSH_PLUS_TOKEN，脚本运行完成后将自动推送结果。
// 6. 运行命令：node 中视频.js。
// 7. 注册链接：https://zsp.99panel.top/#/register?inviteCode=bfxfUlYD
// 8. 下载：https://apka.o3oh4.com/new_apk/download.html?id=zsp/1
// 9. 免责声明：本内容仅为互联网项目资讯分享，不构成任何投资建议。平台规则、奖励机制、活动内容可能随时调整，请以官方公告为准。参与者需自行判断风险，理性参与。请勿借贷、充值或投入超出自身承受能力的资金。本人仅作信息分享，不对平台后续运营及相关结果承担责任。
//
// 10. 新增功能：
//     - ZSP_WEB：Web端账号配置，格式：备注#手机号#密码，用于查询余额、今日奖励、自动提现
//     - ZSP_AUTO_WITHDRAW：自动提现开关，默认开启（1/true），设为0/false关闭
//     - 自动提现阈值：10元
//     - 相同备注的账号会自动合并任务数据
//     - 推送使用 HTML 卡片式表格
//     - Web端查询增加重试和详细错误日志

const http = require("http");
const https = require("https");

const ENV_NAME = "中视频";
const BASE_URL = "https://x1.zsptv.online";
const USER_AGENT = "Mozilla/5.0 (Linux; Android 15; 23013RK75C Build/AQ3A.250226.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.260 Mobile Safari/537.36 (Immersed/39.42857) Html5Plus/1.0";
const REQUEST_TIMEOUT = readPositiveInteger(process.env.ZSP_TIMEOUT, 15000);
const MAX_ADS = readPositiveInteger(process.env.ZSP_MAX_ADS, 50);
const ACCOUNT_ENV_NAMES = ["ZSP", "AD_WATCH_ACCOUNTS"];
const MAX_CONSECUTIVE_FAILURES = 3;
const PUSH_PLUS_TOKEN = process.env.PUSH_PLUS_TOKEN || "";

// 自动提现开关：默认开启
const AUTO_WITHDRAW_ENABLED = (() => {
  const val = process.env.ZSP_AUTO_WITHDRAW;
  if (val === undefined || val === "") return true;
  return val === "1" || val === "true" || val === "on" || val === "yes";
})();

// Web端配置
const WEB_BASE = "https://x1.zsptv.online";
const WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36";

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

// Web端请求头
function buildWebHeaders(webToken) {
  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    "User-Agent": WEB_UA,
    Authorization: `Bearer ${webToken}`,
    Origin: "https://zsp.99panel.top",
    Referer: "https://zsp.99panel.top/"
  };
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

// ---------- Web端账号加载 ----------
function loadWebAccounts() {
  const webAccounts = {};
  const envValue = (process.env.ZSP_WEB || "").trim();
  if (!envValue) return webAccounts;
  
  const rows = envValue.split(/[\n&]/).map(s => s.trim()).filter(Boolean);
  rows.forEach((row, idx) => {
    const parts = row.split("#").map(s => s.trim());
    if (parts.length < 3 || !parts[1] || !parts[2]) {
      log("WARNING", "ZSP_WEB 格式错误，已忽略", { index: idx + 1, hint: "格式：备注#手机号#密码" });
      return;
    }
    const remark = parts[0] || `web账号${idx + 1}`;
    webAccounts[remark] = { phone: parts[1], password: parts[2] };
    log("INFO", "Web账号配置已加载", { remark, phone: maskValue(parts[1]) });
  });
  return webAccounts;
}

const WEB_ACCOUNTS = loadWebAccounts();

// ---------- Web端接口（增加重试和详细日志） ----------
async function webPasswordLogin(remark, retry = 2) {
  const cred = WEB_ACCOUNTS[remark];
  if (!cred) {
    log("WARNING", "未找到Web账号配置", { remark, availableRemarks: Object.keys(WEB_ACCOUNTS).join(",") || "无" });
    return { token: null, error: `未找到Web账号配置（备注"${remark}"不在ZSP_WEB中，可用：${Object.keys(WEB_ACCOUNTS).join(",") || "无"}）` };
  }
  for (let attempt = 1; attempt <= retry; attempt++) {
    const result = await requestJson({
      url: `${WEB_BASE}/api/web/v1/auth/passwordLogin`,
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "User-Agent": WEB_UA,
        Origin: "https://zsp.99panel.top",
        Referer: "https://zsp.99panel.top/"
      },
      body: JSON.stringify({ mobile: cred.phone, password: cred.password })
    });
    if (result.ok && result.data?.code === 0 && result.data?.data?.token) {
      log("INFO", "Web端登录成功", { remark, attempt });
      return { token: result.data.data.token, error: null };
    }
    const errMsg = result.data?.message || result.message || "未知错误";
    const code = result.data?.code ?? '无';
    log("WARNING", `Web端登录失败 (尝试 ${attempt}/${retry})`, { remark, code, message: errMsg, statusCode: result.statusCode });
    if (attempt < retry) {
      await wait(randomInt(2000, 4000));
    }
    if (attempt === retry) {
      return { token: null, error: `登录接口返回失败（code=${code}，${errMsg}）` };
    }
  }
  return { token: null, error: "登录重试耗尽" };
}

async function getUserInfo(remark, webToken) {
  if (!webToken) {
    log("WARNING", "WebToken为空，无法查询", { remark });
    return null;
  }
  const webHeaders = buildWebHeaders(webToken);
  try {
    // 查询金币余额
    const walletResult = await requestJson({
      url: `${WEB_BASE}/api/web/v1/user/wallet/score/getInfo`,
      method: "GET",
      headers: webHeaders
    });
    if (!walletResult.ok || walletResult.data?.code !== 0) {
      log("WARNING", "查询金币余额失败", { remark, code: walletResult.data?.code, message: walletResult.message });
      return null;
    }
    const info = walletResult.data.data;
    // 查询账户余额
    const balanceResult = await requestJson({
      url: `${WEB_BASE}/api/web/v1/user/wallet/balance/getInfo`,
      method: "GET",
      headers: webHeaders
    });
    let moneyBalance = 0;
    if (balanceResult.ok && balanceResult.data?.code === 0 && balanceResult.data?.data) {
      moneyBalance = Number(balanceResult.data.data.balance) || 0;
    } else {
      log("WARNING", "查询账户余额失败", { remark, code: balanceResult.data?.code, message: balanceResult.message });
    }
    return {
      coins: Number(info.balance) || 0,
      balance: moneyBalance,
      _webHeaders: webHeaders
    };
  } catch (error) {
    log("ERROR", "查询用户信息异常", { remark, message: sanitizeErrorMessage(error.message) });
    return null;
  }
}

async function getTodayCoins(remark, webToken, userInfo) {
  const webHeaders = userInfo?._webHeaders;
  if (!webHeaders) {
    log("WARNING", "无Web会话，无法查询今日奖励", { remark });
    return null;
  }
  try {
    const result = await requestJson({
      url: `${WEB_BASE}/api/web/v1/dashboard/getPanelData`,
      method: "GET",
      headers: webHeaders
    });
    if (result.ok && result.data?.code === 0 && result.data?.data != null) {
      return result.data.data.incomeScore ?? null;
    } else {
      log("WARNING", "查询今日奖励失败", { remark, code: result.data?.code, message: result.message });
      return null;
    }
  } catch (error) {
    log("ERROR", "查询今日奖励异常", { remark, message: sanitizeErrorMessage(error.message) });
    return null;
  }
}

async function autoWithdraw(remark, userInfo) {
  if (!AUTO_WITHDRAW_ENABLED) {
    log("INFO", "自动提现已关闭（ZSP_AUTO_WITHDRAW=0），跳过", { remark });
    return { withdrawn: false, amount: 0, reason: "自动提现已关闭" };
  }
  const threshold = 10;
  const webHeaders = userInfo?._webHeaders;
  if (!webHeaders) {
    return { withdrawn: false, amount: 0, reason: "无Web会话" };
  }
  const balance = userInfo.balance;
  if (balance < threshold) {
    log("INFO", "余额不足，跳过提现", { remark, balance, threshold });
    return { withdrawn: false, amount: 0, reason: `余额 ¥${balance.toFixed(2)} 未达 ¥${threshold}` };
  }
  const amount = balance.toFixed(2);
  log("INFO", "余额已达提现阈值，发起提现", { remark, balance, threshold, amount });
  try {
    const result = await requestJson({
      url: `${WEB_BASE}/api/web/v1/user/wallet/balance/withdraw`,
      method: "POST",
      headers: webHeaders,
      body: JSON.stringify({ amount })
    });
    if (result.ok && result.data?.code === 0) {
      log("SUCCESS", "提现成功", { remark, amount });
      return { withdrawn: true, amount: Number(amount), reason: "成功" };
    } else {
      log("WARNING", "提现失败", { remark, amount, code: result.data?.code, message: result.message });
      return { withdrawn: false, amount: 0, reason: result.message || "接口返回失败" };
    }
  } catch (error) {
    log("ERROR", "提现异常", { remark, message: sanitizeErrorMessage(error.message) });
    return { withdrawn: false, amount: 0, reason: "异常: " + error.message };
  }
}

// ---------- App 端接口（不变） ----------
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
    return { success: false, reward: 0 };
  }

  if (result.data.code === 0) {
    const reward = Number(result.data.data?.qiandao_money) || 0;
    log("INFO", "签到成功", {
      requestId: result.requestId,
      remark: account.remark,
      message: result.message,
      reward,
      continuousDays: result.data.data?.continuousDays || 1
    });
    return { success: true, reward };
  }

  if (result.message.includes("已签到")) {
    log("INFO", "今日已签到", {
      requestId: result.requestId,
      remark: account.remark
    });
    return { success: true, reward: 0 };
  }

  log("ERROR", "签到失败", {
    requestId: result.requestId,
    remark: account.remark,
    message: result.message || "未知错误"
  });
  return { success: false, reward: 0 };
}

/**
 * 获取转盘信息（抽奖次数和奖励配置）
 */
async function getTurntableInfo(token, account) {
  const result = await requestJson({
    url: `${BASE_URL}/api/app/v1/device/getTurntableInfo`,
    method: "GET",
    headers: buildHeaders(account, token)
  });

  if (!result.ok) {
    log("ERROR", "获取转盘信息失败", {
      requestId: result.requestId,
      remark: account.remark,
      statusCode: result.statusCode,
      message: result.message
    });
    return null;
  }

  if (result.data.code === 0 && result.data.data) {
    const data = result.data.data;
    const turntableNum = Number.parseInt(data.turntable_num, 10) || 0;
    const turntableMoney = Number.parseInt(data.turntable_money, 10) || 0;
    const goods = data.goods ? data.goods.split(",").map(Number) : [];

    log("INFO", "获取转盘信息成功", {
      requestId: result.requestId,
      remark: account.remark,
      turntableNum,
      turntableMoney,
      goods: goods.join(",")
    });

    return {
      turntableNum,
      turntableMoney,
      goods,
      content: decodeUnicode(data.content || "")
    };
  }

  log("ERROR", "获取转盘信息失败", {
    requestId: result.requestId,
    remark: account.remark,
    message: result.message || "未知错误"
  });
  return null;
}

/**
 * 执行转盘抽奖
 */
async function spinTurntable(token, account, goods) {
  const result = await requestJson({
    url: `${BASE_URL}/api/app/v1/device/turntable`,
    method: "POST",
    headers: buildHeaders(account, token),
    body: JSON.stringify({
      goods: goods || "28,68,128,298,388,488,588,888"
    })
  });

  if (!result.ok) {
    log("ERROR", "抽奖请求失败", {
      requestId: result.requestId,
      remark: account.remark,
      statusCode: result.statusCode,
      message: result.message
    });
    return null;
  }

  if (result.data.code === 0) {
    const data = result.data.data || {};
    // 尝试多种方式获取奖励
    let reward = 0;
    if (data.turntable_money !== undefined && data.turntable_money !== null) {
      reward = Number.parseInt(String(data.turntable_money), 10) || 0;
    }
    if (reward === 0 && data.reward !== undefined && data.reward !== null) {
      reward = Number.parseInt(String(data.reward), 10) || 0;
    }
    if (reward === 0 && data.money !== undefined && data.money !== null) {
      reward = Number.parseInt(String(data.money), 10) || 0;
    }
    const remainingNum = Number.parseInt(data.turntable_num, 10) || 0;
    
    log("INFO", "抽奖完成", {
      requestId: result.requestId,
      remark: account.remark,
      reward,
      remainingNum,
      rawData: JSON.stringify(data)
    });
    
    return {
      reward,
      remainingNum,
      rawData: data
    };
  }

  log("ERROR", "抽奖失败", {
    requestId: result.requestId,
    remark: account.remark,
    message: result.message || "未知错误"
  });
  return null;
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

/**
 * 处理单个账号的转盘抽奖（使用差值计算奖励）
 */
async function processTurntable(token, account) {
  const turntableInfo = await getTurntableInfo(token, account);
  if (!turntableInfo) {
    log("WARNING", "获取转盘信息失败，跳过抽奖", { remark: account.remark });
    return { success: false, reward: 0, reason: "get_info_failed" };
  }

  const { turntableNum, turntableMoney, goods } = turntableInfo;

  if (turntableNum <= 0) {
    log("INFO", "今日无抽奖次数", {
      remark: account.remark,
      turntableNum,
      turntableMoney
    });
    return { success: true, reward: 0, reason: "no_turntable_num", turntableNum };
  }

  log("INFO", "开始转盘抽奖", {
    remark: account.remark,
    turntableNum,
    goodsCount: goods.length,
    currentMoney: turntableMoney
  });

  let totalReward = 0;
  let successCount = 0;
  let lastTurntableMoney = turntableMoney;

  for (let i = 0; i < turntableNum; i++) {
    log("INFO", `执行第 ${i + 1}/${turntableNum} 次抽奖`, {
      remark: account.remark
    });

    const spinResult = await spinTurntable(token, account, goods.join(","));
    if (spinResult) {
      let reward = spinResult.reward;
      
      // 如果接口返回的 reward 为 0，通过查询差值计算
      if (reward === 0) {
        const currentInfo = await getTurntableInfo(token, account);
        if (currentInfo) {
          const diff = currentInfo.turntableMoney - lastTurntableMoney;
          if (diff > 0) {
            reward = diff;
            log("INFO", "通过差值计算奖励", {
              remark: account.remark,
              diff,
              before: lastTurntableMoney,
              after: currentInfo.turntableMoney
            });
          }
          lastTurntableMoney = currentInfo.turntableMoney;
        }
      } else {
        // 如果接口返回了奖励，更新 lastTurntableMoney
        const currentInfo = await getTurntableInfo(token, account);
        if (currentInfo) {
          lastTurntableMoney = currentInfo.turntableMoney;
        }
      }
      
      totalReward += reward;
      successCount++;
      log("INFO", `第 ${i + 1} 次抽奖完成`, {
        remark: account.remark,
        reward,
        totalReward,
        remaining: spinResult.remainingNum
      });
    } else {
      log("WARNING", `第 ${i + 1} 次抽奖失败`, {
        remark: account.remark
      });
    }

    if (i < turntableNum - 1) {
      await wait(randomInt(1000, 3000));
    }
  }

  // 最终查询
  const finalInfo = await getTurntableInfo(token, account);
  const finalMoney = finalInfo ? finalInfo.turntableMoney : 0;
  
  if (totalReward === 0) {
    totalReward = finalMoney - turntableMoney;
  }

  log("INFO", "转盘抽奖完成", {
    remark: account.remark,
    successCount,
    totalReward,
    totalAttempts: turntableNum,
    startMoney: turntableMoney,
    finalMoney,
    actualIncrease: finalMoney - turntableMoney
  });

  return {
    success: true,
    reward: totalReward > 0 ? totalReward : 0,
    successCount,
    totalAttempts: turntableNum,
    turntableNum,
    startMoney: turntableMoney,
    endMoney: finalMoney
  };
}

/**
 * 处理单个账号
 */
async function processAccount(account) {
  let token = await login(account);
  if (!token) {
    log("ERROR", "登录失败，跳过账号", { remark: account.remark });
    return { 
      success: false, 
      reason: "login_failed", 
      successCount: 0, 
      totalReward: 0, 
      turntableReward: 0,
      remark: account.remark,
      signReward: 0,
      signSuccess: false,
      adCount: 0,
      videoReward: 0,
      webError: "App登录失败"
    };
  }

  // 签到
  const signResult = await checkAndSign(token, account);
  const signSuccess = signResult.success;
  const signReward = signResult.reward;
  if (!signSuccess) {
    log("ERROR", "签到未完成，跳过账号", { remark: account.remark });
    return { 
      success: false, 
      reason: "sign_failed", 
      successCount: 0, 
      totalReward: 0, 
      turntableReward: 0,
      remark: account.remark,
      signReward,
      signSuccess: false,
      adCount: 0,
      videoReward: 0,
      webError: "签到失败"
    };
  }

  // 转盘抽奖
  let turntableReward = 0;
  try {
    const turntableResult = await processTurntable(token, account);
    if (turntableResult.success) {
      turntableReward = turntableResult.reward || 0;
      log("INFO", "转盘抽奖完成", {
        remark: account.remark,
        turntableReward,
        successCount: turntableResult.successCount || 0,
        totalAttempts: turntableResult.totalAttempts || 0
      });
    }
  } catch (error) {
    log("ERROR", "转盘抽奖异常", {
      remark: account.remark,
      message: sanitizeErrorMessage(error.message)
    });
  }

  // 视频任务
  let successCount = 0;
  let failCount = 0;
  let totalReward = 0;
  let consecutiveFailures = 0;
  let shouldStop = false;

  for (let adCount = 0; adCount < MAX_ADS && !shouldStop; adCount++) {
    log("INFO", "开始处理任务", {
      remark: account.remark,
      current: adCount + 1,
      total: MAX_ADS,
      consecutiveFailures
    });

    if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
      log("WARNING", "连续失败次数已达上限，停止该账号", {
        remark: account.remark,
        maxFailures: MAX_CONSECUTIVE_FAILURES,
        totalSuccess: successCount,
        totalReward
      });
      shouldStop = true;
      break;
    }

    if (consecutiveFailures > 0 && consecutiveFailures % 2 === 0) {
      log("INFO", "尝试刷新登录状态", { remark: account.remark });
      const newToken = await login(account);
      if (newToken) {
        token = newToken;
        log("INFO", "登录状态刷新成功", { remark: account.remark });
      } else {
        log("WARNING", "登录状态刷新失败", { remark: account.remark });
        consecutiveFailures++;
        await wait(randomInt(2500, 5000));
        continue;
      }
    }

    const adInfo = await getNextAd(token, account);
    if (!adInfo) {
      consecutiveFailures++;
      failCount++;
      log("WARNING", "获取广告失败", {
        remark: account.remark,
        consecutiveFailures
      });
      await wait(randomInt(2500, 5000));
      continue;
    }

    const playResult = await claimReward(token, account, adInfo);
    if (playResult.success) {
      successCount++;
      totalReward += Number.parseInt(playResult.reward, 10) || 0;
      consecutiveFailures = 0;
      log("INFO", "任务完成", {
        remark: account.remark,
        reward: playResult.reward || 0,
        playRecordId: playResult.playRecordId,
        totalRewardSoFar: totalReward
      });
    } else {
      consecutiveFailures++;
      failCount++;
      log("WARNING", "任务失败", {
        remark: account.remark,
        consecutiveFailures,
        maxBeforeStop: MAX_CONSECUTIVE_FAILURES
      });
    }

    if (adCount < MAX_ADS - 1 && !shouldStop) {
      const delay = randomInt(3000, 6000);
      log("INFO", "等待后继续", {
        remark: account.remark,
        delaySeconds: Math.round(delay / 1000),
        remaining: MAX_ADS - (adCount + 1)
      });
      await wait(delay);
    }
  }

  // ====== Web端查询余额 + 自动提现（增加错误捕获和详细日志） ======
  let webToken = null;
  let userInfo = null;
  let todayCoins = null;
  let withdrawResult = null;
  let webError = null;

  try {
    const loginResult = await webPasswordLogin(account.remark);
    webToken = loginResult.token;
    if (webToken) {
      userInfo = await getUserInfo(account.remark, webToken);
      if (userInfo) {
        todayCoins = await getTodayCoins(account.remark, webToken, userInfo);
        log("INFO", "账户信息", {
          remark: account.remark,
          todayCoins: todayCoins ?? totalReward + turntableReward,
          coinsBalance: userInfo.coins,
          moneyBalance: userInfo.balance.toFixed(2)
        });

        if (AUTO_WITHDRAW_ENABLED) {
          withdrawResult = await autoWithdraw(account.remark, userInfo);
          if (withdrawResult.withdrawn) {
            log("SUCCESS", "自动提现成功", { 
              remark: account.remark, 
              amount: withdrawResult.amount.toFixed(2) 
            });
          }
        } else {
          withdrawResult = { withdrawn: false, amount: 0, reason: "自动提现已关闭" };
          log("INFO", "自动提现已关闭（ZSP_AUTO_WITHDRAW=0），跳过", { remark: account.remark });
        }
      } else {
        webError = "查询用户信息失败";
        withdrawResult = { withdrawn: false, amount: 0, reason: `无法评估（${webError}）` };
      }
    } else {
      webError = loginResult.error || "Web登录失败（未知原因）";
      withdrawResult = { withdrawn: false, amount: 0, reason: `无法评估（${webError}）` };
    }
  } catch (error) {
    webError = sanitizeErrorMessage(error.message);
    withdrawResult = { withdrawn: false, amount: 0, reason: `无法评估（${webError}）` };
    log("WARNING", "余额查询/提现异常", { 
      remark: account.remark, 
      message: webError 
    });
  }

  const finalMessage = shouldStop
    ? `连续失败${MAX_CONSECUTIVE_FAILURES}次后停止`
    : "完成所有任务";

  log("INFO", `账号处理完成 (${finalMessage})`, {
    remark: account.remark,
    successCount,
    failCount,
    totalReward,
    turntableReward,
    totalRewardAll: totalReward + turntableReward,
    totalAttempts: successCount + failCount,
    successRate: successCount + failCount > 0 ? `${((successCount / (successCount + failCount)) * 100).toFixed(1)}%` : "0%"
  });

  return {
    success: true,
    remark: account.remark,
    successCount,
    failCount,
    totalReward: totalReward + turntableReward,
    videoReward: totalReward,
    turntableReward,
    stoppedEarly: shouldStop,
    signReward,
    signSuccess: true,
    adCount: successCount,
    userInfo,
    todayCoins,
    withdrawResult,
    webError // 新增错误信息
  };
}

/**
 * 发送 PUSH PLUS 推送（按备注合并相同备注的账号，使用 Markdown 表格语法）
 */
async function sendPushPlusPush(accountDetails, summary, webOrder) {
  if (!PUSH_PLUS_TOKEN) {
    log("INFO", "未配置 PUSH_PLUS_TOKEN，跳过推送");
    return false;
  }

  if (!accountDetails || accountDetails.length === 0) {
    log("INFO", "无账号数据，跳过推送");
    return false;
  }

  // ---------- 按备注合并 ----------
  const groupMap = {};
  for (const detail of accountDetails) {
    const key = detail.remark;
    if (!groupMap[key]) {
      groupMap[key] = {
        remark: key,
        success: detail.success,
        successCount: 0,
        totalReward: 0,
        turntableReward: 0,
        videoReward: 0,
        signReward: 0,
        signSuccess: true,
        adCount: 0,
        stoppedEarly: false,
        userInfo: null,
        todayCoins: null,
        withdrawResult: null,
        webError: null,
        hasFailed: false
      };
    }
    const group = groupMap[key];
    if (!detail.success) {
      group.hasFailed = true;
      group.success = false;
      continue;
    }
    group.successCount += detail.successCount || 0;
    group.totalReward += detail.totalReward || 0;
    group.turntableReward += detail.turntableReward || 0;
    group.videoReward += detail.videoReward || 0;
    group.signReward += detail.signReward || 0;
    group.adCount += detail.adCount || 0;
    if (detail.stoppedEarly) group.stoppedEarly = true;
    if (!group.userInfo && detail.userInfo) group.userInfo = detail.userInfo;
    if (group.todayCoins === null && detail.todayCoins !== null && detail.todayCoins !== undefined) {
      group.todayCoins = detail.todayCoins;
    }
    if (detail.withdrawResult) {
      if (!group.withdrawResult || detail.withdrawResult.withdrawn) {
        group.withdrawResult = detail.withdrawResult;
      }
    }
    if (!detail.signSuccess) group.signSuccess = false;
    // 记录错误信息（只保留第一个非空）
    if (detail.webError && !group.webError) group.webError = detail.webError;
  }

  // 按 webOrder 排序
  const groups = Object.values(groupMap);
  const orderMap = {};
  webOrder.forEach((name, index) => { orderMap[name] = index; });
  groups.sort((a, b) => {
    const indexA = a.remark in orderMap ? orderMap[a.remark] : 999;
    const indexB = b.remark in orderMap ? orderMap[b.remark] : 999;
    return indexA - indexB;
  });

  // 构建内容（使用 HTML 卡片式表格）
  let content = `<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:400px;margin:0 auto;">`;
  content += `<div style="background:#f5f5f5;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">`;
  content += `<div style="text-align:center;font-size:16px;font-weight:600;color:#333;margin-bottom:12px;">📊 中视频运行报告</div>`;
  content += `<div style="text-align:center;font-size:12px;color:#888;margin-bottom:4px;">⏱ 耗时：${summary.elapsed}秒 | 账号：${summary.totalAccounts}个</div>`;
  content += `<div style="text-align:center;font-size:12px;color:#888;margin-bottom:4px;">✅ 成功${summary.successAccounts} | ❌ 失败${summary.failedAccounts} | ⚠ 提前停止${summary.stoppedEarly}</div>`;
  content += `<div style="text-align:center;font-size:13px;color:#e67e22;font-weight:600;margin-bottom:16px;">🎁 总奖励：${summary.totalReward}金币（视频${summary.totalVideoReward} + 转盘${summary.totalTurntableReward}）</div>`;

  for (const group of groups) {
    if (!group.success || group.hasFailed) {
      content += `<div style="background:#fff;border-radius:8px;padding:12px;margin-bottom:10px;">`;
      content += `<div style="font-size:14px;font-weight:600;color:#e74c3c;">❌ ${group.remark}：执行失败</div>`;
      content += `</div>`;
      continue;
    }
    content += `<div style="background:#fff;border-radius:8px;padding:12px;margin-bottom:10px;">`;
    content += `<div style="font-size:14px;font-weight:600;color:#333;margin-bottom:8px;">🔖 ${group.remark}</div>`;
    content += `<table style="width:100%;border-collapse:collapse;font-size:13px;">`;
    content += `<thead><tr style="background:#f0f0f0;">`;
    content += `<th style="padding:8px 6px;text-align:left;font-weight:600;color:#555;border-bottom:1px solid #e0e0e0;">任务</th>`;
    content += `<th style="padding:8px 6px;text-align:right;font-weight:600;color:#555;border-bottom:1px solid #e0e0e0;">结果</th>`;
    content += `</tr></thead><tbody>`;

    if (group.signSuccess) {
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">签到</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#27ae60;border-bottom:1px solid #f0f0f0;">+${group.signReward} 金币</td></tr>`;
    } else {
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">签到</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#e74c3c;border-bottom:1px solid #f0f0f0;">❌ 失败</td></tr>`;
    }

    if (group.turntableReward > 0) {
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">抽奖</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#27ae60;border-bottom:1px solid #f0f0f0;">+${group.turntableReward} 金币</td></tr>`;
    } else {
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">抽奖</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#999;border-bottom:1px solid #f0f0f0;">无次数或未获得</td></tr>`;
    }

    content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">看广告</td>`;
    content += `<td style="padding:7px 6px;text-align:right;color:#27ae60;border-bottom:1px solid #f0f0f0;">${group.adCount}/${group.adCount} 次，+${group.videoReward} 金币</td></tr>`;

    if (group.userInfo) {
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">金币余额</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#333;border-bottom:1px solid #f0f0f0;">${group.userInfo.coins}</td></tr>`;
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">账户余额</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#333;border-bottom:1px solid #f0f0f0;">¥${group.userInfo.balance.toFixed(2)}</td></tr>`;
    } else {
      const errorMsg = group.webError ? `（${group.webError}）` : '';
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">金币余额</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#999;border-bottom:1px solid #f0f0f0;">未查询${errorMsg}</td></tr>`;
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">账户余额</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#999;border-bottom:1px solid #f0f0f0;">未查询${errorMsg}</td></tr>`;
    }

    if (group.todayCoins !== null && group.todayCoins !== undefined) {
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">今日奖励</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#27ae60;border-bottom:1px solid #f0f0f0;">+${group.todayCoins} 金币</td></tr>`;
    } else {
      const errorMsg = group.webError ? `（${group.webError}）` : '';
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">今日奖励</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#999;border-bottom:1px solid #f0f0f0;">未查询${errorMsg}</td></tr>`;
    }

    if (group.withdrawResult) {
      if (group.withdrawResult.withdrawn) {
        content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">自动提现</td>`;
        content += `<td style="padding:7px 6px;text-align:right;color:#27ae60;border-bottom:1px solid #f0f0f0;">✅ ¥${group.withdrawResult.amount.toFixed(2)}</td></tr>`;
      } else {
        content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">自动提现</td>`;
        content += `<td style="padding:7px 6px;text-align:right;color:#999;border-bottom:1px solid #f0f0f0;">${group.withdrawResult.reason}</td></tr>`;
      }
    } else {
      content += `<tr><td style="padding:7px 6px;color:#333;border-bottom:1px solid #f0f0f0;">自动提现</td>`;
      content += `<td style="padding:7px 6px;text-align:right;color:#999;border-bottom:1px solid #f0f0f0;">未触发</td></tr>`;
    }

    content += `</tbody></table></div>`;
  }

  content += `</div></div>`;

  const requestBody = {
    token: PUSH_PLUS_TOKEN,
    title: `📱 中视频运行报告`,
    content: content.trim(),
    template: "html"
  };

  try {
    log("INFO", "开始发送 PUSH PLUS 推送");
    
    const response = await new Promise((resolve, reject) => {
      const url = new URL("http://www.pushplus.plus/send");
      const req = http.request({
        hostname: url.hostname,
        port: 80,
        path: url.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        timeout: 10000
      }, res => {
        let data = "";
        res.on("data", chunk => { data += chunk; });
        res.on("end", () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve({ code: -1, msg: "解析响应失败" });
          }
        });
      });
      
      req.on("error", reject);
      req.on("timeout", () => {
        req.destroy();
        reject(new Error("推送请求超时"));
      });
      
      req.write(JSON.stringify(requestBody));
      req.end();
    });
    
    if (response.code === 200) {
      log("INFO", "PUSH PLUS 推送成功");
      return true;
    } else {
      log("WARNING", "PUSH PLUS 推送失败", { code: response.code, message: response.msg });
      return false;
    }
  } catch (error) {
    log("ERROR", "PUSH PLUS 推送异常", { message: sanitizeErrorMessage(error.message) });
    return false;
  }
}

/**
 * 主函数
 */
async function main() {
  log("INFO", "脚本开始运行（并发模式）", {
    envName: ENV_NAME,
    maxAds: MAX_ADS,
    timeout: REQUEST_TIMEOUT,
    maxConsecutiveFailures: MAX_CONSECUTIVE_FAILURES,
    pushPlusEnabled: !!PUSH_PLUS_TOKEN,
    autoWithdrawEnabled: AUTO_WITHDRAW_ENABLED
  });

  if (AUTO_WITHDRAW_ENABLED) {
    log("INFO", "自动提现已开启（余额≥10元自动发起）");
  } else {
    log("INFO", "自动提现已关闭（可通过 ZSP_AUTO_WITHDRAW=1 开启）");
  }

  const accounts = loadAccounts();
  if (accounts.length === 0) {
    log("ERROR", "未找到有效账号配置");
    return;
  }

  log("INFO", `准备并发处理 ${accounts.length} 个账号`);

  const startTime = Date.now();
  const results = await Promise.allSettled(
    accounts.map(async (account, index) => {
      log("INFO", "开始处理账号", {
        index: index + 1,
        total: accounts.length,
        remark: account.remark
      });

      try {
        const result = await processAccount(account);
        return { accountRemark: account.remark, result };
      } catch (error) {
        log("ERROR", "账号处理异常", {
          remark: account.remark,
          message: sanitizeErrorMessage(error.message)
        });
        return {
          accountRemark: account.remark,
          error: error.message,
          result: { 
            success: false, 
            reason: "exception", 
            successCount: 0, 
            totalReward: 0, 
            turntableReward: 0,
            remark: account.remark,
            signReward: 0,
            signSuccess: false,
            adCount: 0,
            videoReward: 0,
            userInfo: null,
            todayCoins: null,
            withdrawResult: null,
            webError: error.message
          }
        };
      }
    })
  );

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  let totalSuccessCount = 0;
  let totalRewardSum = 0;
  let totalTurntableRewardSum = 0;
  let totalVideoRewardSum = 0;
  let accountsCompleted = 0;
  let accountsFailed = 0;
  let accountsStoppedEarly = 0;
  const accountDetails = [];

  log("INFO", "========== 运行结果汇总 ==========");

  for (const settled of results) {
    if (settled.status === "fulfilled") {
      const { accountRemark, result, error } = settled.value;
      if (error || !result?.success) {
        accountsFailed++;
        accountDetails.push({
          remark: accountRemark,
          success: false,
          successCount: 0,
          totalReward: 0,
          turntableReward: 0,
          stoppedEarly: false,
          error: error || "未知错误",
          userInfo: null,
          todayCoins: null,
          withdrawResult: null,
          signReward: 0,
          signSuccess: false,
          adCount: 0,
          videoReward: 0,
          webError: result?.webError || error
        });
        log("WARNING", `账号 [${accountRemark}] 处理失败`, { error: error || "未知错误" });
      } else {
        accountsCompleted++;
        totalSuccessCount += result.successCount || 0;
        totalRewardSum += result.totalReward || 0;
        totalTurntableRewardSum += result.turntableReward || 0;
        totalVideoRewardSum += result.videoReward || 0;
        if (result.stoppedEarly) {
          accountsStoppedEarly++;
        }
        accountDetails.push({
          remark: accountRemark,
          success: true,
          successCount: result.successCount,
          totalReward: result.totalReward,
          turntableReward: result.turntableReward || 0,
          stoppedEarly: result.stoppedEarly || false,
          userInfo: result.userInfo || null,
          todayCoins: result.todayCoins || null,
          withdrawResult: result.withdrawResult || null,
          signReward: result.signReward || 0,
          signSuccess: result.signSuccess || false,
          adCount: result.adCount || 0,
          videoReward: result.videoReward || 0,
          webError: result.webError || null
        });
        log("INFO", `账号 [${accountRemark}] 处理成功`, {
          successCount: result.successCount,
          videoReward: result.videoReward || 0,
          turntableReward: result.turntableReward || 0,
          totalReward: result.totalReward,
          stoppedEarly: result.stoppedEarly
        });
      }
    } else {
      accountsFailed++;
      log("ERROR", "账号处理 Promise 被拒绝", {
        reason: sanitizeErrorMessage(settled.reason)
      });
      accountDetails.push({
        remark: "未知",
        success: false,
        successCount: 0,
        totalReward: 0,
        turntableReward: 0,
        stoppedEarly: false,
        error: settled.reason,
        userInfo: null,
        todayCoins: null,
        withdrawResult: null,
        signReward: 0,
        signSuccess: false,
        adCount: 0,
        videoReward: 0,
        webError: settled.reason
      });
    }
  }

  log("INFO", "========== 最终统计 ==========");
  log("INFO", "执行概况", {
    总账号数: accounts.length,
    成功完成账号数: accountsCompleted,
    失败账号数: accountsFailed,
    提前停止账号数: accountsStoppedEarly,
    总成功任务数: totalSuccessCount,
    总视频奖励: totalVideoRewardSum,
    总转盘奖励: totalTurntableRewardSum,
    总获得金币: totalRewardSum,
    总耗时_秒: elapsed
  });

  // 获取 ZSP_WEB 顺序
  const webOrder = Object.keys(WEB_ACCOUNTS);

  // 发送 PUSH PLUS 推送
  await sendPushPlusPush(accountDetails, {
    elapsed,
    totalAccounts: accounts.length,
    successAccounts: accountsCompleted,
    failedAccounts: accountsFailed,
    stoppedEarly: accountsStoppedEarly,
    totalSuccess: totalSuccessCount,
    totalReward: totalRewardSum,
    totalVideoReward: totalVideoRewardSum,
    totalTurntableReward: totalTurntableRewardSum
  }, webOrder);

  // 青龙通知
  try {
    const notifyLines = [
      `📊 执行时间：${elapsed} 秒`,
      `👥 账号总数：${accounts.length} 个（成功 ${accountsCompleted}，失败 ${accountsFailed}${accountsStoppedEarly > 0 ? `，提前停止 ${accountsStoppedEarly}` : ""}）`,
      `✅ 总成功任务：${totalSuccessCount} 次`,
      `🎁 本次总获得奖励：${totalRewardSum} 金币（视频${totalVideoRewardSum} + 转盘${totalTurntableRewardSum}）`,
      ``
    ];
    for (const detail of accountDetails) {
      if (!detail.success) continue;
      notifyLines.push(`🔖 账号：${detail.remark}`);
      notifyLines.push(`   🎯 本次金币奖励：${detail.totalReward}`);
      if (detail.turntableReward > 0) notifyLines.push(`   🎰 转盘奖励：${detail.turntableReward}`);
      if (detail.todayCoins != null) notifyLines.push(`   📺 今日金币奖励：${detail.todayCoins}`);
      if (detail.userInfo) {
        notifyLines.push(`   💰 金币余额：${detail.userInfo.coins}`);
        notifyLines.push(`   💳 账户余额：¥${detail.userInfo.balance.toFixed(2)}`);
      } else if (detail.webError) {
        notifyLines.push(`   ❌ Web查询失败：${detail.webError}`);
      }
      if (detail.withdrawResult?.withdrawn) {
        notifyLines.push(`   💸 自动提现：¥${detail.withdrawResult.amount.toFixed(2)} ✅`);
      } else if (detail.withdrawResult && !detail.withdrawResult.withdrawn) {
        if (!["自动提现已关闭", "无Web会话"].includes(detail.withdrawResult.reason)) {
          notifyLines.push(`   💸 提现未触发：${detail.withdrawResult.reason}`);
        }
      }
      if (detail.stoppedEarly) notifyLines.push(`   ⚠️ 因连续失败提前终止`);
    }
    const notifyTitle = `中视频脚本运行完成`;
    const notifyContent = notifyLines.join("\n");
    
    if (typeof $notify === "function") $notify(notifyTitle, "", notifyContent);
    else if (typeof notify === "function") notify(notifyTitle, "", notifyContent);
    else {
      try { const { sendNotify } = require("./sendNotify"); await sendNotify(notifyTitle, notifyContent); }
      catch { try { const { sendNotify } = require("/ql/scripts/sendNotify"); await sendNotify(notifyTitle, notifyContent); }
      catch { log("INFO", "未检测到青龙通知模块，通知内容：\n" + notifyContent); } }
    }
  } catch (e) {
    log("WARNING", "发送青龙通知异常", { message: e.message });
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

// ===== SCRIPT HUB NOTICE BEGIN =====
// 当前脚本来自于 https://jb.3add.cn 脚本分享下载！
// 更多脚本获取 https://pan.quark.cn/s/9dd555d3210d
// 脚本库交流QQ群: 480383815
// 脚本呆瓜QQ群: 958310806
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。
// ===== SCRIPT HUB NOTICE END =====
