"""Detector: kamerada senden baska biri gorunurse videoyu Detector penceresinin solunda oynatir.

Kullanim:
    python detector.py          # normal calisma (ilk acilista yuz kaydi yapar)
    python detector.py --kayit  # yuz kaydini bastan yap

Kamera penceresindeyken:  q = cikis,  r = yuzunu yeniden kaydet
"""
import ctypes
import os
import subprocess
import sys
import threading
import time

from ctypes import wintypes

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

BASE = os.path.dirname(os.path.abspath(__file__))
# Oynatilacak video bu klasorde bu adla durmali (ffmpeg Turkce karakterli dosya adlarini acamayabiliyor)
VIDEO = os.path.join(BASE, "kolpacino.mov")
FFPLAY = os.path.join(BASE, "bin", "ffplay.exe")
LANDMARKER_MODEL = os.path.join(BASE, "models", "face_landmarker.task")
SFACE_MODEL = os.path.join(BASE, "models", "face_recognition_sface_2021dec.onnx")
FACE_DB = os.path.join(BASE, "benim_yuzum.npy")
LOG_FILE = os.path.join(BASE, "dedektor_log.txt")

# SFace kosinus benzerligi: ustu = sen. Ayni kisi genelde 0.6 ustu, farkli kisiler 0.4 alti cikar
MATCH_THRESHOLD = 0.5
TRIGGER_FRAMES = 2       # yabanci yuz bu kadar karede gorulunce video oynar (tek karelik hatayi eler)
COOLDOWN_SEC = 3         # video bittikten sonra bekleme
PLAY_DELAY_SEC = 2       # yabanci tespit edildikten sonra video bu kadar bekleyip ekranda olur
FFPLAY_STARTUP_SEC = 0.45  # olculen ffplay pencere acilma suresi; bekleme suresinden dusulur
ENROLL_SAMPLES = 15
VIDEO_WIDTH = 760        # video penceresi genisligi (yukseklik orana gore)
VIDEO_GAP = 12           # video ile Detector penceresi arasindaki bosluk
VIDEO_SHIFT_LEFT = 16    # videoyu bu kadar daha sola kaydirir (ekran kenarini gecmez)
MIN_VIDEO_WIDTH = 320    # solda yer azsa video en fazla bu kadar kuculur
SCREEN_MARGIN = 20       # pencerelerin ekran kenarina uzakligi
VIDEO_LEFT, VIDEO_TOP = 80, 80  # Detector penceresi bulunamazsa kullanilan konum
MAIN_WIN = "Detector"
VIDEO_WIN = "Kolpacino"

# Sadece yuz kaydinda "kameraya bakiyor mu" kontrolu icin
YAW_RANGE = (0.12, 0.88)
PITCH_RANGE = (0.05, 1.05)

# MediaPipe yuz agi indeksleri (goruntude soldaki goz = kisinin sag gozu)
EYE_A = (33, 133)
EYE_B = (362, 263)
NOSE = 1
MOUTH_A, MOUTH_B = 61, 291

user32 = ctypes.windll.user32
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]


def window_closed(name):
    try:
        return cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) < 1
    except cv2.error:
        return True


class Log:
    """Ayar yapmak icin her yuzun benzerlik/bakis degerlerini dosyaya yazar."""

    def __init__(self):
        self.f = open(LOG_FILE, "w", encoding="utf-8")
        self.last = 0.0
        self.lock = threading.Lock()

    def faces(self, faces, scores, streak):
        now = time.monotonic()
        if now - self.last < 0.3:
            return
        self.last = now
        parts = [f"benzerlik={s:.2f} yaw={f['yaw']:.2f} pitch={f['pitch']:.2f}" for f, s in zip(faces, scores)]
        self.write(f"yuz={len(faces)} seri={streak} | " + " | ".join(parts))

    def write(self, text):
        with self.lock:
            self.f.write(time.strftime("%H:%M:%S ") + text + "\n")
            self.f.flush()

    def close(self):
        self.f.close()


class FaceAnalyzer:
    def __init__(self):
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=LANDMARKER_MODEL),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=4,
            min_face_detection_confidence=0.4,
            min_face_presence_confidence=0.4,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self.recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL, "")
        self.t0 = time.monotonic()
        self.last_ts = -1

    def analyze(self, frame):
        """Her yuz icin kutu, bakis ve oznitelik bilgisi dondurur."""
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ts = max(int((time.monotonic() - self.t0) * 1000), self.last_ts + 1)
        self.last_ts = ts
        result = self.landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
        faces = []
        for lms in result.face_landmarks:
            pts = np.array([(p.x * w, p.y * h) for p in lms], dtype=np.float32)
            x0, y0 = pts.min(axis=0)
            x1, y1 = pts.max(axis=0)
            eye_a = pts[list(EYE_A)].mean(axis=0)
            eye_b = pts[list(EYE_B)].mean(axis=0)
            nose, mouth_a, mouth_b = pts[NOSE], pts[MOUTH_A], pts[MOUTH_B]

            # Kameraya bakiyor mu: burun iki gozun arasinda ve goz-agiz arasinda olmali
            eye_dx = eye_b[0] - eye_a[0]
            yaw = (nose[0] - eye_a[0]) / eye_dx if eye_dx > 1 else -1
            eye_y = (eye_a[1] + eye_b[1]) / 2
            mouth_y = (mouth_a[1] + mouth_b[1]) / 2
            pitch = (nose[1] - eye_y) / (mouth_y - eye_y) if mouth_y - eye_y > 1 else -1
            looking = bool(YAW_RANGE[0] < yaw < YAW_RANGE[1] and PITCH_RANGE[0] < pitch < PITCH_RANGE[1])

            # SFace hizalamasi icin YuNet formatinda yuz satiri
            row = np.array([[x0, y0, x1 - x0, y1 - y0, *eye_a, *eye_b, *nose, *mouth_a, *mouth_b, 1.0]],
                           dtype=np.float32)
            aligned = self.recognizer.alignCrop(frame, row)
            feature = self.recognizer.feature(aligned).copy()
            faces.append({"box": (int(x0), int(y0), int(x1), int(y1)), "looking": looking,
                          "yaw": float(yaw), "pitch": float(pitch), "feature": feature})
        return faces

    def similarity(self, feature, my_features):
        """Kayitli orneklerle en yuksek 3 benzerligin ortalamasi (tek sansli eslesmeyi onler)."""
        scores = sorted((self.recognizer.match(feature, ref.reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE)
                         for ref in my_features), reverse=True)
        return float(np.mean(scores[:3]))

    def close(self):
        self.landmarker.close()


def put_text(img, text, org, scale=0.6, color=(255, 255, 255)):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def mirrored(frame, faces, colors, labels=None):
    """Goruntuyu ayna gibi cevirip kutulari cizer (analiz ters cevrilmemis kare uzerinde yapilir)."""
    w = frame.shape[1]
    view = cv2.flip(frame, 1)
    for i, (face, color) in enumerate(zip(faces, colors)):
        x0, y0, x1, y1 = face["box"]
        cv2.rectangle(view, (w - x1, y0), (w - x0, y1), color, 2)
        if labels and labels[i]:
            cv2.putText(view, labels[i], (w - x1, max(y0 - 14, 28)), cv2.FONT_HERSHEY_SIMPLEX, 0.95, color, 2,
                        cv2.LINE_AA)
    return view


def enroll(cap, analyzer):
    """Kullanicinin yuzunden ornekler alip kaydeder. Iptal edilirse None doner."""
    samples, started, last = [], False, 0.0
    while len(samples) < ENROLL_SAMPLES:
        ok, frame = cap.read()
        if not ok:
            return None
        faces = analyzer.analyze(frame)
        view = mirrored(frame, faces, [(0, 255, 255)] * len(faces))
        if not started:
            put_text(view, "Yuz kaydi: sadece sen ol, kameraya bak, SPACE", (10, 25))
        else:
            put_text(view, f"{len(samples)}/{ENROLL_SAMPLES}", (10, 25), color=(0, 255, 255))
            if len(faces) == 1 and faces[0]["looking"] and time.monotonic() - last > 0.25:
                samples.append(faces[0]["feature"].flatten())
                last = time.monotonic()
        cv2.imshow(MAIN_WIN, view)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or window_closed(MAIN_WIN):
            return None
        if key == ord(" "):
            started = True
    feats = np.array(samples, dtype=np.float32)
    np.save(FACE_DB, feats)
    return feats


class Detector(threading.Thread):
    """Kamerayi okuyup yuzleri arka planda analiz eder; ana dongu sadece goruntuleri gosterir."""

    def __init__(self, cap, analyzer, my_features, log):
        super().__init__(daemon=True)
        self.cap, self.analyzer, self.my_features, self.log = cap, analyzer, my_features, log
        self.lock = threading.Lock()
        self.view, self.view_id = None, 0
        self.triggered = threading.Event()
        self.stopped = threading.Event()
        self.video_playing = threading.Event()  # video oynarken analiz yapilmaz, islemci videoya kalir

    def run(self):
        streak = 0
        try:
            while not self.stopped.is_set():
                ok, frame = self.cap.read()
                if not ok:
                    self.log.write("kameradan goruntu alinamadi")
                    break
                if self.video_playing.is_set():
                    streak = 0
                    with self.lock:
                        self.view, self.view_id = cv2.flip(frame, 1), self.view_id + 1
                    continue
                faces = self.analyzer.analyze(frame)
                scores = [self.analyzer.similarity(f["feature"], self.my_features) for f in faces]
                is_me = [s >= MATCH_THRESHOLD for s in scores]

                # Tek karelik kacirmalar seriyi sifirlamasin, yavasca azalsin
                streak = streak + 1 if not all(is_me) else max(streak - 1, 0)
                self.log.faces(faces, scores, streak)
                if streak >= TRIGGER_FRAMES:
                    self.triggered.set()
                    streak = 0

                view = mirrored(frame, faces, [(0, 200, 0) if me else (0, 0, 255) for me in is_me],
                                ["" if me else "YABANCI" for me in is_me])
                with self.lock:
                    self.view, self.view_id = view, self.view_id + 1
        except Exception as e:  # hata olursa sessizce donmasin, loga yazilsin
            self.log.write(f"HATA: {e!r}")

    def latest(self):
        with self.lock:
            return self.view, self.view_id

    def stop(self):
        self.stopped.set()
        self.join(timeout=3)


class VideoPlayer:
    """Videoyu ayri bir ffplay surecinde oynatir.

    Ayni Python surecinde oynatinca yuz analizi oynaticiyi bekletiyor, ses takilip tekrarliyordu.
    """

    def __init__(self, height):
        # ffplay fiziksel piksel kullanir; Windows olceklendirmesi (%200 vb.) ile carpilmazsa yarim boy acilir
        s = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
        self.rect = video_rect(height)
        left, top, w, h = (round(v * s) for v in self.rect)
        self.proc = subprocess.Popen(
            [FFPLAY, "-hide_banner", "-loglevel", "error", "-autoexit", "-noborder", "-alwaysontop",
             "-left", str(left), "-top", str(top), "-x", str(w), "-y", str(h),
             "-window_title", VIDEO_WIN, VIDEO],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    @property
    def done(self):
        return self.proc.poll() is not None

    def close(self):
        """Programdan cikarken video hala oynuyorsa kapatir."""
        if not self.done:
            self.proc.terminate()
            self.proc.wait(timeout=3)


def place_main_window(video_h):
    """Detector penceresini ekranin sagina koyar; solunda videoya yer kalir, ust kenarlar ayni hizada olur."""
    screen_w = user32.GetSystemMetrics(0)
    cam_w = max(screen_w - 2 * SCREEN_MARGIN - VIDEO_WIDTH - VIDEO_GAP, 480)
    cam_h = round(cam_w * 3 / 4)
    cv2.namedWindow(MAIN_WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(MAIN_WIN, cam_w, cam_h)
    cv2.moveWindow(MAIN_WIN, screen_w - SCREEN_MARGIN - cam_w, VIDEO_TOP)


def video_rect(height):
    """Videoyu Detector penceresinin soluna, ust kenarlari ayni hizada ve araya bosluk birakarak yerlestirir."""
    w, h = VIDEO_WIDTH, height
    hwnd = user32.FindWindowW(None, MAIN_WIN)
    r = wintypes.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return VIDEO_LEFT, VIDEO_TOP, w, h
    room = r.left - VIDEO_GAP
    if room < w:  # solda yer yetmezse video sigacak kadar kuculur
        w = max(room, MIN_VIDEO_WIDTH)
        h = round(height * w / VIDEO_WIDTH)
    top = r.top + (r.bottom - r.top - h) // 2  # Detector penceresine gore dikeyde ortali
    return max(r.left - VIDEO_GAP - w - VIDEO_SHIFT_LEFT, 0), max(top, 0), w, h


def video_height():
    """Pencere yuksekligi videonun en-boy oranina gore."""
    cap = cv2.VideoCapture(VIDEO)
    w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    return round(VIDEO_WIDTH * h / w) if w else round(VIDEO_WIDTH * 9 / 16)


def main():
    if not os.path.exists(VIDEO):
        # cikis kodu 1: .bat penceresi acik kalir, hata okunur
        sys.exit(f"Video bulunamadi: {VIDEO}\nOynatmak istedigin videoyu bu klasore kolpacino.mov adiyla koy.")
    height = video_height()
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        sys.exit("Kamera acilamadi. Baska bir program kamerayi kullaniyor olabilir.")
    analyzer = FaceAnalyzer()
    log = Log()
    place_main_window(height)
    detector, video = None, None
    try:
        my_features = None
        if os.path.exists(FACE_DB) and "--kayit" not in sys.argv:
            my_features = np.load(FACE_DB)
        if my_features is None:
            my_features = enroll(cap, analyzer)
            if my_features is None:
                return
        log.write(f"kayitli ornek sayisi: {len(my_features)}")

        detector = Detector(cap, analyzer, my_features, log)
        detector.start()
        shown_id, last_video_end = 0, -COOLDOWN_SEC
        play_at = None  # tespit sonrasi videonun baslayacagi an
        while True:
            if video is not None and video.done:
                log.write("video bitti")
                video = None
                detector.video_playing.clear()
                last_video_end = time.monotonic()

            view, view_id = detector.latest()
            if view is not None and view_id != shown_id:
                shown_id = view_id
                view = view.copy()
                cooldown_left = COOLDOWN_SEC - (time.monotonic() - last_video_end)
                if video is None and cooldown_left > 0:
                    put_text(view, f"{cooldown_left:.0f}", (10, 30), scale=0.9)
                hint = "q: cikis  r: yeniden kayit"
                (tw, _), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                put_text(view, hint, (view.shape[1] - tw - 10, view.shape[0] - 10), scale=0.45, color=(200, 200, 200))
                cv2.imshow(MAIN_WIN, view)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                log.write("cikis: q tusu")
                break
            if window_closed(MAIN_WIN):
                log.write("cikis: kamera penceresi kapatildi")
                break
            if not detector.is_alive():
                log.write("cikis: analiz durdu")
                break
            if key == ord("r"):
                detector.stop()
                new = enroll(cap, analyzer)
                if new is None:
                    break
                my_features = new
                detector = Detector(cap, analyzer, my_features, log)
                detector.start()

            if detector.triggered.is_set():
                detector.triggered.clear()
                if video is None and play_at is None and time.monotonic() - last_video_end >= COOLDOWN_SEC:
                    log.write("YABANCI TESPIT EDILDI")
                    play_at = time.monotonic() + max(PLAY_DELAY_SEC - FFPLAY_STARTUP_SEC, 0)

            if play_at is not None and time.monotonic() >= play_at:
                play_at = None
                log.write("VIDEO TETIKLENDI")
                detector.video_playing.set()
                video = VideoPlayer(height)
                log.write(f"video konumu (sol, ust, genislik, yukseklik): {video.rect}")
    finally:
        if detector is not None:
            detector.stop()
        if video is not None:
            video.close()
        cap.release()
        analyzer.close()
        log.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
