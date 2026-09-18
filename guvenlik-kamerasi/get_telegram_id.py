import requests
import time
import os

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

def get_chat_id():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    print(f"Lütfen Telegram botunuza (@bot_ismi) gidin ve '/start' yazın veya bir mesaj gönderin.")
    print("Bekleniyor...")
    
    while True:
        try:
            response = requests.get(url)
            data = response.json()
            
            if data["ok"] and data["result"]:
                last_msg = data["result"][-1]
                chat_id = last_msg["message"]["chat"]["id"]
                user_name = last_msg["message"]["chat"].get("first_name", "Kullanıcı")
                
                print("\n" + "="*40)
                print(f"BAŞARILI! Mesaj alındı: {user_name}")
                print(f"Sizin Chat ID'niz: {chat_id}")
                print("="*40)
                print("Bu ID'yi security_cam.py dosyasındaki CHAT_ID kısmına yapıştırın.")
                break
            else:
                time.sleep(2)
        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(2)

if __name__ == "__main__":
    get_chat_id()
