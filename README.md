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



---------------------------------------------------------
清空測試資料 - asset
打開 CMD 或 PowerShell，進到專案根目錄：

cd 資產管理系統2026
python
from core import db
from core.models import Asset

# 清空 assets 表
db.session.query(Asset).delete()
db.session.commit()

print(db.session.query(Asset).count())
如果顯示 0，代表已經清空。
