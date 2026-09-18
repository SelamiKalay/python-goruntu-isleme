# Python Computer Vision Projects

**English** | [Türkçe](README.tr.md)

Small camera-based computer vision projects built with OpenCV, MediaPipe and
face_recognition.

| Project | Description | Libraries |
|---|---|---|
| [`el-hareketi-muzik-kontrolu`](el-hareketi-muzik-kontrolu) | A player that starts the music when both hands make a specific gesture at the same time (thumb + index + middle finger extended) and stops it when the hands are lowered | OpenCV, MediaPipe, pygame |
| [`yuz-tanima-muzik-calar`](yuz-tanima-muzik-calar) | A player that automatically starts the music when a known face appears in front of the camera | face_recognition, OpenCV, pygame |
| [`hareket-algilama`](hareket-algilama) | Motion detection with background subtraction; includes a version that sends photo alerts to Telegram | OpenCV, NumPy, requests |
| [`el-cercevesi-efektler`](el-cercevesi-efektler) | Real-time image effects (X-ray, cartoon, neon, glitch, night vision and more) inside a frame formed by the fingers of both hands; switch effects with a pinch gesture | OpenCV, MediaPipe, NumPy |
| [`guvenlik-kamerasi`](guvenlik-kamerasi) | A security camera that records video with audio when motion is detected and sends the recording to Telegram | OpenCV, PyAudio, MoviePy |

The README files inside the project folders are in Turkish.

## Installation

```bash
pip install -r requirements.txt
```

> The `face_recognition` library depends on `dlib`; on Windows, CMake and the
> Visual C++ Build Tools may be required to install it.

## Usage Notes

- **Hand gesture music control:** the MediaPipe hand model is downloaded
  automatically on first run. Put a music file named `music.mp3` next to the script.
- **Face recognition music player:** put your reference face photo (`my_face.jpg`)
  and the music to play (`song.mp3`) next to the script.
- **Telegram notifications:** bot credentials are not stored in the code; they are
  read from environment variables:

  ```bash
  set TELEGRAM_BOT_TOKEN=<token from BotFather>
  set TELEGRAM_CHAT_ID=<chat id>
  ```

  To find your chat ID, run `guvenlik-kamerasi/get_telegram_id.py` and send a
  message to your bot.
