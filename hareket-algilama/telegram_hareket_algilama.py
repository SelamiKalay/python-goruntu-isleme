# ==============================================================================
# TELEGRAM ENTEGRASYONLU HAREKET ALGILAMA SISTEMI
# ==============================================================================
# Gerekli kutuphaneler:
# pip install opencv-python numpy requests
# ==============================================================================

import cv2
import numpy as np
import requests
from datetime import datetime
import time
import io
import os

# ==============================================================================
# TELEGRAM BOT AYARLARI
# ==============================================================================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ==============================================================================
# YAPILANDIRMA AYARLARI
# ==============================================================================

# Hareket algilama esik degeri (piksel cinsinden kontur alani)
HAREKET_ESIK_DEGERI = 5000

# Gaussian Blur kernel boyutu (tek sayi olmali, gurultuyu azaltir)
BLUR_KERNEL_BOYUTU = (21, 21)

# Ikili esikleme (thresholding) degeri (0-255 arasi)
THRESHOLD_DEGERI = 30

# Spam korumasi: Fotograf gonderme bekleme suresi (saniye)
COOLDOWN_SURESI = 5

# ==============================================================================
# TELEGRAM FONKSIYONLARI
# ==============================================================================

def telegram_fotograf_gonder(frame, mesaj="[!] HAREKET ALGILANDI!"):
    """
    Hareket algilandiginda fotografi Telegram'a gonderir.
    
    Args:
        frame: Gonderilecek goruntu karesi (numpy array)
        mesaj: Fotografla birlikte gonderilecek mesaj
    
    Returns:
        bool: Gonderim basarili ise True, degilse False
    """
    try:
        # Telegram Bot API URL'si
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        
        # OpenCV goruntusunu JPEG formatina cevir
        # imencode, goruntuyu bellek icinde encode eder
        basarili, buffer = cv2.imencode('.jpg', frame)
        
        if not basarili:
            print("[HATA] Goruntu encode edilemedi!")
            return False
        
        # Buffer'i bytes'a cevir
        foto_bytes = io.BytesIO(buffer.tobytes())
        
        # Tarih ve saat bilgisini mesaja ekle
        simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tam_mesaj = f"{mesaj}\nTarih/Saat: {simdi}"
        
        # Telegram'a gonderilecek dosya ve veriler
        files = {
            'photo': ('hareket.jpg', foto_bytes, 'image/jpeg')
        }
        data = {
            'chat_id': CHAT_ID,
            'caption': tam_mesaj
        }
        
        # POST istegi gonder (timeout: 10 saniye)
        response = requests.post(url, files=files, data=data, timeout=10)
        
        # Yaniti kontrol et
        if response.status_code == 200:
            print(f"[TELEGRAM] [OK] Fotograf basariyla gonderildi! ({simdi})")
            return True
        else:
            print(f"[TELEGRAM] [X] Gonderim basarisiz! Kod: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        # Istek zaman asimina ugradi
        print("[HATA] Telegram istegi zaman asimina ugradi!")
        return False
        
    except requests.exceptions.ConnectionError:
        # Internet baglantisi yok veya koptu
        print("[HATA] Internet baglantisi yok! Program calismaya devam ediyor...")
        return False
        
    except requests.exceptions.RequestException as e:
        # Diger request hatalari
        print(f"[HATA] Telegram hatasi: {e}")
        return False
        
    except Exception as e:
        # Beklenmeyen hatalar
        print(f"[HATA] Beklenmeyen hata: {e}")
        return False

def telegram_mesaj_gonder(mesaj):
    """
    Telegram'a sadece metin mesaji gonderir.
    
    Args:
        mesaj: Gonderilecek metin
    
    Returns:
        bool: Gonderim basarili ise True, degilse False
    """
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            'chat_id': CHAT_ID,
            'text': mesaj,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
        
    except Exception:
        # Hata durumunda sessizce devam et
        return False

# ==============================================================================
# ANA HAREKET ALGILAMA FONKSIYONU
# ==============================================================================

def hareket_algilama():
    """
    Ana hareket algilama fonksiyonu.
    
    Algoritma:
    1. Web kamerasini baslat
    2. Her kareyi oku
    3. Gri tonlamaya cevir
    4. GaussianBlur uygula (gurultuyu azalt)
    5. Onceki kare ile farki hesapla (Frame Differencing)
    6. Threshold uygula (ikili goruntu olustur)
    7. Konturlari bul
    8. Buyuk konturlari hareket olarak isaretle
    9. Cooldown suresine uyarak Telegram'a fotograf gonder
    """
    
    print("[BILGI] Web kamerasi baslatiliyor...")
    
    # ==============================================================================
    # ADIM 1: Web kamerasini baslat
    # ==============================================================================
    kamera = cv2.VideoCapture(0)  # 0 = varsayilan kamera
    
    # Kamera acilip acilmadigini kontrol et
    if not kamera.isOpened():
        print("[HATA] Web kamerasi acilamadi!")
        return
    
    print("[BILGI] [OK] Web kamerasi basariyla baslatildi.")
    print("[BILGI] Cikmak icin 'q' tusuna basin.")
    print("-" * 50)
    
    # Telegram'a baslangic mesaji gonder
    telegram_mesaj_gonder("[SISTEM] <b>Hareket Algilama Sistemi Baslatildi!</b>\n\nKamera aktif, izleme basladi...")
    
    # Ilk kare icin referans (onceki kare)
    onceki_kare = None
    
    # Son fotograf gonderme zamani (spam korumasi icin)
    son_gonderim_zamani = 0
    
    # ==============================================================================
    # ADIM 2: Ana dongu - Surekli kare okuma ve isleme
    # ==============================================================================
    while True:
        # Kameradan bir kare oku
        ret, kare = kamera.read()
        
        # Kare okunamadiysa donguden cik
        if not ret:
            print("[HATA] Kare okunamadi!")
            break
        
        # Orijinal kareyi sakla (Telegram'a gondermek icin)
        orijinal_kare = kare.copy()
        
        # ==============================================================================
        # ADIM 3: Goruntuyu gri tonlamaya cevir
        # ==============================================================================
        # Renk isleme maliyetini azaltmak icin gri tonlama kullanilir
        gri_kare = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
        
        # ==============================================================================
        # ADIM 4: GaussianBlur uygula
        # ==============================================================================
        # Gurultuyu azaltir ve kucuk hareketleri filtreler
        # Bu, hatali alarmlari onlemeye yardimci olur
        bulanik_kare = cv2.GaussianBlur(gri_kare, BLUR_KERNEL_BOYUTU, 0)
        
        # ==============================================================================
        # ADIM 5: Ilk kare kontrolu
        # ==============================================================================
        if onceki_kare is None:
            onceki_kare = bulanik_kare
            continue
        
        # ==============================================================================
        # ADIM 6: Frame Differencing - Kareler arasi fark hesaplama
        # ==============================================================================
        # Onceki kare ile su anki kare arasindaki mutlak farki hesapla
        kare_farki = cv2.absdiff(onceki_kare, bulanik_kare)
        
        # ==============================================================================
        # ADIM 7: Threshold (Esikleme) uygula
        # ==============================================================================
        _, threshold_kare = cv2.threshold(
            kare_farki, 
            THRESHOLD_DEGERI, 
            255, 
            cv2.THRESH_BINARY
        )
        
        # ==============================================================================
        # ADIM 8: Morfolojik islemler - Gurultuyu temizle
        # ==============================================================================
        threshold_kare = cv2.dilate(threshold_kare, None, iterations=2)
        
        # ==============================================================================
        # ADIM 9: Konturlari bul
        # ==============================================================================
        konturlar, _ = cv2.findContours(
            threshold_kare.copy(), 
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Hareket durumu bayragi
        hareket_algilandi = False
        en_buyuk_alan = 0
        
        # ==============================================================================
        # ADIM 10: Her kontur icin hareket kontrolu
        # ==============================================================================
        for kontur in konturlar:
            alan = cv2.contourArea(kontur)
            
            if alan > en_buyuk_alan:
                en_buyuk_alan = alan
            
            # Esik degerinden kucuk konturlari atla
            if alan < HAREKET_ESIK_DEGERI:
                continue
            
            hareket_algilandi = True
            
            # Konturun sinirlayici dikdortgenini ciz
            (x, y, w, h) = cv2.boundingRect(kontur)
            cv2.rectangle(kare, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # ==============================================================================
        # ADIM 11: Hareket algilandiginda Telegram'a gonder
        # ==============================================================================
        if hareket_algilandi:
            # Ekrana uyari yaz
            cv2.putText(
                kare, 
                "HAREKET ALGILANDI!", 
                (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                1, 
                (0, 0, 255),
                2
            )
            
            # Su anki zamani al
            simdi = time.time()
            
            # ==============================================================================
            # SPAM KORUMASI: Cooldown kontrolu
            # ==============================================================================
            # Son gonderimden bu yana gecen sureyi kontrol et
            gecen_sure = simdi - son_gonderim_zamani
            
            if gecen_sure >= COOLDOWN_SURESI:
                # Cooldown suresi doldu, fotograf gonder
                print(f"[ALGILAMA] [!] Hareket algilandi! Alan: {int(en_buyuk_alan)} piksel")
                
                # Telegram'a fotograf gonder (hata olursa program devam eder)
                if telegram_fotograf_gonder(orijinal_kare):
                    son_gonderim_zamani = simdi
                else:
                    # Gonderim basarisiz olsa bile cooldown'u guncelle
                    # Boylece surekli deneme yapmaz
                    son_gonderim_zamani = simdi
            else:
                # Cooldown suresi icindeyiz, bekleme suresini goster
                kalan_sure = COOLDOWN_SURESI - gecen_sure
                print(f"[COOLDOWN] Bekleniyor... {kalan_sure:.1f} saniye kaldi")
        
        # ==============================================================================
        # ADIM 12: Durum bilgilerini ekrana yaz
        # ==============================================================================
        # Cooldown durumunu goster
        gecen_sure = time.time() - son_gonderim_zamani
        if gecen_sure < COOLDOWN_SURESI and son_gonderim_zamani > 0:
            kalan = COOLDOWN_SURESI - gecen_sure
            cooldown_metni = f"COOLDOWN: {kalan:.1f}s"
            cv2.putText(kare, cooldown_metni, (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        
        # Esik ve algilanan alan bilgisi
        durum_metni = f"Esik: {HAREKET_ESIK_DEGERI} | Algilanan: {int(en_buyuk_alan)}"
        cv2.putText(kare, durum_metni, (10, kare.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Telegram baglanti durumu
        cv2.putText(kare, "Telegram: AKTIF", (kare.shape[1] - 180, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # ==============================================================================
        # ADIM 13: Goruntuleri ekranda goster
        # ==============================================================================
        cv2.imshow("Telegram Hareket Algilama", kare)
        cv2.imshow("Threshold", threshold_kare)
        
        # Onceki kareyi guncelle
        onceki_kare = bulanik_kare
        
        # ==============================================================================
        # ADIM 14: Cikis kontrolu
        # ==============================================================================
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n[BILGI] Program sonlandiriliyor...")
            break
    
    # ==============================================================================
    # TEMIZLIK
    # ==============================================================================
    # Telegram'a kapanis mesaji gonder
    telegram_mesaj_gonder("[SISTEM] <b>Hareket Algilama Sistemi Kapatildi!</b>")
    
    kamera.release()
    cv2.destroyAllWindows()
    
    print("[BILGI] Program basariyla sonlandirildi.")

# ==============================================================================
# PROGRAMI BASLAT
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("   TELEGRAM ENTEGRASYONLU HAREKET ALGILAMA SISTEMI")
    print("=" * 60)
    print()
    print("Yapilandirma:")
    print(f"  - Hareket esik degeri: {HAREKET_ESIK_DEGERI} piksel")
    print(f"  - Cooldown suresi: {COOLDOWN_SURESI} saniye")
    print(f"  - Telegram Bot: Aktif")
    print(f"  - Chat ID: {CHAT_ID}")
    print()
    print("-" * 60)
    
    hareket_algilama()
