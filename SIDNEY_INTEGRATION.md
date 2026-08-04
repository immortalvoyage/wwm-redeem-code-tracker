# 老祖兌換碼公告整合

自動更新仍由 Google Apps Script 偵測與永久去重；發現新碼後，系統會把簽章事件送到 Sidney Worker，由 Discord Bot 以老祖身分公告。

## 設定

1. 先在 Sidney Worker 設定 Secret：`wrangler secret put REDEEM_TRACKER_SECRET`。
2. 在 `wrangler.jsonc` 設定 `REDEEM_CODE_CHANNEL_ID`，並部署 Worker。
3. 重新整理 Google 試算表，選擇「📡 Discord → ☯ 設定老祖自動公告」。
4. 端點填入 `https://你的-worker網域/integrations/redeem-codes`。
5. 共享密鑰必須與 Worker Secret 完全相同，且至少 32 字元。

共享密鑰只保存在 Apps Script 的 Script Properties，不可提交至 GitHub。
