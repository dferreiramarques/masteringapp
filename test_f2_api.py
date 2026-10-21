"""E2E da fase 2.1 (auto + /auto + /remaster) contra o servidor local."""
import json
import uuid
import urllib.request

BASE = "http://127.0.0.1:7860"
boundary = uuid.uuid4().hex


def multipart(field, fname, data, extra=None):
    parts = []
    for k, v in (extra or {}).items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"'
                     f'\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                 f'filename="{fname}"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
                 + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


data = open("test_mix.wav", "rb").read()
req = urllib.request.Request(BASE + "/process", data=multipart("audio", "test_mix.wav", data, {"genre": "pop"}), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
j = json.load(urllib.request.urlopen(req, timeout=600))
print("process ok | bio_strength:", j["params"]["bio_strength"],
      "| comp_thr:", j["params"]["comp_threshold"])
print("auto dyn:", [d["msg"] for d in j["auto"]["dyn"]])
print("tech:", [t["key"] for t in j["psycho"]["tech"]])
print("indices:", j["psycho"]["indices"])

req2 = urllib.request.Request(BASE + "/auto",
                              data=json.dumps({"uid": j["uid"], "genre": "krautrock"}).encode(),
                              headers={"Content-Type": "application/json"})
j2 = json.load(urllib.request.urlopen(req2, timeout=60))
print("auto ok | bio:", j2["params"]["bio_strength"],
      "comp_ratio:", j2["params"]["comp_ratio"])

req3 = urllib.request.Request(BASE + "/remaster",
                              data=json.dumps({"uid": j["uid"], "genre": "krautrock",
                                               "preview": True, "params": j2["params"]}).encode(),
                              headers={"Content-Type": "application/json"})
j3 = json.load(urllib.request.urlopen(req3, timeout=600))
print("remaster preview ok | lufs:", j3["master"]["lufs"],
      "tp:", j3["master"]["true_peak"])
print("chain:", j3["chain"][2])
