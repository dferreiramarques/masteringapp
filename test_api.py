import json
import time

import requests

BASE = "http://127.0.0.1:7860"

print("/genres:", [g["id"] for g in requests.get(BASE + "/genres", timeout=15).json()])

data = open("test_mix.wav", "rb").read()
for genre in ["pop", "ambient", "noise"]:
    t0 = time.time()
    r = requests.post(BASE + "/process",
                      files={"audio": ("test_mix.wav", data, "audio/wav")},
                      data={"genre": genre}, timeout=900)
    j = r.json()
    print(f"/process {genre}: {r.status_code} | lufs {j['master']['lufs']} | tp {j['master']['true_peak']} | {time.time()-t0:.1f}s")
    break  # só um uid para os testes seguintes

uid = requests.post(BASE + "/process",
                    files={"audio": ("test_mix.wav", data, "audio/wav")},
                    data={"genre": "krautrock"}, timeout=900).json()["uid"]

# pre-escuta
t0 = time.time()
r = requests.post(BASE + "/remaster", json={"uid": uid, "preview": True,
                                            "params": {"tape_drive": 9.0}}, timeout=900)
j = r.json()
print(f"/remaster preview: {r.status_code} | {time.time()-t0:.1f}s | slice {j['slice']} | tp {j['master']['true_peak']}")

# completa para comparar tempo
t0 = time.time()
r = requests.post(BASE + "/remaster", json={"uid": uid, "preview": False,
                                            "params": {"tape_drive": 9.0}}, timeout=900)
print(f"/remaster completa: {r.status_code} | {time.time()-t0:.1f}s")
