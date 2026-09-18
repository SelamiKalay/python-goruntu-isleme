# El Çerçevesi ile Görüntü Efektleri

İki elin **başparmak** ve **işaret parmağı** uçlarıyla oluşturulan çerçevenin içindeki kamera görüntüsünü gerçek zamanlı olarak farklı görsel efektlere (X-ray, karikatür, neon, glitch, gece görüşü ve 6 efekt daha) dönüştüren bir bilgisayarlı görü projesi.

![Python](https://img.shields.io/badge/Python-3.14%20ile%20test%20edildi-blue)
![OpenCV](https://img.shields.io/badge/OpenCV-5.x-green)
![MediaPipe](https://img.shields.io/badge/MediaPipe-1.0%20Tasks%20API-orange)

---

## İçindekiler

- [Proje Fikri](#proje-fikri)
- [Nasıl Çalışır (Algoritma)](#nasıl-çalışır-algoritma)
- [Kurulum](#kurulum)
- [Kullanım](#kullanım)
- [Kod Yapısı](#kod-yapısı)
- [Efektlerin Detaylı Açıklaması](#efektlerin-detaylı-açıklaması)
- [Bilinen Sınırlamalar](#bilinen-sınırlamalar)
- [Genişletme Fikirleri](#genişletme-fikirleri)
- [Sorun Giderme](#sorun-giderme)
- [Dosyalar](#dosyalar)

---

## Proje Fikri

Fotoğraf makinesi tutar gibi iki elinle bir "çerçeve" oluşturduğunda (başparmak ve işaret parmakların birer köşe oluşturacak şekilde), o çerçevenin içindeki görüntü seçili bir efekte dönüşüyor; çerçevenin dışı normal kalıyor. Elini hareket ettirdikçe çerçeve de görüntü üzerinde hareket ediyor. Ellerini birbirine doğru uzatıp parmak uçlarını iç içe geçirdiğinde çerçeve dikdörtgenden **yatay kum saatine** dönüşüyor.

Kullanılan 4 nokta:

| Nokta | Kaynak | MediaPipe Landmark Index |
|---|---|---|
| Başparmak ucu | Ekranda soldaki el | 4 |
| İşaret parmağı ucu | Ekranda soldaki el | 8 |
| Başparmak ucu | Ekranda sağdaki el | 4 |
| İşaret parmağı ucu | Ekranda sağdaki el | 8 |

> Eller MediaPipe'ın "Left/Right" etiketiyle değil, **ekrandaki konumlarıyla** (bilek noktasının x koordinatı) ayırt edilir. Algoritma elin gerçekte sol mu sağ mı olduğuna ihtiyaç duymaz; ellerini çaprazlasan bile çalışır.

---

## Nasıl Çalışır (Algoritma)

Her karede (frame) şu adımlar sırayla işletilir:

### 1. Görüntünün Alınması
Kameradan gelen kare yatay olarak aynalanır (`cv2.flip(frame, 1)`). Böylece elini sağa götürdüğünde çerçeve de ekranda sağa gider, ayna gibi doğal bir kullanım olur.

### 2. El Tespiti
MediaPipe **Tasks API**'sindeki `HandLandmarker`, `VIDEO` modunda çalıştırılır. Her el için 21 adet landmark (eklem noktası) döndürür; `num_hands=2` ile en fazla iki el takip edilir. `VIDEO` modu kareler arası takip yaptığı için her karede sıfırdan tespitten daha hızlı ve kararlıdır; bunun için her kareye kesin artan bir zaman damgası (ms) verilir.

> Eski `mp.solutions.hands` API'si MediaPipe'ın yeni sürümlerinden kaldırıldı. Tasks API ayrı bir model dosyası (`hand_landmarker.task`) kullanır; dosya yoksa program ilk çalıştırmada onu resmi MediaPipe deposundan otomatik indirir.

### 3. Kritik Noktaların Çıkarılması
Tam olarak **iki el** görünüyorsa her elden 2 nokta alınır:
- `landmark[4]` → başparmak ucu (thumb tip)
- `landmark[8]` → işaret parmağı ucu (index finger tip)

MediaPipe koordinatları 0-1 aralığında normalize edildiğinden piksel koordinatına `x * genişlik`, `y * yükseklik` ile çevrilir.

MediaPipe ellerin listedeki sırasını kareden kareye değiştirebilir. Bu yüzden eller önce bilek x koordinatına göre soldan sağa sıralanır; böylece 4 noktanın sırası her karede aynı köşeyi temsil eder (bir sonraki adım için gerekli).

### 4. Titreme Azaltma
Parmak ucu tespitleri kareden kareye birkaç piksel oynar. Bunu azaltmak için her köşeye **üstel hareketli ortalama** uygulanır:

```python
yumuşak = alfa * önceki_yumuşak + (1 - alfa) * yeni_nokta
```

`alfa` (`--smoothing`) 0 ise yumuşatma kapalıdır; 1'e yaklaştıkça çerçeve daha stabil olur ama eli daha geç takip eder. İki el görüş alanından çıktığında geçmiş sıfırlanır.

### 5. Çokgenin Oluşturulması
4 nokta doğrudan sırayla çizilirse kendi kendini kesen bozuk bir şekil oluşabilir. Noktaları merkeze göre açıyla (`atan2`) sıralamak bu kesişmeyi önler, ancak **dışbükey (konveks) bir şekil garanti etmez**: bir nokta diğer üçünün oluşturduğu üçgenin içindeyse içbükey bir dörtgen çıkar.

Bu yüzden noktaların **dışbükey zarfı** (`cv2.convexHull`) alınır. Sonuç her durumda sıralı ve dışbükey bir çokgendir: normalde 4 köşe, bir nokta içeride kalırsa 3 köşe (üçgen). Parmaklar üst üste geldiğinde olduğu gibi alan çok küçükse çerçeve oluşturulmaz.

#### Yatay Kum Saati (Eller İç İçe)
Eller bileklerine göre soldan sağa sıralandığı için şu durum ölçülebilir: bilekler yerinde dururken **soldaki elin parmak uçları sağdaki elin parmak uçlarının sağına geçerse** eller iç içe geçmiş sayılır. Bu durumda dışbükey zarf yerine yatay kum saati çizilir:

```
sol-üst ●         ● sağ-üst
        │ ╲     ╱ │
        │   ╲ ╱   │
        │   ╱ ╲   │
        │ ╱     ╲ │
sol-alt ●         ● sağ-alt
```

- Ekranda soldaki elin iki ucu sol kenarı, sağdaki elin iki ucu sağ kenarı oluşturur
- Üst ve alt kenarlar yerine köşegenler çizilir ve ortada kesişir. Çokgen sırası: sol-üst → sol-alt → sağ-üst → sağ-alt
- `cv2.fillPoly` kendini kesen bu çokgenin iki üçgenini de doldurur; efekt iki üçgenin içine uygulanır
- Parmak uçları hizadayken şeklin dörtgen ile kum saati arasında gidip gelmemesi için geçiş, iki elin uçları arasındaki yatay fark kare genişliğinin %3'ünü aşınca yapılır (histerezis)
- Eller kadrajdan çıkınca şekil tekrar dörtgene döner

### 6. Maskeleme ve Efekt Uygulama
Efekti tüm karede hesaplamak gereksiz işlem yükü demektir. Bunun yerine:

1. Çokgeni saran dikdörtgen (`cv2.boundingRect`) bulunur ve kare sınırlarına kırpılır. Bu bölgeye **ROI** (ilgi alanı) denir.
2. Seçili efekt yalnızca bu ROI üzerinde hesaplanır.
3. ROI boyutunda tek kanallı bir maske oluşturulur; `cv2.fillPoly` ile çokgenin içi 255, dışı 0 yapılır.
4. Orijinal ve efektli görüntü maskeye göre birleştirilir:

```python
alfa = maske / 255                                  # 0 veya 1
çıktı = roi * (1 - alfa) + efektli_roi * alfa
```

Maske 0/255 değerleri taşıdığı için önce 0-1 aralığına çevrilmeli ve renkli görüntüyle çarpılabilmesi için 3 kanala genişletilmelidir. Maske yalnızca 0 veya 1 olduğundan kod bunu tek adımda, daha hızlı olan `np.where` ile yapar:

```python
roi_çıktı = np.where(maske[..., None] > 0, efektli_roi, roi)
```

### 7. Görselleştirme
Çerçevenin kenarları yeşil bir çizgiyle (`cv2.polylines`) gösterilir. El iskeleti (eklem noktaları ve aralarındaki çizgiler) görüntüyü kalabalıklaştırdığı için çizilmez. Ekranın üstünde aktif efekt ve FPS yazar.

### 8. Cımbızlama (Pinch) ile Efekt Değiştirme
Bir elde başparmak ucu ile işaret parmağı ucu birleştirilince sıradaki efekte geçilir. El modelinin zaten ürettiği noktalar kullanıldığı için ek bir model veya işlem yükü yoktur.

1. Her el için başparmak ucu (4) ile işaret parmağı ucu (8) arasındaki mesafe hesaplanır. Parmaklar kameraya dönükken uçlar görüntüde üst üste görünse bile derinlikte ayrı olabileceği için mesafe derinlik (z) dahil 3B hesaplanır
2. Mesafe el boyutuna (bilek (0) ile orta parmak kökü (9) arası) bölünür. Böylece oran, elin kameraya yakınlığından bağımsız olur:

   ```python
   oran = |başparmak_ucu - işaret_ucu| / |bilek - orta_parmak_kökü|
   ```

3. Oran eşiğin (`--pinch-threshold`, varsayılan `0.3`) altına inince el "kapalı" sayılır

Yanlışlıkla tetiklemeyi önlemek için:
- **Histerezis:** Kapanma eşiği 0.3 iken açılma eşiği bunun 1.6 katıdır (0.48). Oran eşiğin çevresinde gidip gelse bile tek bir cımbızlama birden fazla sayılmaz
- **Tutma süresi:** Parmaklar en az 0.1 saniye birleşik kalmalıdır; tek karelik tespit gürültüsü tetiklemez
- **Bekleme süresi:** Bir efekt değişiminden sonra 0.6 saniye yeni değişim yapılmaz
- **Tekrar için aç-kapa:** Parmakları birleşik tutmaya devam etmek efekti tekrar değiştirmez; önce parmaklar ayrılmalıdır
- **Yeni gelen el:** Kadraja zaten birleşik parmaklarla giren bir el tetikleme yapmaz; el sayısı değiştiğinde parmaklar bir kez açık görülene kadar beklenir

Efekt değişince yeni efektin adı ekranın üstünde kısa süre büyük harflerle görünür. Cımbızlama tek elle de çalışır; çerçeve kurulu olmasa bile efekti seçebilirsin.

---

## Kurulum

Bir sanal ortam (venv) kullanman önerilir:

**Windows (PowerShell):**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Windows notu:** `python` komutu "Python bulunamadı" hatası verip Microsoft Store'u açmaya çalışıyorsa, onun yerine Python başlatıcısını kullan: `py -m venv .venv`. Sanal ortamı etkinleştirmeden de çalıştırabilirsin: `.venv\Scripts\python.exe hand_frame_effects.py`

> **Not:** `opencv-python` paketini ayrıca kurma. MediaPipe `opencv-contrib-python` paketini zaten getirir; ikisi aynı `cv2` dosyalarını paylaştığı için birlikte kurulduklarında çakışabilirler.

İlk çalıştırmada el modeli (`hand_landmarker.task`, ~7.8 MB) proje klasörüne otomatik indirilir; bunun için bir kere internet bağlantısı gerekir.

**Gereksinimler:**
- Python 3 (Python 3.14 ile test edildi)
- Çalışan bir webcam
- `requirements.txt` içindeki paketler: MediaPipe 1.0.1, OpenCV 5.0 (contrib), NumPy 2.5

---

## Kullanım

**Windows'ta en kolay yol:** Proje klasöründeki `baslat.bat` dosyasına çift tıkla.
- İlk çalıştırmada sanal ortam (`.venv`) yoksa oluşturur ve eksik paketleri kurar
- Sonraki açılışlarda doğrudan programı başlatır
- Bir hata olursa pencere kapanmadan önce mesajı okuyabilmen için bekler

Seçenekler bat dosyasına da verilebilir:

```bash
baslat.bat --effect cartoon
```

Komut satırından doğrudan çalıştırmak için:

```bash
python hand_frame_effects.py
```

**Komut satırı seçenekleri:**

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--camera` | `0` | Kamera indeksi |
| `--width` / `--height` | `1280` / `720` | İstenen kamera çözünürlüğü |
| `--effect` | `xray` | Başlangıç efekti: `xray`, `cartoon`, `sketch`, `thermal`, `negative`, `pixel`, `sepia`, `neon`, `glitch`, `nightvision`, `emboss` |
| `--smoothing` | `0.5` | Titreme azaltma, 0-1 arası (0 = kapalı) |
| `--confidence` | `0.5` | El tespit güven eşiği, 0-1 arası |
| `--pinch-threshold` | `0.3` | Cımbızlama eşiği (parmak ucu mesafesi / el boyutu); `0` cımbızlamayı kapatır |
| `--debug` | kapalı | Her elin cımbızlama oranını parmak uçlarının yanında gösterir (eşik ayarlamak için) |

Örnek:

```bash
python hand_frame_effects.py --effect cartoon --smoothing 0.7 --width 640 --height 480
```

**Kontroller:**

| Tuş | İşlev |
|---|---|
| `n` veya **cımbızlama** | Sıradaki efekte geç (cımbızlama: bir elde başparmak ile işaret parmağı ucunu kısa süre birleştir) |
| `s` | Ekran görüntüsünü (efekt ve çerçeve dahil) `ekran_YYYYAAGG_SSDDss.png` olarak proje klasörüne kaydet |
| `q` veya `ESC` | Programdan çık (pencereyi kapatmak da çıkar) |

> Tuşların çalışması için kamera penceresinin seçili (odakta) olması gerekir.

**Kullanım adımları:**
1. Programı çalıştır, kamera penceresi açılsın
2. İki elini kameraya göster
3. Başparmak ve işaret parmağını her elde ayrı tutarak bir "çerçeve" şekli oluştur (fotoğrafçı pozu gibi)
4. Çerçevenin içindeki görüntünün efekte dönüştüğünü gözlemle
5. Bir elinde başparmak ile işaret parmağı ucunu kısa süre birleştirip ayırarak (cımbızlama) ya da `n` tuşuyla diğer efektleri dene
6. Bileklerini yerinde tutup parmak uçlarını karşı elin parmak uçlarının öbür tarafına geçir: çerçeve yatay kum saatine dönüşür

---

## Kod Yapısı

```
hand_frame_effects.py
│
├── apply_xray()                # Gri + ters çevirme + BONE renk haritası
├── apply_cartoon()             # Bilateral düzleştirme + LAB cel shading + kalın hatlar
├── apply_sketch()              # Dodge blend ile kalem eskizi
├── apply_thermal()             # JET renk haritası
├── apply_negative()            # Renk tersine çevirme
├── apply_pixel()               # Küçült + en yakın komşu ile büyüt
├── apply_sepia()               # Sepya renk matrisi
├── apply_neon()                # Gökkuşağı renkli parlayan kenarlar
├── apply_glitch()              # Kanal kayması + kayan şeritler + tarama çizgileri
├── apply_night_vision()        # Histogram eşitleme + gürültü + vinyet + yeşil ton
├── apply_emboss()              # Kabartma çekirdeği
├── EFFECT_FUNCS / EFFECTS      # İsim -> fonksiyon sözlüğü ve geçiş sırası
│
├── get_frame_points()          # 2 elden 4 parmak ucunu sabit sırayla çıkarır
├── order_quad_points()         # Noktaları dışbükey çokgene dönüştürür (convex hull)
├── hands_crossed()             # Parmak uçları iç içe geçti mi (histerezisli)
├── hourglass_polygon()         # Yatay kum saati çokgeni
├── FrameShaper                 # Dörtgen / kum saati seçimi
├── PointSmoother               # Köşelere üstel hareketli ortalama (titreme azaltma)
├── apply_effect_in_polygon()   # ROI'de efekt + maske ile birleştirme
│
├── pinch_ratio()               # Başparmak-işaret ucu mesafesi / el boyutu (3B)
├── PinchDetector               # Cımbızlamayı algılar (histerezis, tutma, bekleme)
│
├── ensure_model()              # Model dosyası yoksa indirir
├── create_landmarker()         # MediaPipe HandLandmarker (VIDEO modu)
├── open_camera()               # Kamerayı açar (Windows'ta DirectShow)
├── process_frame()             # Tek kare: tespit -> çerçeve -> efekt
├── draw_overlay()              # Çerçeve ve ekran yazıları
├── save_snapshot()             # `s` tuşu: kareyi PNG olarak kaydeder
└── main()                      # Argümanlar, kamera döngüsü, klavye kontrolleri
```

Yeni bir efekt eklemek için:
1. `def apply_yenisi(img): ...` şeklinde bir fonksiyon yaz (BGR görüntü al, aynı boyutta BGR görüntü döndür)
2. `EFFECT_FUNCS` sözlüğüne `"yenisi": apply_yenisi` olarak ekle

`EFFECTS` listesi sözlükten otomatik üretilir; `n` tuşu efektleri sözlükteki sırayla gezer.

> Efektler çerçeveyi saran küçük bir bölge (ROI) üzerinde çalışır. Yazdığın efekt birkaç piksellik çok küçük görüntülerde de hata vermemeli.

---

## Efektlerin Detaylı Açıklaması

### X-Ray
Görüntü griye çevrilir, ardından renkler ters çevrilir (`bitwise_not`). Böylece parlak bölgeler koyu, koyu bölgeler parlak olur. Son olarak `COLORMAP_BONE` renk haritası uygulanarak röntgen filmini andıran mavi-beyaz bir tonlama elde edilir.

### Karikatür (Cartoon)
Çizgi film görünümü üç adımda elde edilir:
1. **Renk düzleştirme:** Görüntü yarı çözünürlüğe küçültülür, 4 kez bilateral filtreden geçirilir ve tekrar büyütülür. Bilateral filtre kenarları koruyarak düz alanları pürüzsüzleştirir. Küçük görüntüde tekrarlamak hem daha güçlü düzleştirir hem de tam çözünürlükte tek geçişten hızlıdır
2. **Cel shading (basamaklı gölgelendirme):** Görüntü LAB renk uzayına çevrilir. Yalnızca parlaklık (L) kanalı 8 basamağa yuvarlanır, renk kanalları (a, b) ise canlandırılır. Böylece yuvarlak yüzeylerdeki yumuşak gölgeler çizgi filmlerdeki gibi keskin tonlara ayrılır. B, G, R kanallarını ayrı ayrı basamaklamak gri yüzeylerde pembe/yeşil lekeler oluşturduğu için bu yol seçilmedi. Ton sınırlarının tırtıklı çıkmaması için parlaklık, yuvarlamadan önce bulanıklaştırılır ve sonra medyan filtreyle temizlenir
3. **Dış hatlar:** Düzleştirilmiş görüntüde Canny ile kenarlar bulunur, kalınlaştırılır (`dilate`) ve siyaha boyanır

### Eskiz (Sketch)
Klasik "dodge blend" tekniği: gri görüntünün tersi alınıp bulanıklaştırılır. Ardından gri görüntü, bu bulanık tersin tersine bölünür (`gri / (255 - bulanık_ters)`). Düz alanlar beyaza döner, kenarlar koyu çizgiler olarak kalır ve kalemle çizilmiş bir taslak görünümü ortaya çıkar.

### Termal
Gri tonlamalı görüntüye `COLORMAP_JET` uygulanır: düşük parlaklık mavi, yüksek parlaklık kırmızı/sarı olur. Bu, termal kamera hissi verir (gerçek sıcaklık değil, parlaklık gösterilir).

### Negatif
Her pikselin renk değerleri 255'ten çıkarılır (`bitwise_not`). Sonuç fotoğraf negatifi görünümüdür.

### Piksel (Pixel)
Görüntü 14 kat küçültülür (`INTER_AREA` her bloğun ortalama rengini alır), ardından en yakın komşu (`INTER_NEAREST`) yöntemiyle eski boyutuna büyütülür. Sonuç, büyük kare bloklardan oluşan retro oyun görünümüdür.

### Sepya (Sepia)
Her piksele klasik sepya renk matrisi uygulanır (`cv2.transform`). Renkler kahverengi-sarı tonlara çekilir ve eski fotoğraf görünümü elde edilir.

### Neon
Canny ile kenarlar bulunur ve hafifçe kalınlaştırılır. Kenarlar soldan sağa gökkuşağı gibi değişen ve zamanla kayan renklerle boyanır. Bulanıklaştırılmış bir kopyası üstüne eklenerek parlama (glow) etkisi verilir. Kenar olmayan her yer siyahtır.

### Glitch
Bozuk dijital sinyal görünümü üç katmandan oluşur: kırmızı ve mavi kanallar zıt yönlere birkaç piksel kaydırılır (renk ayrışması), rastgele yatay şeritler yana kaydırılır ve her 3 satırdan biri karartılarak tarama çizgileri eklenir. Rastgelelik her karede değiştiği için görüntü sürekli titrer.

### Gece Görüşü (Night Vision)
Gri görüntünün histogramı eşitlenerek (`equalizeHist`) karanlık bölgeler aydınlatılır. Üstüne sensör gürültüsü eklenir, kenarlara doğru kararan bir vinyet uygulanır ve görüntü yeşile boyanır.

### Kabartma (Emboss)
Gri görüntüye çapraz yönlü bir kabartma çekirdeği (`filter2D`) uygulanır. Kenarlar, ışık bir köşeden geliyormuş gibi açık ve koyu çizgilere dönüşür; görüntü metal üzerine basılmış gibi görünür.

---

## Bilinen Sınırlamalar

- **Işık koşulları**: El tespiti düşük ışıkta veya eller kısmen kamera dışına çıktığında kararsızlaşabilir
- **Gecikme / stabilite dengesi**: Yumuşatma titremeyi azaltır ama hızlı el hareketlerinde çerçeve eli biraz geriden takip eder (`--smoothing` ile ayarlanır)
- **Performans**: Efekt yalnızca çerçeveyi saran bölgede hesaplanır, ancak çerçeve ekranın büyük kısmını kapladığında `cartoon` efekti (bilateral filtre) düşük güçlü bilgisayarlarda FPS düşüşüne yol açabilir
- **Tek çerçeve mantığı**: Çerçeve yalnızca tam olarak 2 el görünüyorsa oluşur; tek elle çerçeve desteklenmiyor
- **Keskin kenar**: Çerçeve kenarında efekt ile orijinal görüntü arasında yumuşak geçiş yoktur
- **Cımbızlama anında çerçeve**: Parmaklar birleşince o elin iki köşesi üst üste gelir, çerçeve bir anlığına üçgene döner
- **Cımbızlama yanlış algılaması**: Parmaklar kameraya dönükken derinlik (z) tahmini hatalıysa, ayrı duran parmak uçları birleşik sanılabilir
- **Kum saati hareketi**: Eller bileklerin konumuna göre ayırt edildiği için kum saati, bilekler yerinde kalıp parmak uçları iç içe geçince oluşur. Kolları tamamen çaprazlayıp bilekleri de yer değiştirmek çerçeveyi yine dörtgen yapar

---

## Genişletme Fikirleri

1. **Yönlü cımbızlama**: Soldaki elle cımbızlama önceki, sağdaki elle sonraki efekte geçsin
2. **Daha iyi takip**: Hareketli ortalama yerine Kalman filtresi veya One Euro filtresi kullanarak hem stabil hem de gecikmesi az bir çerçeve elde etme
3. **Yumuşak kenar**: Maskeyi `GaussianBlur` ile bulanıklaştırıp 0-1 arası ondalıklı alfa ile birleştirerek çerçeve kenarında yumuşak geçiş
4. **Yeni efektler**: ASCII dönüşümü, görünmezlik pelerini (önceden kaydedilen boş arka planı çerçevenin içinde gösterme), kendi yazdığın bir konvolüsyon filtresi
5. **Başka jestler**: Yumruk yapma gibi el hareketleri (MediaPipe `GestureRecognizer`) veya bilinçli uzun göz kırpma (MediaPipe `FaceLandmarker` göz kırpma skorları) ile efekti açıp kapatma gibi ek kontroller
6. **Kayıt özelliği**: `cv2.VideoWriter` ile çıktıyı video olarak kaydetme
7. **Çoklu çerçeve**: `num_hands` değerini 4'e çıkarıp elleri yakınlığa göre eşleştirerek aynı anda birden fazla efekt bölgesi oluşturma

---

## Sorun Giderme

| Sorun | Olası Neden | Çözüm |
|---|---|---|
| "Kamera açılamadı" hatası | Kamera başka bir uygulama tarafından kullanılıyor veya indeks yanlış | Diğer kamera uygulamalarını kapat; `--camera 1`, `--camera 2` deneyerek doğru cihazı bul |
| `module 'mediapipe' has no attribute 'solutions'` | İnternetteki eski bir örnek kodu yeni MediaPipe ile çalıştırıyorsun | Bu projedeki kod yeni Tasks API'yi kullanır; `requirements.txt` ile kurulum yap |
| Model indirilemiyor | İnternet yok veya ağ engelliyor | `hand_landmarker.task` dosyasını [resmi adresten](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task) indirip `hand_frame_effects.py` ile aynı klasöre koy |
| `cv2` ile ilgili garip import hataları | `opencv-python` ve `opencv-contrib-python` birlikte kurulu | İkisini de kaldırıp yalnızca `pip install -r requirements.txt` ile yeniden kur |
| El tespit edilmiyor | Düşük ışık veya eller kadraj dışında | Daha aydınlık bir ortamda dene, elleri kameraya daha yakın tut; gerekirse `--confidence 0.3` |
| Yanlış el / hayalet el tespiti | Güven eşiği düşük | `--confidence 0.7` gibi daha yüksek bir değer dene |
| Çerçeve titriyor | Parmak ucu tespitindeki doğal gürültü | `--smoothing 0.7` gibi daha yüksek bir değer dene |
| Çerçeve eli geriden takip ediyor | Yumuşatma çok yüksek | `--smoothing` değerini düşür (örn. `0.3`) |
| Efekt kendiliğinden değişiyor | Eller kadraja girip çıkarken veya parmaklar kameraya dönükken cımbızlama sanılıyor | `--debug` ile oranlara bak ve `--pinch-threshold 0.2` gibi daha düşük bir eşik dene; gerekirse `--pinch-threshold 0` ile kapat |
| Kum saati oluşmuyor | Parmak uçları yeterince iç içe geçmemiş ya da kollar tamamen çaprazlanıp bilekler de yer değiştirmiş | Bileklerini yerinde tutup parmak uçlarını karşı elin parmak uçlarının belirgin şekilde öbür tarafına geçir |
| Cımbızlama algılanmıyor | Parmak uçları birleşikken oran eşiğin üstünde kalıyor | `--debug` ile parmaklar birleşikken görünen oranı oku, eşiği bunun biraz üstüne ayarla (örn. `--pinch-threshold 0.4`) |
| Düşük FPS | Cartoon efekti, yüksek çözünürlük veya düşük donanım | `--width 640 --height 480` ile çözünürlüğü düşür |

---

## Dosyalar

- `hand_frame_effects.py` — Ana çalıştırılabilir betik
- `baslat.bat` — Windows başlatıcısı: çift tıklayınca çalışır, gerekirse sanal ortamı ve paketleri kurar
- `requirements.txt` — Sabitlenmiş paket sürümleri
- `hand_landmarker.task` — MediaPipe el modeli (ilk çalıştırmada otomatik indirilir)
- `ekran_*.png` — `s` tuşuyla kaydedilen ekran görüntüleri
