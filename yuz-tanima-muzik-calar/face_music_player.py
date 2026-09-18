# =============================================================================
# Face Detection Music Player
# =============================================================================
# Bu script, yüz tanıma kullanarak müzik çalmayı otomatik olarak başlatır.
# Kamera karşısındaki yüz tanındığında belirtilen müzik dosyası çalınır.
#
# GEREKLİ KÜTÜPHANELERİN KURULUMU:
# ---------------------------------
# pip install face_recognition
# pip install opencv-python
# pip install pygame
# pip install numpy
#
# NOT: face_recognition kütüphanesi dlib kütüphanesine bağımlıdır.
# Windows'ta dlib kurulumu için CMake ve Visual Studio Build Tools gerekebilir.
# Alternatif olarak: pip install cmake
#                    pip install dlib
#
# KULLANIM:
# ---------
# 1. 'my_face.jpg' dosyasını script ile aynı klasöre koyun (referans yüzünüz)
# 2. 'song.mp3' dosyasını script ile aynı klasöre koyun (çalınacak müzik)
# 3. Script'i çalıştırın: python face_music_player.py
# 4. Çıkmak için 'q' tuşuna basın
# =============================================================================

import cv2
import face_recognition
import pygame
import numpy as np
import os
import time

# =============================================================================
# YAPILANDIRMA AYARLARI
# =============================================================================
# Referans yüz resmi ve müzik dosyası yolları
# Bu değerleri kendi dosya yollarınızla değiştirin
REFERENCE_IMAGE_PATH = "my_face.jpeg"  # Tanınacak yüzün referans fotoğrafı
MUSIC_FILE_PATH = "song.mp3"          # Çalınacak müzik dosyası

# Yüz eşleşme toleransı (düşük = daha katı eşleşme, yüksek = daha esnek)
FACE_MATCH_TOLERANCE = 0.6

# Kamera işleme ayarları (performans için frame atlama)
PROCESS_EVERY_N_FRAMES = 12  # OPTİMİZASYON: Yüksek çözünürlük (0.50) için değer 12'ye çıkarıldı.

# Debounce ayarları - müziğin sürekli baştan başlamasını önler
RECOGNITION_COOLDOWN = 2.0  # Saniye cinsinden bekleme süresi (Başlatma için)
STOP_COOLDOWN = 1.0         # Saniye cinsinden bekleme süresi (Durdurma için)


# =============================================================================
# YARDIMCI FONSİYONLAR (Devamı...)
# =============================================================================
def resolve_music_path(file_path):
    """
    Verilen dosya yolunu inceler. Eğer bir M3U/M3U8 çalma listesiyse,
    içindeki ilk geçerli müzik dosyasının yolunu döndürür.
    Değilse, dosya yolunu olduğu gibi döndürür.
    """
    if not os.path.exists(file_path):
        return file_path
        
    # Uzantı kontrolü
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.m3u', '.m3u8']:
        print(f"[INFO] Playlist dosyası algılandı: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                # Yorum satırlarını ve boş satırları atla
                if not line or line.startswith('#'):
                    continue
                
                # Dosya yolunu oluştur (playlist ile aynı klasörde olabilir)
                potential_path = line
                if not os.path.isabs(potential_path):
                    playlist_dir = os.path.dirname(os.path.abspath(file_path))
                    potential_path = os.path.join(playlist_dir, potential_path)
                
                if os.path.exists(potential_path):
                    print(f"[INFO] Playlist içinden dosya seçildi: {potential_path}")
                    return resolve_music_path(potential_path) # Recursive check (iç içe playlist için)
            
            print("[UYARI] Playlist içinde geçerli bir dosya bulunamadı!")
        except Exception as e:
            print(f"[HATA] Playlist okunurken hata: {e}")
            
    return file_path

def check_music_file_format(file_path):
    """
    Müzik dosyasının formatını kontrol eder.
    MP3 uzantılı olup aslında M4A/MP4 olan dosyaları tespit eder.
    """
    # Önce playlist ise çözümle
    actual_path = resolve_music_path(file_path)
    
    if not os.path.exists(actual_path):
        return
        
    try:
        with open(actual_path, 'rb') as f:
            header = f.read(12)
            # M4A/MP4 imzası kontrolü (ftyp)
            if len(header) >= 8 and header[4:8] == b'ftyp':
                print("=" * 60)
                print(f"[UYARI] '{os.path.basename(actual_path)}' dosyası 'MP3' uzantılı veya M4A formatında!")
                print("[UYARI] Pygame varsayılan olarak bu formatı (MPEG-4 Audio) desteklemeyebilir.")
                print("[ÇÖZÜM] Lütfen dosyayı gerçek bir MP3 veya WAV formatına dönüştürün.")
                print("=" * 60)
            elif header[:3] == b'ID3' or header[:2] == b'\xff\xfb' or header[:2] == b'\xff\xf3':
                 print("[INFO] Dosya formatı doğrulandı (MP3/ID3).")
    except Exception as e:
        print(f"[UYARI] Dosya formatı kontrol edilirken hata: {e}")
    
    return actual_path

# =============================================================================
# PYGAME MÜZİK ÇALAR BAŞLATMA
# =============================================================================
def initialize_audio():
    """
    Pygame mixer modülünü başlatır.
    """
    # Başlangıçta dosya kontrolü yap (bilgi amaçlı)
    check_music_file_format(MUSIC_FILE_PATH)
    
    try:
        pygame.mixer.init()
        print("[INFO] Ses sistemi başlatıldı.")
    except Exception as e:
        print(f"[HATA] Ses sistemi başlatılamadı: {e}")


# =============================================================================
# REFERANS YÜZ KODLAMASI YÜKLEME
# =============================================================================
def load_reference_faces():
    """
    Çalışma dizinindeki 'my_face*.jpg/jpeg' formatındaki tüm resimleri arar ve yükler.
    
    Returns:
        Yüz kodlamaları listesi (List of numpy arrays)
    """
    known_encodings = []
    
    # Desteklenen uzantılar
    valid_extensions = ['.jpg', '.jpeg', '.png']
    
    print("[INFO] Referans yüzler aranıyor...")
    
    # Dizin içindeki dosyaları tara
    current_dir = os.path.dirname(os.path.abspath(__file__)) # Script'in olduğu klasör
    files = os.listdir(current_dir)
    
    count = 0
    for filename in files:
        # İsim kontrolü: 'my_face' ile başlamalı
        if not filename.lower().startswith("my_face"):
            continue
            
        # Uzantı kontrolü
        ext = os.path.splitext(filename)[1].lower()
        if ext not in valid_extensions:
            continue
            
        full_path = os.path.join(current_dir, filename)
        print(f"[INFO] Yükleniyor: {filename}")
        
        try:
            image = face_recognition.load_image_file(full_path)
            encodings = face_recognition.face_encodings(image)
            
            if len(encodings) > 0:
                known_encodings.append(encodings[0])
                count += 1
                print(f"      -> Başarılı.")
            else:
                print(f"      -> [UYARI] Yüz algılanamadı, atlanıyor.")
                
        except Exception as e:
            print(f"      -> [HATA] {e}")
            
    if count == 0:
        print("[HATA] Hiçbir referans yüz yüklenemedi!")
        print("[BILGI] Lütfen 'my_face.jpeg', 'my_face1.jpeg' vb. dosyaları klasöre ekleyin.")
        return None
        
    print(f"[INFO] Toplam {count} referans yüz hafızaya alındı.")
    return known_encodings


# =============================================================================
# MÜZİK KONTROL FONKSİYONLARI
# =============================================================================
def play_music(music_path):
    """
    Belirtilen müzik dosyasını (veya playlisti) çalar.
    """
    # Dosya yolunu çözümle (M3U vb. ise içindeki dosyayı al)
    actual_path = resolve_music_path(music_path)
    
    if not os.path.exists(actual_path):
        print(f"[HATA] Müzik dosyası bulunamadı: {actual_path}")
        return False
    
    try:
        pygame.mixer.music.load(actual_path)
        pygame.mixer.music.play()
        print(f"[INFO] Müzik çalınmaya başladı: {os.path.basename(actual_path)}")
        return True
    except Exception as e:
        print(f"[HATA] Müzik çalınamadı: {e}")
        return False


def is_music_playing():
    """
    Müziğin şu anda çalıp çalmadığını kontrol eder.
    
    Returns:
        True eğer müzik çalıyorsa, False değilse
    """
    return pygame.mixer.music.get_busy()


def stop_music():
    """
    Çalan müziği durdurur.
    """
    try:
        pygame.mixer.music.stop()
        print("[INFO] Müzik durduruldu.")
    except:
        pass


# =============================================================================
# ANA YÜZ TANIMA VE MÜZİK ÇALAR DÖNGÜSÜ
# =============================================================================
def main():
    """
    Ana program döngüsü.
    Webcam'i başlatır, yüz tanıma yapar ve eşleşme durumunda müzik çalar.
    """
    # Ses sistemini başlat
    initialize_audio()
    
    # Referans yüzleri yükle (LİSTE OLARAK)
    known_face_encodings = load_reference_faces()
    if known_face_encodings is None:
        print("[HATA] Program sonlandırılıyor - referans yüzler yok.")
        return
    
    # Webcam'i başlat
    print("[INFO] Webcam başlatılıyor...")
    # cv2.CAP_DSHOW windows'ta bazen daha hızlı açılış sağlar
    video_capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    if not video_capture.isOpened():
        # DSHOW ile açılmazsa normal dene
        video_capture = cv2.VideoCapture(0)
        
    if not video_capture.isOpened():
        print("[HATA] Webcam açılamadı!")
        return
    
    print("[INFO] Webcam başarıyla açıldı.")
    print("[INFO] Çıkmak için 'q' tuşuna basın.")
    print("-" * 50)
    
    # Durum değişkenleri
    frame_count = 0                    # İşlenen frame sayacı
    last_recognition_time = 0          # Son tanıma zamanı (debounce için)
    last_face_seen_time = time.time()  # Yüzün en son görüldüğü zaman
    face_locations = []                # Tespit edilen yüz konumları
    face_names = []                    # Tespit edilen yüz isimleri/durumları
    current_status = "Yuz araniyor..." # Ekranda gösterilecek durum
    
    # Optimizasyon: Küçültme oranı (0.20 = %20 boyut)
    # Uzaktan algılama için çözünürlük artırıldı (0.20 -> 0.50)
    RESIZE_RATIO = 0.50
    
    while True:
        # Kameradan bir frame oku
        ret, frame = video_capture.read()
        if not ret:
            print("[HATA] Frame okunamadı!")
            break
        
        # Performans için frame'i küçült (yüz tespiti için)
        small_frame = cv2.resize(frame, (0, 0), fx=RESIZE_RATIO, fy=RESIZE_RATIO)
        
        # OpenCV BGR formatından RGB'ye dönüştür
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        current_time = time.time()
        
        # Her N frame'de bir yüz analizi yap
        frame_count += 1
        if frame_count % PROCESS_EVERY_N_FRAMES == 0:
            # Yüzleri tespit et
            face_locations = face_recognition.face_locations(rgb_small_frame)
            
            # Tespit edilen yüzlerin kodlamalarını çıkar
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            face_names = []
            user_recognized = False
            
            for face_encoding in face_encodings:
                # Yüzü referans yüzler LİSTESİ ile karşılaştır
                # compare_faces artık bir liste ile karşılaştırıyor ve boolean liste dönüyor
                matches = face_recognition.compare_faces(
                    known_face_encodings, 
                    face_encoding, 
                    tolerance=FACE_MATCH_TOLERANCE
                )
                
                name = "Bilinmeyen"
                
                # Eğer matches listesinde herhangi bir True varsa, yüzlerden biriyle eşleşmiştir
                if True in matches:
                    # Eşleşme bulundu
                    name = "Kullanici Tanindi"
                    user_recognized = True
                    last_face_seen_time = current_time # Yüz görüldü, zamanı güncelle
                
                face_names.append(name)
            
            # Kullanıcı tanındıysa müzik mantığını işle
            if user_recognized:
                # Debounce kontrolü
                music_busy = is_music_playing()
                
                if not music_busy:
                    if current_time - last_recognition_time > RECOGNITION_COOLDOWN:
                        print("[DEBUG] Müzik başlatma koşulları sağlandı.")
                        if play_music(MUSIC_FILE_PATH):
                             last_recognition_time = current_time
                
                current_status = "Kullanici Tanindi - Muzik Caliniyor"
            else:
                # Sadece kullanıcı yoksa diğer durumları kontrol et
                if len(face_locations) > 0:
                    current_status = "Bilinmeyen yuz"
                else:
                    current_status = "Yuz araniyor..."
                    
            # Müzik DURDURMA mantığı (Auto-Stop)
            if is_music_playing():
                time_since_last_seen = current_time - last_face_seen_time
                if time_since_last_seen > STOP_COOLDOWN:
                    print(f"[INFO] Yüz {STOP_COOLDOWN} saniyedir görülmedi. Müzik durduruluyor...")
                    stop_music()
                    current_status = "Yuz kayboldu - Muzik Durduruldu"

        
        # =====================================================================
        # GÖRSEL GERİ BİLDİRİM - ÇERÇEVELER KALDIRILDI
        # =====================================================================
        # Kullanıcı isteği üzerine yüz çerçeveleri ve isim etiketleri kaldırıldı.
        # Sadece sol üstteki genel durum bilgisi gösterilecek.
        
        # Üst köşeye genel durum bilgisi ekle
        cv2.putText(frame, current_status, (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Müzik durumu göstergesi
        music_status = "Muzik: CALINIYOR" if is_music_playing() else "Muzik: DURDU"
        music_color = (0, 255, 0) if is_music_playing() else (128, 128, 128)
        cv2.putText(frame, music_status, (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, music_color, 2)
        
        # Frame'i ekranda göster
        cv2.imshow('Face Detection Music Player - Cikmak icin Q', frame)
        
        # 'q' tuşuna basıldığında çık
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n[INFO] Çıkış yapılıyor...")
            break
    
    # Temizlik işlemleri
    print("[INFO] Kaynaklar serbest bırakılıyor...")
    video_capture.release()
    cv2.destroyAllWindows()
    pygame.mixer.quit()
    print("[INFO] Program sonlandırıldı.")


# =============================================================================
# PROGRAM GİRİŞ NOKTASI
# =============================================================================
if __name__ == "__main__":
    print("=" * 50)
    print("   YÜZ TANIMI MÜZİK ÇALAR")
    print("=" * 50)
    main()
