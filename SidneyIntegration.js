/**************************************************
 * Sidney Platform / 老祖兌換碼事件整合
 * Secrets 一律保存於 Script Properties。
 **************************************************/

const SIDNEY_ENDPOINT_PROPERTY = "SIDNEY_REDEEM_ENDPOINT";
const SIDNEY_SECRET_PROPERTY = "SIDNEY_REDEEM_SECRET";

function setSidneyIntegration() {
  const ui = SpreadsheetApp.getUi();
  const endpointResult = ui.prompt("設定老祖整合", "請輸入 Sidney Worker 兌換碼端點：", ui.ButtonSet.OK_CANCEL);
  if (endpointResult.getSelectedButton() !== ui.Button.OK) return;
  const secretResult = ui.prompt("設定老祖整合", "請輸入共享密鑰（至少 32 個字元）：", ui.ButtonSet.OK_CANCEL);
  if (secretResult.getSelectedButton() !== ui.Button.OK) return;

  const endpoint = String(endpointResult.getResponseText() || "").trim();
  const secret = String(secretResult.getResponseText() || "").trim();
  if (!/^https:\/\/.+\/integrations\/redeem-codes$/.test(endpoint)) throw new Error("Sidney Worker 端點格式不正確");
  if (secret.length < 32) throw new Error("共享密鑰至少需要 32 個字元");

  PropertiesService.getScriptProperties().setProperties({
    [SIDNEY_ENDPOINT_PROPERTY]: endpoint,
    [SIDNEY_SECRET_PROPERTY]: secret
  });
  SpreadsheetApp.getActive().toast("老祖整合設定完成", CONFIG.APP.TOAST_TITLE, 5);
}

function sendNewCodesToSidney_(newCodes, activeCount, expiredCount) {
  const properties = PropertiesService.getScriptProperties();
  const endpoint = String(properties.getProperty(SIDNEY_ENDPOINT_PROPERTY) || "");
  const secret = String(properties.getProperty(SIDNEY_SECRET_PROPERTY) || "");
  if (!endpoint || !secret) throw new Error("尚未執行 setSidneyIntegration 設定端點與共享密鑰");

  const items = (Array.isArray(newCodes) ? newCodes : []).filter(Boolean);
  const codes = [...new Set(items.map(function (item) {
    return String(item && typeof item === "object" ? item.code || "" : item).trim().toUpperCase();
  }).filter(Boolean))];
  if (codes.length === 0) return;

  const batchId = String((items[0] && items[0].batchId) || Utilities.getUuid()).replace(/[^A-Za-z0-9_-]/g, "-");
  const timestamp = String(Math.floor(Date.now() / 1000));
  const body = JSON.stringify({
    source: "wwm-redeem-code-tracker",
    codes: codes,
    activeCount: Number(activeCount) || 0,
    expiredCount: Number(expiredCount) || 0
  });
  const signedValue = timestamp + "." + batchId + "." + body;
  const signature = Utilities.computeHmacSha256Signature(signedValue, secret)
    .map(function (value) { return (value < 0 ? value + 256 : value).toString(16).padStart(2, "0"); })
    .join("");

  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    payload: body,
    headers: {
      "X-Sidney-Timestamp": timestamp,
      "X-Sidney-Event-Id": batchId,
      "X-Sidney-Signature": signature
    },
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) throw new Error("Sidney Worker 回應 HTTP " + status);
}

function testSidneyIntegration() {
  const result = sendSignedSidneyRequest_({
    type: "connection_test",
    source: "wwm-redeem-code-tracker"
  }, "connection-test-" + Utilities.getUuid());

  if (!result || result.ok !== true || result.connectionTest !== true) {
    throw new Error("Sidney Worker 未回傳有效的老祖連線測試結果");
  }

  SpreadsheetApp.getUi().alert(
    "☯ 老祖連線測試成功",
    "Worker、共享密鑰、老祖 Bot 與兌換碼公告頻道均已驗證成功。請到 Discord 查看老祖的測試訊息。",
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

function sendSignedSidneyRequest_(payload, eventId) {
  const properties = PropertiesService.getScriptProperties();
  const endpoint = String(properties.getProperty(SIDNEY_ENDPOINT_PROPERTY) || "");
  const secret = String(properties.getProperty(SIDNEY_SECRET_PROPERTY) || "");
  if (!endpoint || !secret) throw new Error("尚未設定老祖公告端點與共享密鑰");

  const timestamp = String(Math.floor(Date.now() / 1000));
  const cleanEventId = String(eventId || Utilities.getUuid()).replace(/[^A-Za-z0-9_-]/g, "-");
  const body = JSON.stringify(payload || {});
  const signature = Utilities.computeHmacSha256Signature(timestamp + "." + cleanEventId + "." + body, secret)
    .map(function (value) { return (value < 0 ? value + 256 : value).toString(16).padStart(2, "0"); })
    .join("");
  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    payload: body,
    headers: {
      "X-Sidney-Timestamp": timestamp,
      "X-Sidney-Event-Id": cleanEventId,
      "X-Sidney-Signature": signature
    },
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error("Sidney Worker 連線測試失敗｜HTTP " + status + "｜" + response.getContentText());
  }
  return JSON.parse(response.getContentText() || "{}");
}
