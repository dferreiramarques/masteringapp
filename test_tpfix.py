"""Reproduz o crash do /process: mistura com TP alto (> -0.2 dB) + auto."""
import io
import json
import uuid
import urllib.request

import numpy as np
import soundfile as sf

BASE = "http://127.0.0.1:7860"
boundary = uuid.uuid4().hex

x, sr = sf.read("test_mix.wav", always_2d=True)
x = (x[:sr * 30] * 2.5).astype(np.float32)          # TP sobe ~ +8 dB
buf = io.BytesIO()
sf.write(buf, x, sr, format="WAV", subtype="PCM_16")
data = buf.getvalue()


def multipart(field, fname, blob, extra=None):
    parts = []
    for k, v in (extra or {}).items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"'
                     f'\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                 f'filename="{fname}"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
                 + blob + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


req = urllib.request.Request(
    BASE + "/process",
    data=multipart("audio", "tp_alto.wav", data, {"genre": "indie"}),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
j = json.load(urllib.request.urlopen(req, timeout=600))
print("process OK | TP entrada:", j["original"]["true_peak"])
print("auto dyn:", [(d["metric"], d["msg"][:50]) for d in j["auto"]["dyn"]])
