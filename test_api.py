import io
import json
import time
import urllib.request

BASE = "http://127.0.0.1:7860"


def multipart(fields, filename, filedata):
    bound = "----ma1"
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f'--{bound}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    body.write(f'--{bound}\r\nContent-Disposition: form-data; name="audio"; filename="{filename}"'
               '\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    body.write(filedata + f"\r\n--{bound}--\r\n".encode())
    req = urllib.request.Request(
        BASE + "/process", data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={bound}"})
    return json.load(urllib.request.urlopen(req, timeout=900))


def post_json(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))


print("/genres:", [g["id"] for g in json.load(urllib.request.urlopen(BASE + "/genres", timeout=15))])

data = open("test_mix.wav", "rb").read()
t0 = time.time()
j = multipart({"genre": "pop", "auto": "1"}, "test_mix.wav", data)
print(f"/process pop: status ok | lufs {j['master']['lufs']} | tp {j['master']['true_peak']} | {time.time()-t0:.1f}s")
uid = j["uid"]

# pre-escuta
t0 = time.time()
j = post_json("/remaster", {"uid": uid, "preview": True, "params": {"tape_drive": 9.0}})
print(f"/remaster preview: ok | {time.time()-t0:.1f}s | slice {j['slice']} | tp {j['master']['true_peak']}")

# completa para comparar tempo
t0 = time.time()
j = post_json("/remaster", {"uid": uid, "preview": False, "params": {"tape_drive": 9.0}})
print(f"/remaster completa: ok | {time.time()-t0:.1f}s | lra master: {j['master']['lra']}")
