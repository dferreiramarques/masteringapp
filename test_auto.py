"""Testes do fluxo Auto v2:
   1) /auto SEM current -> = antigo (default genero + decisões)
   2) /auto COM current -> ajusta SOBRE o perfil enviado (respeita manual:
      bio >0 mantém-se; comp deltas escalam dos valores atuais; fita/drive
      manual não é apagado)
   3) /profile/{genre} -> perfil puro (sem overrides, bio 0, tape 0)."""
import json
import os
import time
import uuid
import urllib.request

BASE = "http://127.0.0.1:7860"
fails = []


def check(name, cond, detail=""):
    ok = "PASS" if cond else "FAIL"
    print(f"{ok} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        fails.append(name)


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
    data=multipart("audio", "Auto Flow Teste.wav", data, {"genre": "indie"}),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
j = json.load(urllib.request.urlopen(req, timeout=600))
uid, params = j["uid"], j["params"]
print("process ok", uid)

# ---------------------------------------------------------- 1) auto default --
reqA = urllib.request.Request(
    BASE + "/auto",
    data=json.dumps({"uid": uid, "genre": "indie"}).encode(),
    headers={"Content-Type": "application/json"})
a1 = json.load(urllib.request.urlopen(reqA, timeout=120))
check("auto default: bio 50", a1["params"]["bio_strength"] == 50.0)
check("auto default: tape_mix 0 (perfil genero)", a1["params"]["tape_mix"] == 0.0)
check("auto devolve decisão dyn", any("compress" in d["msg"].lower() or "dín" in d["msg"].lower()
                                      or "dinâ" in d["msg"].lower() or "equilib" in d["msg"].lower()
                                      for d in a1["auto"]["dyn"]),
      str([d["msg"] for d in a1["auto"]["dyn"]][:1]))

# ------------------------------------------------ 2) auto com perfil atual ---
cur = dict(params)
cur["tape_drive"] = 9.0                      # escolha manual do user
cur["tape_mix"] = 0.6
cur["bio_strength"] = 80.0                   # user já ativou bio alto
cur["comp_ratio"] = 2.2
cur["comp_threshold"] = -6.0
reqB = urllib.request.Request(
    BASE + "/auto",
    data=json.dumps({"uid": uid, "genre": "indie", "params": cur}).encode(),
    headers={"Content-Type": "application/json"})
a2 = json.load(urllib.request.urlopen(reqB, timeout=120))
p2 = a2["params"]
check("auto SOBRE current: mantém fita manual (drive 9)", p2["tape_drive"] == 9.0,
      f'{p2["tape_drive"]}')
check("auto SOBRE current: mantém mix de fita manual (0.6)", p2["tape_mix"] == 0.6)
check("auto SOBRE current: bio >0 não é reduzido", p2["bio_strength"] == 80.0)
check("dinâmica escala do atual (ratio <= 2.2)", p2["comp_ratio"] <= 2.2,
      f'{cur["comp_ratio"]} -> {p2["comp_ratio"]}')

# LRA baixo -> solta: ratio 0.85x, threshold +1.5, release 1.25x (sobre o atual)
lra = j["original"].get("lra")
if lra is not None and lra < 3.5:
    check("LRA<3.5: solta a partir do ATUAL",
          abs(p2["comp_ratio"] - cur["comp_ratio"] * 0.85) < 0.01
          and abs(p2["comp_threshold"] - (cur["comp_threshold"] + 1.5)) < 0.01,
          f'ratio {cur["comp_ratio"]}->{p2["comp_ratio"]}, thr {cur["comp_threshold"]}->{p2["comp_threshold"]}')

# ---------------------------------------------------------- 3) perfil puro ---
reqC = urllib.request.urlopen(BASE + "/profile/indie", timeout=30)
c = json.loads(reqC.read().decode())
pr = c["params"]
check("/profile bio 0", pr["bio_strength"] == 0.0)
check("/profile tape_mix 0", pr["tape_mix"] == 0.0)
check("/profile = default do genero (LUFS igual ao do /process)",
      pr["lufs_target"] == params["lufs_target"])
g = json.load(urllib.request.urlopen(BASE + "/genres", timeout=10))
gl = [x for x in g if x["id"] == "indie"][0]
check("/profile lufs = meta do genero", pr["lufs_target"] == gl["lufs"])
try:
    urllib.request.urlopen(BASE + "/profile/naoexiste", timeout=10)
    check("/profile genero invalido -> 404", False)
except urllib.error.HTTPError as e:
    check("/profile genero invalido -> 404", e.code == 404)

print("\n" + ("TODOS PASS" if not fails else f"FALHAS: {fails}"))
raise SystemExit(0 if not fails else 1)
