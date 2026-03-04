import sounddevice as sd
import numpy as np
import keyboard
import pyperclip
import tempfile
import wave
import os
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
recording = []
is_recording = False

print("Загрузка модели Whisper (первый раз ~1 минута)...")
model = WhisperModel("tiny", device="cpu", compute_type="int8")
print("Готово!")
print("Держи F8 чтобы говорить, отпусти — текст вставится автоматически")
print("Нажми ESC для выхода")

def audio_callback(indata, frames, time, status):
    if is_recording:
        recording.append(indata.copy())

stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32', callback=audio_callback)
stream.start()

def on_press(e):
    global is_recording, recording
    if not is_recording:
        recording = []
        is_recording = True
        print("Запись...", end='\r')

def on_release(e):
    global is_recording
    if is_recording:
        is_recording = False
        transcribe()

def transcribe():
    if not recording:
        return

    print("Распознавание...  ", end='\r')
    audio = np.concatenate(recording, axis=0).flatten()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    with wave.open(tmp_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())

    segments, _ = model.transcribe(tmp_path, language="ru")
    text = " ".join([s.text for s in segments]).strip()

    os.unlink(tmp_path)

    if text:
        pyperclip.copy(text)
        print(f"Вставка в чат: {text}")
        keyboard.press_and_release('ctrl+v')
    else:
        print("Ничего не распознано")

keyboard.on_press_key('F8', on_press)
keyboard.on_release_key('F8', on_release)

keyboard.wait('esc')
stream.stop()
print("Выход.")
