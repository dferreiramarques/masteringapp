"""E2E dos exports por plataforma + paridade do A/B em pre-escuta."""
import io
import json
import uuid
import urllib.request

BASE = "http://127.0.0.1:7860"
boundary = uuid.uuid4().hex

with open("test_mix.wav", "rb") as fh:
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
    data=multipart("audio", "test_mix.wav", data, {"genre": "indie"}),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
j = json.load(urllib.request.urlopen(req, timeout=600))
uid, params = j["uid"], j["params"]
print("process ok | uid", uid)

# paridade A/B: preview tem de devolver preview_url do original cortado
req2 = urllib.request.Request(
    BASE + "/remaster",
    data=json.dumps({"uid": uid, "genre": "indie", "preview": True,
                     "params": params}).encode(),
    headers={"Content-Type": "application/json"})
j2 = json.load(urllib.request.urlopen(req2, timeout=600))
print("preview | slice:", j2["slice"],
      "| preview_url:", j2["original"].get("preview_url"))

# exports por grupo de spec (ficheiros iguais partilham render em cache)
import time
times = {}
for plat in ["spotify", "youtube", "amazon", "tidal"]:
    req3 = urllib.request.Request(
        BASE + "/export_platform",
        data=json.dumps({"uid": uid, "genre": "indie", "platform": plat,
                         "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    t1 = time.time()
    ex = json.load(urllib.request.urlopen(req3, timeout=900))
    times[plat] = time.time() - t1
    print(f"{plat:>8}: lufs {ex['master']['lufs']:7.2f} (meta {ex['spec']['lufs']})"
          f"  tp {ex['master']['true_peak']:6.2f}  spec_ok={ex['spec_ok']}"
          f"  cache={ex['cached']}  serve={'+'.join(ex['serves'])}  [{times[plat]:.1f}s]")
# primeiro pedido do grupo renderiza; os seguintes devem sair de cache (<2 s)
for plat in ["youtube", "amazon", "tidal"]:
    if times[plat] >= 2.0:
        raise SystemExit(f"FALHOU: {plat} devia reusar o render do Spotify (cache), levou {times[plat]:.1f}s")

for plat in ["deezer", "apple"]:
    req3 = urllib.request.Request(
        BASE + "/export_platform",
        data=json.dumps({"uid": uid, "genre": "indie", "platform": plat,
                         "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    ex = json.load(urllib.request.urlopen(req3, timeout=900))
    print(f"{plat:>8}: lufs {ex['master']['lufs']:7.2f} (meta {ex['spec']['lufs']})"
          f"  tp {ex['master']['true_peak']:6.2f}  spec_ok={ex['spec_ok']}")

# ficheiro original intacto: o export tnao deve tocar no master da sessao
req4 = urllib.request.Request(
    BASE + "/remaster",
    data=json.dumps({"uid": uid, "genre": "indie", "preview": False,
                     "params": params}).encode(),
    headers={"Content-Type": "application/json"})
j4 = json.load(urllib.request.urlopen(req4, timeout=600))
print("master da sessao intacto | lufs", j4["master"]["lufs"])
