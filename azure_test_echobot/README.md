在 Azure 創建 App Service + Azure Bot 
---
1. 用 local git 的方式將這份程式碼 deploy 到 web app 上
2. 到 App registration 取得 `Application (Client) ID` 並產生一個新的 secret，複製 `secret value`
3. 更改 web app 的 Configuration，general setting 的 startup command : `gunicorn --bind 0.0.0.0 --worker-class aiohttp.worker.GunicornWebWorker --timeout 600 app:APP`
4. bot 的 messaging endpoint 設為 web app 的 default domain + `/api/messages`
5. 連通 Line 只要在 channel 改 token 等，複製 bot 的 webhook url 貼上即可

**問題:**
- 無法在 'PodcastSearcher' resource group 下新增 bot service，似乎是權限的問題
- 因為是用 Microsoft 的 Bot Framework，和之前 linebotsdk+flask 的寫法不同，不確定能不能用 linebot 內建的一些功能，例如選單。
   
ref: [利用 Azure Portal 建立 chatbot 相關的雲端資源](https://ithelp.ithome.com.tw/articles/10246979)
echobot ref: [echobot sample](https://github.com/microsoft/BotBuilder-Samples/tree/main/samples/python/02.echo-bot?fbclid=IwAR3Yjm9IpIvCOhHv7-veFD9uIW81nZgbIkI5ltoopz7Kf_YLJkZglc1beQg)
