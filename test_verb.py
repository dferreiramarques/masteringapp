"""Testes do reverb de mix (verb_mix / mix_ambience):
   1) offline: IR determinístico, comprimento preservado, energia limitada,
      correlação estéreo desce, graves do wet filtrados;
   2) E2E: /remaster preview com verb 0/50/100 — LUFS/TP estáveis, corr desce,
      tempo de render aceitável."""
import io
import json
import time
import uuid
import urllib.request
import wave

import numpy as np

BASE = "http://127.0.0.1:7860"
SR = 44100

# ---------------------------------------------------------------- offline ---
import app as m

rng = np.random.default_rng(7)
x = rng.standard_normal((SR * 4, 2)) * 0.2
# sinal estéreo correlacionado: canal direito = esquerdo
x[:, 1] = x[:, 0]

fails = []

def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        fails.append(name)

t0 = time.perf_counter()
y0 = m.mix_ambience(x.copy(), SR, 0.0)
t1 = time.perf_counter()
y1 = m.mix_ambience(x.copy(), SR, 0.1)
t2 = time.perf_counter()
y1b = m.mix_ambience(x.copy(), SR, 0.1)
y2 = m.mix_ambience(x.copy(), SR, 0.2)
t3 = time.perf_counter()

check("mix=0 identico", np.array_equal(y0, x))
check("comprimento preservado", y1.shape == x.shape)
check("deterministico (mesmo IR)", np.array_equal(y1, y1b))
check("mix 20% > 10% em diff RMS",
      np.sqrt(np.mean((y2 - x) ** 2)) > np.sqrt(np.mean((y1 - x) ** 2)))

# energia adicionada: diff RMS nunca deve passar ~0.45 * RMS do sinal a mix=0.2
d2 = np.sqrt(np.mean((y2 - x) ** 2)) / np.sqrt(np.mean(x ** 2))
check("diff RMS a mix=0.2 limitado (<0.5x)", d2 < 0.5, f"{d2:.3f}")

# correlacao desce com mais wet (o dry era 100% correlacionado)
c0 = m.stereo_correlation(x)
c1 = m.stereo_correlation(y1)
c2 = m.stereo_correlation(y2)
check("corr desce com wet", c0 > c1 > c2, f"{c0:.3f} -> {c1:.3f} -> {c2:.3f}")

# graves do wet filtrados: diff (o wet) deve ter pouca energia < 200 Hz
sp = __import__("scipy.signal", fromlist=["signal"])
seg = (y2 - x)[:, 0]
f, P = sp.welch(seg, SR, nperseg=8192)
lo = np.mean(P[f < 150]); mid = np.mean(P[(f > 400) & (f < 4000)])
check("graves do wet atenuados (hp 220)", lo < mid, f"lo/mid {lo / max(mid, 1e-12):.2f}")

# agudos amortecidos: energia do wet acima de 9 kHz < banda 2-5 kHz
hi = np.mean(P[f > 9000]); mid2 = np.mean(P[(f > 2000) & (f < 5000)])
check("agudos do wet amortecidos", hi < mid2, f"hi/mid {hi / max(mid2, 1e-12):.2f}")

print(f"timing offline: mix=0 {1000 * (t1 - t0):.0f} ms | 10% {1000 * (t2 - t1):.0f} ms | "
      f"20% {1000 * (t3 - t2):.0f} ms (4 s estéreo)")

# -------------------------------------------------------------------- E2E ---
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
    data=multipart("audio", "Verb Teste.wav", data, {"genre": "indie"}),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
j = json.load(urllib.request.urlopen(req, timeout=600))
uid, params = j["uid"], j["params"]
print("process ok", uid)

results = []
for vm in [0, 50, 100]:
    tA = time.perf_counter()
    req2 = urllib.request.Request(
        BASE + "/remaster",
        data=json.dumps({"uid": uid, "genre": "indie", "preview": True,
                         "params": {**params, "verb_mix": vm}}).encode(),
        headers={"Content-Type": "application/json"})
    r2 = json.load(urllib.request.urlopen(req2, timeout=900))
    dt = time.perf_counter() - tA
    results.append((vm, r2, dt))
    print(f"verb={vm:3d}%  lufs={r2['master']['lufs']:.2f}  tp={r2['master']['true_peak']:.2f}"
          f"  corr={r2['master']['corr']:.3f}  render={dt:.1f}s")

mm0, mm50, mm100 = (r[1]["master"] for r in results)
check("LUFS estavel com reverb", abs(mm100["lufs"] - mm0["lufs"]) <= 0.6,
      f"{mm0['lufs']:.2f} vs {mm100['lufs']:.2f}")
ceil = params.get("lim_ceiling_db", -1.0)
check("TP dentro do ceiling", mm100["true_peak"] <= ceil + 0.1,
      f"{mm100['true_peak']:.2f} vs ceiling {ceil:.2f}")
check("corr desce no master real", mm100["corr"] < mm0["corr"],
      f"{mm0['corr']:.3f} -> {mm100['corr']:.3f}")
check("render +reverb < 15 s", results[2][2] < 15.0, f"{results[2][2]:.1f}s")

# cadeia menciona a ambiencia quando > 0
chain = r2.get("chain") or []
if chain:
    check("cadeia menciona Ambiencia", any("mbi" in s for s in chain))

print("\n" + ("TODOS PASS" if not fails else f"FALHAS: {fails}"))
raise SystemExit(0 if not fails else 1)
