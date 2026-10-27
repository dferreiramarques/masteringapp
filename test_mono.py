"""/process com ficheiro MONO: a app assumia stereo (x[:,1]) — crash esperado."""
import io
import json
import urllib.error
import urllib.request

import numpy as np
import soundfile as sf

BASE = "http://127.0.0.1:7860"
sr = 44100
t = np.linspace(0, 2, sr * 2, endpoint=False)
mono = (0.3 * np.sin(2 * np.pi * 440 * t)).astype("float32")
sf.write("test_mono.wav", mono, sr, subtype="PCM_16")

data = open("test_mono.wav", "rb").read()
bound = "----b1"
body = io.BytesIO()
for k, v in [("genre", "indie"), ("auto", "1")]:
    body.write(f'--{bound}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
body.write(f'--{bound}\r\nContent-Disposition: form-data; name="audio"; filename="mono.wav"'
           '\r\nContent-Type: audio/wav\r\n\r\n'.encode())
body.write(data + f"\r\n--{bound}--\r\n".encode())
req = urllib.request.Request(BASE + "/process", data=body.getvalue(),
                             headers={"Content-Type": f"multipart/form-data; boundary={bound}"})
try:
    r = urllib.request.urlopen(req, timeout=120)
    j = json.load(r)
    print("OK", j["master"]["lufs"], j["master"]["true_peak"])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:400])
