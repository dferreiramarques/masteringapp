"""/compare (pré-escuta multi-género com cache) + /progress/{uid}."""
import io
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:7860"


def post_json(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))


data = open("test_mix_short.wav", "rb").read()
bound = "----cmp1"
body = io.BytesIO()
for k, v in [("genre", "indie"), ("auto", "1"), ("uid", "cafebeef01")]:
    body.write(f'--{bound}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
body.write(f'--{bound}\r\nContent-Disposition: form-data; name="audio"; filename="cmp.wav"'
           '\r\nContent-Type: audio/wav\r\n\r\n'.encode())
body.write(data + f"\r\n--{bound}--\r\n".encode())
req = urllib.request.Request(BASE + "/process", data=body.getvalue(),
                             headers={"Content-Type": f"multipart/form-data; boundary={bound}"})
uid = json.load(urllib.request.urlopen(req, timeout=900))["uid"]
print("1) process ok, uid =", uid)

p = json.load(urllib.request.urlopen(BASE + "/progress/" + uid, timeout=15))
print("2) progress endpoint ok | pct", p["pct"], "|", p["msg"][:40])

s = post_json("/compare", {"uid": uid, "genres": ["krautrock", "pop", "ambient"]})
rows = s["results"]
assert len(rows) == 3, len(rows)
for r in rows:
    assert r["lufs"] is not None and r["tp"] is not None, r
    print(f"   {r['genre']:<10} lufs {r['lufs']:>6} tp {r['tp']:>6} cache={r['cached']} chars={r['chars']}")
print("3) /compare ok (3 géneros)")

s2 = post_json("/compare", {"uid": uid, "genres": ["krautrock", "pop", "ambient"]})
assert all(r["cached"] for r in s2["results"]), "cache de compare falhou"
print("4) re-comparar = cache em todos")

try:
    post_json("/compare", {"uid": uid, "genres": []})
except urllib.error.HTTPError as e:
    assert e.code == 400, e.code
    print("5) géneros vazios -> 400 ok")

print("COMPARE/PROGRESS PASS")
