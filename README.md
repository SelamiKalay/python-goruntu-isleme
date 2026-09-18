# Python Görüntü İşleme Projeleri

OpenCV, MediaPipe ve face_recognition kullanılarak geliştirilmiş, kamera tabanlı
küçük bilgisayarlı görü projeleri.

| Proje | Açıklama | Kütüphaneler |
|---|---|---|
| [`el-hareketi-muzik-kontrolu`](el-hareketi-muzik-kontrolu) | İki el aynı anda belirli bir işareti (başparmak + işaret + orta parmak açık) yaptığında müziği çalan, eller indirilince durduran oynatıcı | OpenCV, MediaPipe, pygame |
| [`yuz-tanima-muzik-calar`](yuz-tanima-muzik-calar) | Kameraya tanımlı yüz geldiğinde müziği otomatik başlatan oynatıcı | face_recognition, OpenCV, pygame |
| [`hareket-algilama`](hareket-algilama) | Arka plan çıkarma ile hareket algılama; Telegram'a fotoğraflı bildirim gönderen sürümü de var | OpenCV, NumPy, requests |
| [`el-cercevesi-efektler`](el-cercevesi-efektler) | İki elin parmaklarıyla oluşturulan çerçevenin içine gerçek zamanlı görüntü efektleri (X-ray, karikatür, neon, glitch, gece görüşü ve daha fazlası); cımbız hareketiyle efekt değiştirme | OpenCV, MediaPipe, NumPy |
| [`guvenlik-kamerasi`](guvenlik-kamerasi) | Hareket algılandığında sesli video kaydeden ve kaydı Telegram'a gönderen güvenlik kamerası | OpenCV, PyAudio, MoviePy |

## Kurulum

```bash
pip install -r requirements.txt
```

> `face_recognition` kütüphanesi `dlib`'e bağımlıdır; Windows'ta kurulum için
> CMake ve Visual C++ Build Tools gerekebilir.

## Kullanım Notları

- **El hareketi müzik kontrolü:** MediaPipe el modeli ilk çalıştırmada otomatik
  indirilir. Script ile aynı klasöre `music.mp3` adında bir müzik dosyası koyun.
- **Yüz tanıma müzik çalar:** Script ile aynı klasöre referans yüz fotoğrafınızı
  (`my_face.jpg`) ve çalınacak müziği (`song.mp3`) koyun.
- **Telegram bildirimleri:** Bot bilgileri koda yazılmaz, ortam değişkenlerinden okunur:

  ```bash
  set TELEGRAM_BOT_TOKEN=<BotFather'dan alınan token>
  set TELEGRAM_CHAT_ID=<sohbet id>
  ```

  Sohbet ID'nizi öğrenmek için `guvenlik-kamerasi/get_telegram_id.py` scriptini
  çalıştırıp botunuza mesaj gönderebilirsiniz.
