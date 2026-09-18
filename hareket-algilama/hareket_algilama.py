# ==============================================================================
# GELİŞMİŞ HAREKET ALGILAMA SİSTEMİ (Motion Detection System)
# ==============================================================================
# Gerekli kütüphaneler:
# pip install opencv-python numpy
# ==============================================================================

import cv2
import numpy as np
from datetime import datetime
import os
import winsound  # Windows için sistem sesi

# ==============================================================================
# YAPILANDIRMA AYARLARI
# ==============================================================================

# Hareket algılama eşik değeri (piksel cinsinden kontür alanı)
HAREKET_ESIK_DEGERI = 5000

# Gaussian Blur kernel boyutu (tek sayı olmalı, gürültüyü azaltır)
BLUR_KERNEL_BOYUTU = (21, 21)

# İkili eşikleme (thresholding) değeri (0-255 arası)
THRESHOLD_DEGERI = 30

# Ses çalma özelliği (True: Açık, False: Kapalı)
SES_CALISTIR = True

# Ses frekansı ve süresi (milisaniye)
SES_FREKANSI = 1000  # Hz
SES_SURESI = 200     # ms

# Fotoğraf kayıt klasörü
KAYIT_KLASORU = "supheli_hareketler"

# ==============================================================================
# ANA FONKSİYONLAR
# ==============================================================================

def klasor_olustur():
    """
    Fotoğrafların kaydedileceği klasörü oluşturur.
    Eğer klasör zaten varsa, işlem yapılmaz.
    """
    if not os.path.exists(KAYIT_KLASORU):
        os.makedirs(KAYIT_KLASORU)
        print(f"[BİLGİ] '{KAYIT_KLASORU}' klasörü oluşturuldu.")

def fotograf_kaydet(frame):
    """
    Hareket algılandığında o anın fotoğrafını kaydeder.
    Dosya adı formatı: supheli_hareket_YYYY-MM-DD_HH-MM-SS.jpg
    
    Args:
        frame: Kaydedilecek görüntü karesi
    
    Returns:
        str: Kaydedilen dosyanın yolu
    """
    # Şu anki tarih ve saat bilgisini al
    simdi = datetime.now()
    tarih_saat = simdi.strftime("%Y-%m-%d_%H-%M-%S")
    
    # Dosya adını oluştur
    dosya_adi = f"supheli_hareket_{tarih_saat}.jpg"
    dosya_yolu = os.path.join(KAYIT_KLASORU, dosya_adi)
    
    # Görüntüyü kaydet
    cv2.imwrite(dosya_yolu, frame)
    print(f"[KAYIT] Şüpheli hareket kaydedildi: {dosya_yolu}")
    
    return dosya_yolu

def alarm_sesi_cal():
    """
    Hareket algılandığında sistem sesi çalar.
    Windows'ta winsound kütüphanesi kullanılır.
    """
    if SES_CALISTIR:
        try:
            winsound.Beep(SES_FREKANSI, SES_SURESI)
        except Exception as e:
            print(f"[UYARI] Ses çalınamadı: {e}")

def hareket_algilama():
    """
    Ana hareket algılama fonksiyonu.
    
    Algoritma:
    1. Web kamerasını başlat
    2. Her kareyi oku
    3. Gri tonlamaya çevir
    4. GaussianBlur uygula (gürültüyü azalt)
    5. Önceki kare ile farkı hesapla
    6. Threshold uygula (ikili görüntü oluştur)
    7. Konturları bul
    8. Büyük konturları hareket olarak işaretle
    9. Gerekirse fotoğraf çek ve alarm ver
    """
    
    # Kayıt klasörünü oluştur
    klasor_olustur()
    
    # ==============================================================================
    # ADIM 1: Web kamerasını başlat
    # ==============================================================================
    print("[BİLGİ] Web kamerası başlatılıyor...")
    kamera = cv2.VideoCapture(0)  # 0 = varsayılan kamera
    
    # Kamera açılıp açılmadığını kontrol et
    if not kamera.isOpened():
        print("[HATA] Web kamerası açılamadı!")
        return
    
    print("[BİLGİ] Web kamerası başarıyla başlatıldı.")
    print("[BİLGİ] Çıkmak için 'q' tuşuna basın.")
    print("-" * 50)
    
    # İlk kare için referans (önceki kare)
    onceki_kare = None
    
    # Son fotoğraf çekme zamanı (hızlı ardışık kayıtları önlemek için)
    son_kayit_zamani = None
    KAYIT_BEKLEME_SURESI = 2  # saniye (iki kayıt arası minimum süre)
    
    # ==============================================================================
    # ADIM 2: Ana döngü - Sürekli kare okuma ve işleme
    # ==============================================================================
    while True:
        # Kameradan bir kare oku
        ret, kare = kamera.read()
        
        # Kare okunamadıysa döngüden çık
        if not ret:
            print("[HATA] Kare okunamadı!")
            break
        
        # Orijinal kareyi sakla (kayıt için)
        orijinal_kare = kare.copy()
        
        # ==============================================================================
        # ADIM 3: Görüntüyü gri tonlamaya çevir
        # ==============================================================================
        # Renk işleme maliyetini azaltmak için gri tonlama kullanılır
        gri_kare = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
        
        # ==============================================================================
        # ADIM 4: GaussianBlur uygula
        # ==============================================================================
        # Gürültüyü azaltır ve küçük hareketleri filtreler
        # Bu, hatalı alarmları önlemeye yardımcı olur
        bulanik_kare = cv2.GaussianBlur(gri_kare, BLUR_KERNEL_BOYUTU, 0)
        
        # ==============================================================================
        # ADIM 5: İlk kare kontrolü
        # ==============================================================================
        # İlk karede karşılaştırma yapacak referans yok
        if onceki_kare is None:
            onceki_kare = bulanik_kare
            continue
        
        # ==============================================================================
        # ADIM 6: Frame Differencing - Kareler arası fark hesaplama
        # ==============================================================================
        # Önceki kare ile şu anki kare arasındaki mutlak farkı hesapla
        kare_farki = cv2.absdiff(onceki_kare, bulanik_kare)
        
        # ==============================================================================
        # ADIM 7: Threshold (Eşikleme) uygula
        # ==============================================================================
        # THRESH_BINARY: Eşik değerinin üstündeki pikseller beyaz (255), altındakiler siyah (0)
        # Bu, hareket alanlarını net bir şekilde belirler
        _, threshold_kare = cv2.threshold(
            kare_farki, 
            THRESHOLD_DEGERI, 
            255, 
            cv2.THRESH_BINARY
        )
        
        # ==============================================================================
        # ADIM 8: Morfolojik işlemler - Gürültüyü temizle
        # ==============================================================================
        # Dilate: Beyaz alanları genişletir, boşlukları doldurur
        threshold_kare = cv2.dilate(threshold_kare, None, iterations=2)
        
        # ==============================================================================
        # ADIM 9: Konturları bul
        # ==============================================================================
        # Konturlar, hareket eden nesnelerin sınırlarını belirler
        konturlar, _ = cv2.findContours(
            threshold_kare.copy(), 
            cv2.RETR_EXTERNAL,      # Sadece dış konturları bul
            cv2.CHAIN_APPROX_SIMPLE # Konturu basitleştir
        )
        
        # Hareket durumu bayrağı
        hareket_algilandi = False
        en_buyuk_alan = 0
        
        # ==============================================================================
        # ADIM 10: Her kontur için hareket kontrolü
        # ==============================================================================
        for kontur in konturlar:
            # Kontur alanını hesapla
            alan = cv2.contourArea(kontur)
            
            # En büyük alanı güncelle
            if alan > en_buyuk_alan:
                en_buyuk_alan = alan
            
            # Eşik değerinden küçük konturları atla (gürültü filtresi)
            if alan < HAREKET_ESIK_DEGERI:
                continue
            
            # Hareket algılandı!
            hareket_algilandi = True
            
            # Konturun sınırlayıcı dikdörtgenini hesapla
            (x, y, w, h) = cv2.boundingRect(kontur)
            
            # Hareket alanını yeşil dikdörtgen ile işaretle
            cv2.rectangle(kare, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # ==============================================================================
        # ADIM 11: Hareket algılandığında işlemler
        # ==============================================================================
        if hareket_algilandi:
            # Ekrana hareket uyarısı yaz
            cv2.putText(
                kare, 
                "HAREKET ALGILANDI!", 
                (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                1, 
                (0, 0, 255),  # Kırmızı renk
                2
            )
            
            # Şu anki zamanı al
            simdi = datetime.now()
            
            # Kayıt bekleme süresini kontrol et (çok hızlı ardışık kayıtları önle)
            kayit_yap = False
            if son_kayit_zamani is None:
                kayit_yap = True
            elif (simdi - son_kayit_zamani).total_seconds() >= KAYIT_BEKLEME_SURESI:
                kayit_yap = True
            
            if kayit_yap:
                # Fotoğraf kaydet
                fotograf_kaydet(orijinal_kare)
                
                # Alarm sesi çal
                alarm_sesi_cal()
                
                # Son kayıt zamanını güncelle
                son_kayit_zamani = simdi
        
        # ==============================================================================
        # ADIM 12: Durum bilgilerini ekrana yaz
        # ==============================================================================
        # Eşik değerini ve algılanan en büyük hareketi göster
        durum_metni = f"Esik: {HAREKET_ESIK_DEGERI} | Algılanan: {int(en_buyuk_alan)}"
        cv2.putText(
            kare, 
            durum_metni, 
            (10, kare.shape[0] - 10),  # Sol alt köşe
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.6, 
            (255, 255, 255),  # Beyaz renk
            1
        )
        
        # ==============================================================================
        # ADIM 13: Görüntüleri ekranda göster
        # ==============================================================================
        # Ana kamerayı göster (hareket işaretleriyle)
        cv2.imshow("Hareket Algilama Sistemi", kare)
        
        # Threshold görüntüsünü göster (debug için)
        cv2.imshow("Threshold Goruntusu", threshold_kare)
        
        # ==============================================================================
        # ADIM 14: Önceki kareyi güncelle
        # ==============================================================================
        onceki_kare = bulanik_kare
        
        # ==============================================================================
        # ADIM 15: Çıkış kontrolü
        # ==============================================================================
        # 'q' tuşuna basıldığında programı sonlandır
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n[BİLGİ] Program sonlandırılıyor...")
            break
    
    # ==============================================================================
    # TEMİZLİK
    # ==============================================================================
    # Kamerayı serbest bırak
    kamera.release()
    
    # Tüm OpenCV pencerelerini kapat
    cv2.destroyAllWindows()
    
    print("[BİLGİ] Program başarıyla sonlandırıldı.")

# ==============================================================================
# PROGRAMI BAŞLAT
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("       GELİŞMİŞ HAREKET ALGILAMA SİSTEMİ")
    print("=" * 60)
    print()
    print("Yapılandırma:")
    print(f"  - Hareket eşik değeri: {HAREKET_ESIK_DEGERI} piksel")
    print(f"  - Blur kernel boyutu: {BLUR_KERNEL_BOYUTU}")
    print(f"  - Threshold değeri: {THRESHOLD_DEGERI}")
    print(f"  - Ses bildirimi: {'Açık' if SES_CALISTIR else 'Kapalı'}")
    print(f"  - Kayıt klasörü: {KAYIT_KLASORU}/")
    print()
    print("-" * 60)
    
    # Ana fonksiyonu çağır
    hareket_algilama()
