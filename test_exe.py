"""E2E minimo contra um server Base arbitrario (p/ o .exe: MASTERING_BASE).
   process → remaster preview → export plataforma → download com Content-Disposition."""
import io
import json
import os
import uuid
import urllib.request

BASE = os.environ.get("MASTERING_BASE", "http://127.0.0.1:7860")
boundary = uuid.uuid4().hex
with open("test_mix_short.wav", "rb") as fh:
    data = fh.read()


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
    data=multipart("audio", "Exe Teste.wav", data, {"genre": "indie"}),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
j = json.load(urllib.request.urlopen(req, timeout=600))
uid, params = j["uid"], j["params"]
print("1) process ok", uid, "| lufs orig", round(j["original"]["lufs"], 2)
      if isinstance(j["original"].get("lufs"), (int, float)) else "")

req2 = urllib.request.Request(
    BASE + "/remaster",
    data=json.dumps({"uid": uid, "genre": "indie", "preview": True,
                     "params": params}).encode(),
    headers={"Content-Type": "application/json"})
r2 = json.load(urllib.request.urlopen(req2, timeout=900))
print("2) remaster ok | lufs", round(r2["master"]["lufs"], 2),
      "tp", round(r2["master"]["true_peak"], 2))

req3 = urllib.request.Request(
    BASE + "/export_platform",
    data=json.dumps({"uid": uid, "genre": "indie", "platform": "spotify",
                     "params": params}).encode(),
    headers={"Content-Type": "application/json"})
r3 = json.load(urllib.request.urlopen(req3, timeout=900))
print("3) export ok | lufs", round(r3["master"]["lufs"], 2), "spec_ok", r3["spec_ok"])

r4 = urllib.request.urlopen(BASE + r3["master"]["download"], timeout=60)
blob = r4.read()
print("4) download ok |", r4.headers.get("Content-Disposition"),
      "|", round(len(blob) / 1e6, 1), "MB | WAV magic:", blob[:4])

print("\nEXE E2E PASS")
