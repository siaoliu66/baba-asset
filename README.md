啟動方式: 執行 `start_windows.bat`  
	-> 檢查 Docker 是否已安裝
	-> 檢查 Python 是否已安裝	
	
取得網址 內網可直接使用
外網需透過 ngrok 反向代理 產生連結使用	

---------------------------------------------------------
ngrok 使用
1.直接啟動 ngrok.exe
2.ngrok config add-authtoken <token>
3.ngrok http <port>
4.就會有網址 Forwarding的那個

只要.exe關閉 連結就會失效 下次開啟就直接從3開始做