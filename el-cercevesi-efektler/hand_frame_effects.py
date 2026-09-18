"""
El Çerçevesi ile Görüntü Efektleri

İki elin başparmak ve işaret parmağı uçlarıyla oluşturulan çerçevenin
içindeki kamera görüntüsüne gerçek zamanlı efekt uygular. Eller iç içe
geçince çerçeve dörtgenden yatay kum saatine dönüşür.

Kullanım:
    python hand_frame_effects.py [--camera 0] [--effect xray] [--smoothing 0.5]

Kontroller:
    n / cımbızlama  sıradaki efekt (bir elde başparmak ile işaret ucunu birleştir)
    s               ekran görüntüsünü kaydet
    q / ESC         çıkış
"""

import argparse
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().with_name("hand_landmarker.task")

WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_MCP = 9

WINDOW_NAME = "El Cercevesi Efektleri"
MIN_POLYGON_AREA = 400  # piksel^2; parmaklar üst üsteyken çerçeve oluşturma
CROSS_MARGIN = 0.03  # kare genişliğine oranla; dörtgen/kum saati geçişinde titremeyi önler
FRAME_COLOR = (0, 255, 0)
BANNER_SECONDS = 0.8  # efekt değişince adının ekranda kalma süresi


# ---------------------------------------------------------------------------
# Efektler: her fonksiyon BGR bir görüntü alır, aynı boyutta BGR döndürür.
# ---------------------------------------------------------------------------

def apply_xray(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.applyColorMap(cv2.bitwise_not(gray), cv2.COLORMAP_BONE)


def make_lut(fn):
    """0-255 her değer için fn(değer) sonucunu tutan cv2.LUT tablosu üretir."""
    return np.clip([fn(i) for i in range(256)], 0, 255).astype(np.uint8)


CARTOON_LIGHTNESS_LUT = make_lut(lambda i: i // 32 * 32 + 16)     # 8 parlaklık basamağı
CARTOON_CHROMA_LUT = make_lut(lambda i: (i - 128) * 1.35 + 128)  # renkleri canlandır


def apply_cartoon(img):
    height, width = img.shape[:2]

    # 1) Renkleri düzleştir: yarı çözünürlükte tekrarlı bilateral filtre hem
    #    daha güçlü düzleştirir hem de tam çözünürlükte tek geçişten hızlıdır.
    small = cv2.resize(
        img, (max(1, width // 2), max(1, height // 2)), interpolation=cv2.INTER_AREA
    )
    for _ in range(4):
        small = cv2.bilateralFilter(small, 7, 40, 7)
    smooth = cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)

    # 2) Cel shading: LAB'de yalnızca parlaklık basamaklara ayrılır. B, G, R
    #    kanallarını ayrı ayrı basamaklamak gri yüzeylerde renk lekeleri yapar.
    #    Önce bulanıklaştırma ve sonra medyan, basamak sınırlarını pürüzsüzleştirir.
    lightness, a, b = cv2.split(cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB))
    lightness = cv2.GaussianBlur(lightness, (0, 0), 2)
    lightness = cv2.medianBlur(cv2.LUT(lightness, CARTOON_LIGHTNESS_LUT), 5)
    lab = cv2.merge([lightness, cv2.LUT(a, CARTOON_CHROMA_LUT), cv2.LUT(b, CARTOON_CHROMA_LUT)])
    color = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # 3) Kalın siyah dış hatlar
    gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
    outlines = cv2.dilate(cv2.Canny(gray, 30, 90), np.ones((3, 3), np.uint8))
    color[outlines > 0] = 0
    return color


def apply_sketch(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred_inv = cv2.GaussianBlur(cv2.bitwise_not(gray), (21, 21), 0)
    # Dodge blend: gri / (255 - bulanık_ters)
    sketch = cv2.divide(gray, cv2.bitwise_not(blurred_inv), scale=256)
    return cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)


def apply_thermal(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.applyColorMap(gray, cv2.COLORMAP_JET)


def apply_negative(img):
    return cv2.bitwise_not(img)


PIXEL_SIZE = 14


def apply_pixel(img):
    height, width = img.shape[:2]
    small = cv2.resize(
        img, (max(1, width // PIXEL_SIZE), max(1, height // PIXEL_SIZE)),
        interpolation=cv2.INTER_AREA,
    )
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_NEAREST)


# BGR girişten BGR çıkışa klasik sepya matrisi (satırlar: B', G', R').
SEPIA_MATRIX = np.array([
    [0.131, 0.534, 0.272],
    [0.168, 0.686, 0.349],
    [0.189, 0.769, 0.393],
])


def apply_sepia(img):
    return cv2.transform(img, SEPIA_MATRIX)


def apply_neon(img):
    height, width = img.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 40, 110), np.ones((2, 2), np.uint8))

    # Renk tonu soldan sağa gökkuşağı gibi değişir ve zamanla kayar.
    hue = (np.arange(width) * 180 / width + time.monotonic() * 60) % 180
    hsv = np.empty((height, width, 3), dtype=np.uint8)
    hsv[..., 0] = hue.astype(np.uint8)
    hsv[..., 1] = 255
    hsv[..., 2] = edges
    lines = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    glow = cv2.GaussianBlur(lines, (0, 0), 5)
    return cv2.add(lines, cv2.convertScaleAbs(glow, alpha=2.0))


RNG = np.random.default_rng()


def apply_glitch(img):
    height, width = img.shape[:2]
    out = img.copy()

    # Renk ayrışması: kırmızı ve mavi kanallar zıt yönlere kayar.
    shift = max(1, width // 60)
    out[..., 2] = np.roll(img[..., 2], shift, axis=1)
    out[..., 0] = np.roll(img[..., 0], -shift, axis=1)

    # Rastgele yatay şeritler yana kayar.
    for _ in range(RNG.integers(3, 7)):
        y = RNG.integers(0, height)
        band = RNG.integers(1, max(2, height // 12))
        dx = RNG.integers(-(width // 8), width // 8 + 1)
        out[y:y + band] = np.roll(out[y:y + band], dx, axis=1)

    # Tarama çizgileri: her 3 satırdan biri karartılır.
    out[::3] = out[::3] // 4 * 3
    return out


def apply_night_vision(img):
    height, width = img.shape[:2]
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)).astype(np.float32)
    gray += RNG.standard_normal(gray.shape, dtype=np.float32) * 12  # sensör gürültüsü

    # Kenarlara doğru kararan vinyet
    vignette = cv2.getGaussianKernel(height, height * 0.55) @ cv2.getGaussianKernel(width, width * 0.55).T
    gray = np.clip(gray * (vignette / vignette.max()), 0, 255)
    return cv2.merge([gray * 0.25, gray, gray * 0.35]).astype(np.uint8)


EMBOSS_KERNEL = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32)


def apply_emboss(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(cv2.filter2D(gray, -1, EMBOSS_KERNEL), cv2.COLOR_GRAY2BGR)


# Sıra, `n` tuşu ve cımbızlama ile geçiş sırasını belirler.
EFFECT_FUNCS = {
    "xray": apply_xray,
    "cartoon": apply_cartoon,
    "sketch": apply_sketch,
    "thermal": apply_thermal,
    "negative": apply_negative,
    "pixel": apply_pixel,
    "sepia": apply_sepia,
    "neon": apply_neon,
    "glitch": apply_glitch,
    "nightvision": apply_night_vision,
    "emboss": apply_emboss,
}
EFFECTS = list(EFFECT_FUNCS)


# ---------------------------------------------------------------------------
# Geometri
# ---------------------------------------------------------------------------

def get_frame_points(result, width, height):
    """Tam olarak iki el görünüyorsa 4 parmak ucunu (4, 2) dizisi olarak döndürür.

    Eller bilek x koordinatına göre soldan sağa sıralanır. MediaPipe ellerin
    listedeki sırasını kareden kareye değiştirebildiği için bu sıralama,
    yumuşatmanın her köşeyi yine kendisiyle eşleştirmesini sağlar.
    """
    hands = result.hand_landmarks
    if len(hands) != 2:
        return None
    hands = sorted(hands, key=lambda landmarks: landmarks[WRIST].x)
    points = [
        (landmarks[i].x * width, landmarks[i].y * height)
        for landmarks in hands
        for i in (THUMB_TIP, INDEX_TIP)
    ]
    return np.array(points, dtype=np.float32)


def order_quad_points(points):
    """Noktaları geçerli, dışbükey bir çokgen sırasına dizer.

    Merkeze göre açıyla sıralamak kendini kesmeyi önler ama bir nokta diğer
    üçünün oluşturduğu üçgenin içindeyse içbükey bir şekil çıkar. Dışbükey
    zarf (convex hull) her durumda dışbükey ve sıralı bir çokgen verir
    (3 veya 4 köşe). Alan çok küçükse None döner.
    """
    hull = cv2.convexHull(np.round(points).astype(np.int32))
    if len(hull) < 3 or cv2.contourArea(hull) < MIN_POLYGON_AREA:
        return None
    return hull.reshape(-1, 2)


def hands_crossed(points, was_crossed, margin):
    """Parmak uçlarının çapraz geçip geçmediğini (ellerin iç içe olduğunu) bulur.

    points get_frame_points sırasındadır: ilk iki nokta bileği solda olan elin,
    son ikisi bileği sağda olan elin parmak uçları. Bilekler yerinde dururken
    soldaki elin parmak uçları sağdaki elinkilerin sağına geçmişse eller iç
    içe geçmiştir. Uçlar hizadayken şeklin gidip gelmemesi için durum ancak
    yatay fark `margin` pikseli aşınca değişir.
    """
    gap = points[:2, 0].mean() - points[2:, 0].mean()
    if gap > margin:
        return True
    if gap < -margin:
        return False
    return was_crossed


def hourglass_polygon(points):
    """4 noktadan yatay kum saati çokgeni üretir.

    Ekranda soldaki elin iki ucu sol kenarı, sağdaki elin iki ucu sağ kenarı
    oluşturur. Üst ve alt kenarlar yerine köşegenler çizilir ve ortada kesişir:
    sol-üst -> sol-alt -> sağ-üst -> sağ-alt. cv2.fillPoly kendini kesen bu
    çokgenin iki üçgenini de doldurur. Alan çok küçükse None döner.
    """
    left, right = sorted((points[:2], points[2:]), key=lambda pair: pair[:, 0].mean())
    left_top, left_bottom = sorted(left, key=lambda point: point[1])
    right_top, right_bottom = sorted(right, key=lambda point: point[1])

    # Kenar yükseklikleri h1, h2 ve kenarlar arası genişlik w için iki üçgenin
    # toplam alanı w * (h1² + h2²) / (2 * (h1 + h2)) olur.
    h1 = left_bottom[1] - left_top[1]
    h2 = right_bottom[1] - right_top[1]
    w = right[:, 0].mean() - left[:, 0].mean()
    if h1 + h2 <= 0 or w * (h1 ** 2 + h2 ** 2) / (2 * (h1 + h2)) < MIN_POLYGON_AREA:
        return None
    return np.round([left_top, left_bottom, right_top, right_bottom]).astype(np.int32)


class FrameShaper:
    """Parmak uçlarından çerçeve çokgenini üretir.

    Normalde dışbükey dörtgen, eller iç içe geçince yatay kum saati.
    """

    def __init__(self, margin_ratio=CROSS_MARGIN):
        self.margin_ratio = margin_ratio
        self.crossed = False

    def update(self, points, frame_width):
        if points is None:
            self.crossed = False
            return None
        self.crossed = hands_crossed(points, self.crossed, self.margin_ratio * frame_width)
        return hourglass_polygon(points) if self.crossed else order_quad_points(points)


class PointSmoother:
    """Köşe noktalarına üstel hareketli ortalama uygulayarak titremeyi azaltır.

    alpha = 0 yumuşatma yok; 1'e yaklaştıkça çerçeve daha stabil ama
    el hareketini daha geç takip eder.
    """

    def __init__(self, alpha=0.5):
        self.alpha = alpha
        self.state = None

    def update(self, points):
        if points is None:
            self.state = None
        elif self.state is None:
            self.state = points.copy()
        else:
            self.state = self.alpha * self.state + (1 - self.alpha) * points
        return self.state


def apply_effect_in_polygon(frame, polygon, effect):
    """Efekti yalnızca çokgenin içine uygular; dışı değişmeden kalır.

    Efekt tüm kare yerine sadece çokgeni saran dikdörtgende (ROI) hesaplanır,
    böylece çerçeve küçükken işlem yükü de küçük olur. Kare yerinde değiştirilir.
    """
    frame_h, frame_w = frame.shape[:2]
    x, y, w, h = cv2.boundingRect(polygon)
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, frame_w), min(y + h, frame_h)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return frame

    roi = frame[y0:y1, x0:x1]
    mask = np.zeros(roi.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [polygon - (x0, y0)], 255)

    # output = roi * (1 - alfa) + efekt * alfa, alfa = mask / 255 ∈ {0, 1}
    frame[y0:y1, x0:x1] = np.where(mask[..., None] > 0, effect(roi), roi)
    return frame


# ---------------------------------------------------------------------------
# Cımbızlama (pinch) hareketi
# ---------------------------------------------------------------------------

def pinch_ratio(landmarks, width, height):
    """Başparmak ucu ile işaret parmağı ucu arasındaki mesafenin el boyutuna oranı.

    El boyutu olarak bilek ile orta parmak kökü arası kullanılır; böylece oran
    elin kameraya yakınlığından bağımsızdır. Mesafeler derinlik (z) dahil 3B
    hesaplanır: parmaklar kameraya dönükken uçlar görüntüde üst üste görünse
    bile derinlikte ayrı olabilir. MediaPipe z'yi x ile yaklaşık aynı ölçekte
    verdiği için genişlikle çarpılır.
    """
    def point(index):
        landmark = landmarks[index]
        return np.array([landmark.x * width, landmark.y * height, landmark.z * width])

    hand_size = np.linalg.norm(point(WRIST) - point(MIDDLE_MCP))
    tip_distance = np.linalg.norm(point(THUMB_TIP) - point(INDEX_TIP))
    return float(tip_distance / max(hand_size, 1e-6))


class PinchDetector:
    """Herhangi bir elde başparmak ile işaret ucunun birleşmesini algılar.

    Yanlışlıkla tetiklemeyi önlemek için:
      - histerezis: kapanma eşiği close_ratio, açılma eşiği onun 1.6 katı;
        oran eşik çevresinde gidip gelse de tek cımbızlama bir kez sayılır,
      - tutma süresi: parmaklar en az `hold` saniye birleşik kalmalı,
      - bekleme süresi: tetiklemeden sonra `cooldown` saniye yeni tetikleme yok,
      - kurma (armed): tetiklemeden sonra ve el sayısı değiştiğinde, parmaklar
        bir kez açık görülene kadar tetikleme yapılmaz. Böylece birleşik tutmaya
        devam etmek ya da kadraja zaten kapalı parmakla giren el efekti değiştirmez.
    """

    OPEN_FACTOR = 1.6

    def __init__(self, close_ratio=0.3, hold=0.1, cooldown=0.6):
        self.close_ratio = close_ratio
        self.open_ratio = close_ratio * self.OPEN_FACTOR
        self.hold = hold
        self.cooldown = cooldown
        self.ratios = []
        self.closed = False
        self.closed_since = 0.0
        self.armed = False
        self.hand_count = 0
        self.last_trigger = float("-inf")

    def update(self, hand_landmarks, width, height, now):
        """Yeni bir cımbızlama algılandıysa True döndürür. `now` saniye cinsindendir."""
        self.ratios = [pinch_ratio(landmarks, width, height) for landmarks in hand_landmarks]

        if len(self.ratios) != self.hand_count:
            self.hand_count = len(self.ratios)
            self.armed = False

        threshold = self.open_ratio if self.closed else self.close_ratio
        if not any(ratio < threshold for ratio in self.ratios):
            self.closed = False
            self.armed = bool(self.ratios)
            return False

        if not self.closed:
            self.closed = True
            self.closed_since = now

        if (
            self.armed
            and now - self.closed_since >= self.hold
            and now - self.last_trigger >= self.cooldown
        ):
            self.armed = False
            self.last_trigger = now
            return True
        return False


# ---------------------------------------------------------------------------
# MediaPipe ve kamera
# ---------------------------------------------------------------------------

def ensure_model(path=MODEL_PATH):
    """El modeli yoksa resmi MediaPipe deposundan indirir."""
    if not path.exists():
        print(f"El modeli indiriliyor: {MODEL_URL}")
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(MODEL_URL, partial)
        partial.replace(path)
    return path


def create_landmarker(model_path, confidence):
    # Model yol yerine bayt olarak verilir: MediaPipe Windows'ta Türkçe
    # karakter içeren klasör yollarını açamayabiliyor.
    options = vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_buffer=model_path.read_bytes()),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=confidence,
        min_hand_presence_confidence=confidence,
        min_tracking_confidence=confidence,
    )
    return vision.HandLandmarker.create_from_options(options)


def open_camera(index, width, height):
    # Windows'ta DirectShow genellikle çok daha hızlı açılır.
    if sys.platform == "win32":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(index)
    else:
        cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def process_frame(frame, landmarker, timestamp_ms, effect_name, smoother, shaper):
    """Bir kareyi işler: el tespiti, çerçeve çıkarımı ve efekt uygulama."""
    height, width = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect_for_video(image, timestamp_ms)

    points = smoother.update(get_frame_points(result, width, height))
    polygon = shaper.update(points, width)
    if polygon is not None:
        apply_effect_in_polygon(frame, polygon, EFFECT_FUNCS[effect_name])
    return frame, result, polygon


def put_text(img, text, org, scale=0.7, thickness=2):
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, text, org, font, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(img, text, org, font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def draw_overlay(frame, result, polygon, effect_name, fps, banner=None, pinch_ratios=None):
    height, width = frame.shape[:2]
    if polygon is not None:
        cv2.polylines(frame, [polygon], True, FRAME_COLOR, 2, cv2.LINE_AA)

    # --debug: her elin cımbızlama oranı, parmak uçlarının ortasında.
    if pinch_ratios:
        for landmarks, ratio in zip(result.hand_landmarks, pinch_ratios):
            x = int((landmarks[THUMB_TIP].x + landmarks[INDEX_TIP].x) / 2 * width)
            y = int((landmarks[THUMB_TIP].y + landmarks[INDEX_TIP].y) / 2 * height)
            put_text(frame, f"{ratio:.2f}", (x + 10, y), 0.6)

    # cv2.putText Türkçe karakter çizemediği için ekran yazıları ASCII.
    put_text(frame, f"Efekt: {effect_name}   FPS: {fps:.0f}", (10, 30))
    if polygon is None:
        put_text(frame, "Iki elinizle bir cerceve olusturun", (10, 60), 0.6)
    if banner:
        scale, thickness = 1.5, 3
        (text_w, _), _ = cv2.getTextSize(banner, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        put_text(frame, banner, ((width - text_w) // 2, 110), scale, thickness)
    put_text(
        frame, "n / cimbizla: sonraki efekt   s: kaydet   q: cikis", (10, height - 15), 0.6
    )


def save_snapshot(frame):
    """Kareyi PNG olarak proje klasörüne kaydeder; başarısızsa None döner.

    cv2.imwrite Windows'ta Türkçe karakter içeren yollara sessizce yazamadığı
    için görüntü önce bellekte PNG'ye kodlanır, dosyaya Python ile yazılır.
    """
    path = Path(__file__).resolve().with_name(time.strftime("ekran_%Y%m%d_%H%M%S.png"))
    ok, buffer = cv2.imencode(".png", frame)
    if not ok:
        return None
    path.write_bytes(buffer.tobytes())
    return path


def parse_args():
    parser = argparse.ArgumentParser(description="El çerçevesi ile görüntü efektleri")
    parser.add_argument("--camera", type=int, default=0, help="kamera indeksi (varsayılan: 0)")
    parser.add_argument("--width", type=int, default=1280, help="kamera genişliği")
    parser.add_argument("--height", type=int, default=720, help="kamera yüksekliği")
    parser.add_argument("--effect", choices=EFFECTS, default=EFFECTS[0], help="başlangıç efekti")
    parser.add_argument(
        "--smoothing", type=float, default=0.5,
        help="titreme azaltma, 0-1 arası (0 = kapalı, varsayılan: 0.5)",
    )
    parser.add_argument(
        "--confidence", type=float, default=0.5,
        help="el tespit güven eşiği, 0-1 arası (varsayılan: 0.5)",
    )
    parser.add_argument(
        "--pinch-threshold", type=float, default=0.3,
        help="cımbızlama eşiği: parmak ucu mesafesi / el boyutu (0 = kapalı, varsayılan: 0.3)",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="her elin cımbızlama oranını ekranda göster (eşik ayarlamak için)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    cap = open_camera(args.camera, args.width, args.height)
    if not cap.isOpened():
        print(
            f"Kamera açılamadı (indeks {args.camera}). Başka bir uygulama kamerayı "
            "kullanıyor olabilir; --camera 1 gibi farklı bir indeks deneyin.",
            file=sys.stderr,
        )
        return 1

    effect_index = EFFECTS.index(args.effect)
    smoother = PointSmoother(args.smoothing)
    shaper = FrameShaper()
    pinch = PinchDetector(args.pinch_threshold) if args.pinch_threshold > 0 else None
    last_timestamp = -1
    last_time = time.perf_counter()
    fps = 0.0
    banner_until = 0.0

    try:
        with create_landmarker(ensure_model(), args.confidence) as landmarker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("Kameradan görüntü okunamadı.", file=sys.stderr)
                    break

                # Ayna görüntüsü: elini sağa götürdüğünde çerçeve de sağa gider.
                frame = cv2.flip(frame, 1)

                # VIDEO modu kesin artan zaman damgası ister.
                timestamp = max(int(time.monotonic() * 1000), last_timestamp + 1)
                last_timestamp = timestamp

                frame, result, polygon = process_frame(
                    frame, landmarker, timestamp, EFFECTS[effect_index], smoother, shaper
                )

                now = time.perf_counter()
                instant_fps = 1.0 / max(now - last_time, 1e-6)
                fps = instant_fps if fps == 0 else 0.9 * fps + 0.1 * instant_fps
                last_time = now

                height, width = frame.shape[:2]
                if pinch is not None and pinch.update(result.hand_landmarks, width, height, now):
                    effect_index = (effect_index + 1) % len(EFFECTS)
                    banner_until = now + BANNER_SECONDS

                effect_name = EFFECTS[effect_index]
                draw_overlay(
                    frame, result, polygon, effect_name, fps,
                    banner=effect_name.upper() if now < banner_until else None,
                    pinch_ratios=pinch.ratios if args.debug and pinch is not None else None,
                )
                cv2.imshow(WINDOW_NAME, frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("n"):
                    effect_index = (effect_index + 1) % len(EFFECTS)
                    banner_until = time.perf_counter() + BANNER_SECONDS
                if key == ord("s"):
                    snapshot = save_snapshot(frame)
                    print(f"Ekran görüntüsü kaydedildi: {snapshot}" if snapshot
                          else "Ekran görüntüsü kaydedilemedi.")
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
