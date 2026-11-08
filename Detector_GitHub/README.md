# Detector

Bilgisayarının ekranına **senden başka biri** baktığında, kameradan bunu fark edip ekranda bir video oynatan küçük bir Windows programı. Video, yabancı tespit edildikten 2 saniye sonra kamera penceresinin solunda açılır, oynar ve kendiliğinden kapanır.

Fikir: arkandan ekranına bakan birine Kolpaçino'nun meşhur *"Siz kimsiniz lan?"* sahnesini izletmek.

## Nasıl çalışır?

1. **MediaPipe** kameradaki yüzleri bulur.
2. **OpenCV SFace** modeli her yüzü, ilk açılışta kaydettiğin kendi yüzünle karşılaştırır.
3. Sen olmayan bir yüz görünürse çerçevesi kırmızı olur, üstünde **YABANCI** yazar ve video **FFmpeg (ffplay)** ile oynatılır.

Yüz verin sadece kendi bilgisayarında, program klasöründeki `benim_yuzum.npy` dosyasında durur. Hiçbir yere gönderilmez.

## Gereksinimler

- Windows 10 veya 11
- Web kamerası
- İnternet bağlantısı (sadece kurulum sırasında)

## Kurulum

1. Bu sayfada yeşil **Code** düğmesine tıkla, **Download ZIP** ile indir.
2. Zip'i kısa ve Türkçe karakter içermeyen bir klasöre çıkar, örneğin `C:\Detector`.
   > Klasör yolunda ç, ş, ğ, ü, ö, ı gibi harfler varsa yüz modeli açılamayabilir.
3. `kurulum.bat` dosyasına çift tıkla. Python, kütüphaneler, yüz modelleri ve video oynatıcı otomatik kurulur. Bu birkaç dakika sürebilir.
   > Windows "Bilgisayarınız korundu" uyarısı verirse **Ek bilgi**, ardından **Yine de çalıştır** seç.

## Kullanım

1. `detector.bat` dosyasına çift tıkla.
2. İlk açılışta yüz kaydı yapılır: kamerada sadece sen ol, kameraya bak ve **SPACE** tuşuna bas.
3. Artık kamerada senden başka biri görünürse 2 saniye sonra video oynar.

| Tuş | İşlev |
|-----|-------|
| `q` | Programı kapatır |
| `r` | Yüzünü yeniden kaydeder |

Kamera penceresinde yeşil çerçeve **sen**, kırmızı çerçeve **yabancı** demektir.

Başka bir video oynatmak istersen, onu klasördeki `kolpacino.mov` dosyasının yerine aynı adla koyman yeterli.

## Ayarlar

`detector.py` dosyasının başındaki değerleri değiştirebilirsin:

| Ayar | Varsayılan | Açıklama |
|------|-----------|----------|
| `PLAY_DELAY_SEC` | `2` | Yabancı tespit edildikten kaç saniye sonra videonun başlayacağı |
| `COOLDOWN_SEC` | `3` | İki video arasındaki bekleme süresi (saniye) |
| `VIDEO_WIDTH` | `760` | Video penceresinin genişliği |
| `VIDEO_GAP` | `12` | Video ile kamera penceresi arasındaki boşluk |
| `MATCH_THRESHOLD` | `0.5` | Seni yabancı sanıyorsa düşür, yabancıyı sen sanıyorsa yükselt |

## Sorun giderme

- **Kamera açılamadı:** Kamerayı kullanan başka bir programı (Zoom, Teams, kamera uygulaması) kapat.
- **Video bulunamadı:** Klasörde `kolpacino.mov` dosyasının durduğundan emin ol.
- **Seni yabancı sanıyor:** Programı açıp `r` tuşuna bas ve yüzünü iyi ışıkta yeniden kaydet.

## Kullanılan açık kaynak araçlar

- [MediaPipe](https://github.com/google-ai-edge/mediapipe): yüz bulma
- [OpenCV](https://opencv.org/) ve [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface): yüz tanıma
- [FFmpeg](https://ffmpeg.org/): video oynatma
