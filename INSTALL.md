# stat-hub 安裝步驟（給同事）

stat-hub 是本專案的「統計資料機器人」MCP server：在 Claude 裡問「某項統計資料去哪拿、口徑是什麼」，
並可即時向政府平台取數、把農業部／漁業署／普查／縣市年報下載解析存進本機資料庫。

## 1. 取得程式

repo 為私人，需先由維護者在 GitHub 加你為協作者（Settings → Collaborators）。

```bash
git clone https://github.com/ykupicai/stat-hub.git 統計資料庫
```

需要 Python 3.10 以上（開發環境為 3.14）。**不要用 QGIS 內建的 Python 安裝套件**（會弄壞 QGIS）。

## 2. 安裝套件

```bash
python -m pip install -r requirements.txt
```

## 3. 註冊 MCP server

**方法 A：只在本專案資料夾裡用**——不用做任何事。repo 根目錄的 `.mcp.json` 已註冊 `stat-hub`，
用 Claude Code 開啟這個資料夾時會詢問是否啟用，按允許即可。

**方法 B：在任何專案都能用（建議）**——在使用者層設定加入 stat-hub（路徑改成你 clone 的位置）：

```bash
claude mcp add -s user stat-hub -- python "C:\你的路徑\統計資料庫\stat_mcp\server.py"
```

沒有 `claude` 指令時，手動編輯 `%USERPROFILE%\.claude.json`，在最上層 `mcpServers` 加：

```json
"stat-hub": {
  "type": "stdio",
  "command": "python 的完整路徑（例：C:\\Users\\你\\AppData\\Local\\Programs\\Python\\Python314\\python.exe）",
  "args": ["C:\\你的路徑\\統計資料庫\\stat_mcp\\server.py"],
  "env": {}
}
```

改完**重開 Claude session** 才會載入。驗證：問 Claude「用 stat-hub 查屏東縣耕地面積去哪拿」，應會呼叫 `stat_search`。

## 4. 自我檢查（選用）

```bash
python stat_mcp/index.py
```

會印出各來源的目錄項目數（約 2 萬筆），代表索引正常。

## 5. 關於資料庫

- **clone 下來就能用**：來源登記、主題速查、各平台目錄、普查與年報結構（都在 repo 裡）；
  即時查詢類工具（主計處平台、農糧署、氣候、普查動態查詢、公務統計報表清冊）直接連網，不需資料庫。
- **用到才下載**：`stat_fetch`、`stat_census_tables`、`stat_pingtung_yearbook` 第一次查某張表時自動下載、
  解析、存進 `資料庫/stat.sqlite`（不進版控，每人各自累積），之後就直接查本機。
- **想一開始就有現成資料**：公司 NAS 上有維護者定期發布的共用快照（路徑請向維護者索取），
  把其中的 `stat.sqlite` **複製**到自己的 `資料庫/stat.sqlite`，重開 session 即可；同資料夾的 README.txt 寫有快照日期與內容。
  請複製到本機使用，**不要讓 stat-hub 直接讀寫 NAS 上的檔**（多人同時寫入會鎖檔或損壞）。

## 6. 執行改書件腳本（只有維護者需要）

`scripts/patch_docx_*` 等腳本要讀案件書件，路徑不進版控：
複製 `local_paths.example.json` 為 `local_paths.json`，填入本機的案件資料夾路徑。

## 常見問題

- **工具呼叫卡住不回應**：確認 `pandas` 有安裝（server 啟動時需預先載入）。
- **屏東站查詢偶爾斷線**：網站會擋連續請求，程式已內建自動重試，稍候即可。
- **政府網站憑證錯誤**：程式已一律關閉憑證驗證（政府站常缺 Subject Key Identifier），不用處理。
