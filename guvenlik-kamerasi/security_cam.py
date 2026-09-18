# GEREKLİ KÜTÜPHANELER:
# pip install opencv-python pyaudio moviepy requests

import cv2
import datetime
import os
import requests
import time
import threading
import wave
import pyaudio
import sys

# MoviePy Uyumluluk Bloğu
try:
    from moviepy.editor import VideoFileClip, AudioFileClip
except ImportError:
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        from moviepy.audio.io.AudioFileClip import AudioFileClip
    except ImportError:
        from moviepy import VideoFileClip, AudioFileClip

# --- AYARLAR ---
# Telegram
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Hareket
MIN_AREA = 2500
BUFFER_TIME = 5
WARMUP_FRAMES = 50
ALPHA = 0.5
THRESHOLD_VAL = 25

# Ses
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.thread = None
        self.filename = None

    def start(self, filename):
        self.filename = filename
        self.frames = []
        self.is_recording = True
        try:
            self.stream = self.audio.open(format=FORMAT, channels=CHANNELS,
                                          rate=RATE, input=True,
                                          frames_per_buffer=CHUNK)
            self.thread = threading.Thread(target=self._record)
            self.thread.start()
            print(f"[SES] Kayıt Başladı: {self.filename}")
        except Exception as e:
            print(f"[SES HATASI] {e}")
            self.is_recording = False

    def _record(self):
        while self.is_recording:
            try:
                data = self.stream.read(CHUNK)
                self.frames.append(data)
            except:
                break

    def stop(self):
        self.is_recording = False
        if self.thread:
            self.thread.join()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if self.filename and self.frames:
            wf = wave.open(self.filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            print("[SES] Dosya Kaydedildi.")

    def terminate(self):
        self.audio.terminate()

def process_and_send(temp_video, temp_audio, final_output):
    """
    Video ve sesi birleştir, Telegram'a gönder, temizle.
    """
    try:
        print("[ISLEM] Video ve Ses birleştiriliyor (MoviePy)...")
        
        if os.path.exists(temp_video) and os.path.exists(temp_audio):
            # Dosyaları yükle
            video_clip = VideoFileClip(temp_video)
            audio_clip = AudioFileClip(temp_audio)
            
            # Sesi videoya ekle
            # Videonun süresi esas alınır
            # Ses süresi videodan uzunsa veya kısaysa kes/ayarla (Senkronizasyon için önemli)
            # Genellikle video süresi esas alınır
            if hasattr(video_clip, 'with_audio'):
                # MoviePy 2.0+
                final_clip = video_clip.with_audio(audio_clip)
            else:
                # MoviePy 1.x
                final_clip = video_clip.set_audio(audio_clip)
            
            # Çıktı al (logger=None ile konsol kirliliğini engelle)
            # preset='ultrafast' ile hızlı render
            final_clip.write_videofile(final_output, codec='libx264', audio_codec='aac', logger=None, preset='ultrafast')
            
            # Kaynakları serbest bırak
            video_clip.close()
            audio_clip.close()
            
            print(f"[TAMAM] Final dosya hazır: {final_output}")
            
            # Telegram Gönderimi
            send_telegram_video(final_output)
            
            # Temizlik
            # Kullanıcı "Geçici dosyaları sil" dedi
            if os.path.exists(temp_video): os.remove(temp_video)
            if os.path.exists(temp_audio): os.remove(temp_audio)
            print("[TEMIZLIK] Geçici dosyalar silindi.")
            
        else:
            print("[HATA] Geçici dosyalar bulunamadı!")
            
    except Exception as e:
        print(f"[HATA] İşlem sırasında hata: {e}")

def send_telegram_video(filename):
    if not BOT_TOKEN or not CHAT_ID: return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    print(f"[UPLOAD] Telegram'a yükleniyor: {filename}")
    
    try:
        # Dosyanın tamamen yazıldığından emin olmak için kısa bekleme
        time.sleep(1)
        with open(filename, 'rb') as f:
            files = {'video': f}
            data = {'chat_id': CHAT_ID, 'caption': f'Hareket Algilandi: {filename}'}
            resp = requests.post(url, files=files, data=data)
            
        if resp.status_code == 200:
            print("[BAŞARILI] Video gönderildi.")
            # Final dosyayı da silebiliriz (Opsiyonel, kullanıcı belirtmedi ama mantıklı)
            # os.remove(filename)
        else:
            print(f"[HATA] Telegram Sunucu Hatası: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        print(f"[HATA] Gönderim Hatası: {e}")

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Kamera hatası!")
        return

    # Ses nesnesi
    audio_recorder = AudioRecorder()
    
    # Video Ayarları - Geçici dosya için AVI/XVID
    fourcc = cv2.VideoWriter_fourcc(*'XVID') 
    fps = 20.0 
    
    # Hareket Değişkenleri
    detection = False
    detection_stopped_time = None
    timer_started = False
    
    out = None
    frame_size = (int(cap.get(3)), int(cap.get(4)))
    
    avg_frame = None

    print("-" * 50)
    print("GUVENLIK SISTEMI DEVREDE (Video + Ses)")
    print(f"Token: {BOT_TOKEN[:5]}...")
    print(f"ChatID: {CHAT_ID}")
    print("-" * 50)
    
    # Isınma
    print("Kamera isiniyor...")
    for _ in range(WARMUP_FRAMES):
        cap.read()
        time.sleep(0.01)
    print("Izleme basladi!")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # Görüntü İşleme
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if avg_frame is None:
            avg_frame = gray.copy().astype("float")
            continue

        cv2.accumulateWeighted(gray, avg_frame, ALPHA)
        bg_model = cv2.convertScaleAbs(avg_frame)
        
        delta = cv2.absdiff(bg_model, gray)
        thresh = cv2.threshold(delta, THRESHOLD_VAL, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Ekran Gösterimi için kopya oluştur (Videoya kutu basmamak için)
        display_frame = frame.copy()

        movement = False
        for c in cnts:
            if cv2.contourArea(c) < MIN_AREA: continue
            movement = True
            (x, y, w, h) = cv2.boundingRect(c)
            # Sadece Ekranda Göster (display_frame), Kayda Basma (frame temiz kalsın)
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        now = datetime.datetime.now()
        timestamp = now.strftime("%d-%m-%Y %H:%M:%S")

        # --- DURUM YÖNETİMİ ---
        if movement:
            if detection:
                timer_started = False
            else:
                # KAYIT BAŞLAT
                detection = True
                
                # Klasör Kontrolü
                record_dir = "kayitlar"
                os.makedirs(record_dir, exist_ok=True)
                
                start_time_str = now.strftime("%Y%m%d_%H%M%S")
                
                # Geçici Dosyalar (kayitlar klasörüne)
                temp_vid = os.path.join(record_dir, f"temp_{start_time_str}.avi")
                temp_aud = os.path.join(record_dir, f"temp_{start_time_str}.wav")
                final_mp4 = os.path.join(record_dir, f"Guvenlik_Kamera_{start_time_str}.mp4")
                
                # Video Yazar
                out = cv2.VideoWriter(temp_vid, fourcc, fps, frame_size)
                
                # Ses Kayıt (Thread başlatır)
                audio_recorder.start(temp_aud)
                
                print(f"\n[ALARM] Hareket! Kayıt Başladı: {start_time_str}")

        elif detection: # Hareket durdu, bekleme buffer
            if timer_started:
                if time.time() - detection_stopped_time >= BUFFER_TIME:
                    # KAYIT DURDUR ve BİRLEŞTİR
                    detection = False
                    timer_started = False
                    
                    if out: out.release()
                    audio_recorder.stop()
                    
                    print(f"[ALARM] Kayıt Bitti. İşleniyor...")
                    
                    # Arka planda birleştir ve gönder
                    t = threading.Thread(target=process_and_send, args=(temp_vid, temp_aud, final_mp4))
                    t.start()
            else:
                timer_started = True
                detection_stopped_time = time.time()

        # Kayıt (Video Thread gibi davranan Ana Döngü)
        if detection and out:
            # Tarih damgasını VİDEOYA bas (Temiz frame üzerine)
            cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            out.write(frame)
            
            # Aynı zaman damgasını EKRAN görüntüsüne de bas (Senkron görünsün)
            cv2.putText(display_frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            # İzleme ekranına bas
            cv2.putText(display_frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        # İzleme Ekranı Durum
        cv2.putText(display_frame, "REC" if detection else "IZLENIYOR", (frame_size[0]-100, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255) if detection else (0,255,0), 2)
        cv2.imshow("Guvenlik Kamerasi (Sesli)", display_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'): break

    # Çıkış
    cap.release()
    if out: out.release()
    audio_recorder.terminate()
    cv2.destroyAllWindows()
    # Açık kalan threadleri beklemeden çıkabilir (daemon değilse) ama terminate iyidir
    sys.exit()

if __name__ == "__main__":
    main()
