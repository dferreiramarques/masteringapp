"""Verifica os nomes de download (input + sufixo) no /process e /export_platform."""
import io
import json
import uuid
import urllib.request

BASE = "http://127.0.0.1:7860"
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
    data=multipart("audio", "Minha Mix Teste.wav", data, {"genre": "indie"}),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
j = json.load(urllib.request.urlopen(req, timeout=600))
uid, params = j["uid"], j["params"]
print("process ok", uid)
print("master.download_name:", j["master"]["download_name"])
print("master.download:", j["master"]["download"])
print("original.download_name:", j["original"]["download_name"])

# Content-Disposition real do master
r = urllib.request.urlopen(BASE + j["master"]["download"], timeout=60)
print("CD master:", r.headers.get("Content-Disposition"))

for plat in ["spotify", "apple"]:
    req3 = urllib.request.Request(
        BASE + "/export_platform",
        data=json.dumps({"uid": uid, "genre": "indie", "platform": plat,
                         "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    ex = json.load(urllib.request.urlopen(req3, timeout=900))
    print(f"export {plat}: {ex['master']['download_name']}  cache={ex['cached']}")
    r3 = urllib.request.urlopen(BASE + ex["master"]["download"], timeout=60)
    print("  CD:", r3.headers.get("Content-Disposition"))
