# AWS 價格自然語言查詢應用

這是一個使用自然語言查詢 AWS 服務價格的應用程式。用戶可以使用自然語言提問，例如"東京 linux t2.micro 價格為多少"，應用會返回準確的價格信息。

## 功能特點

- 自然語言查詢 AWS 服務價格
- 支持多種 AWS 服務（目前主要支持 EC2）
- 多區域和實例類型的價格查詢
- 用戶友好的介面
- 詳細的查詢結果顯示

## 技術架構

- 前端：React, TypeScript, Material-UI
- 後端：Python, Flask
- 外部 API：OpenAI API, AWS Price List API

## 安裝說明

### 先決條件

- Node.js 14+
- Python 3.8+
- AWS 帳戶（用於獲取 API 認證）
- OpenAI API 密鑰

### 後端設置

1. 進入後端目錄：

   ```
   cd backend
   ```

2. 安裝 Python 依賴：

   ```
   pip install -r ../requirements.txt
   ```

3. 複製環境變量示例文件並填寫您的 API 密鑰：

   ```
   cp ../.env.example .env
   ```

   然後編輯`.env`文件，添加您的 API 密鑰。

4. 啟動後端服務器：
   ```
   python app.py
   ```
   服務器將在 http://localhost:5000 運行。

### 前端設置

1. 進入前端目錄：

   ```
   cd frontend
   ```

2. 安裝依賴：

   ```
   npm install
   ```

3. 啟動開發服務器：
   ```
   npm start
   ```
   前端將在 http://localhost:3000 運行。

## 使用說明

1. 在網頁界面的輸入框中輸入您的 AWS 價格查詢，例如：

   - "東京 linux t2.micro 價格為多少"
   - "AWS EC2 us-east-1 區域的 m5.xlarge Windows 執行個體每小時費用是多少"
   - "新加坡區域的 t3.medium Linux 實例的費用"

2. 點擊"查詢"按鈕提交您的問題。

3. 系統將顯示查詢結果，包括：
   - 自然語言回答
   - 識別的查詢參數
   - 詳細的價格數據

## 擴展方向

- 增加對更多 AWS 服務的支持（RDS, S3 等）
- 支持更複雜的價格計算（例如按使用量和時間的估算）
- 增加歷史查詢功能
- 實現數據緩存以提高性能
