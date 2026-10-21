"""Validacao do Maxximizer estilo L2: push + ceiling + IDR.
Casos: factory (tudo off), push max, IDR 100%, e teste THD com IDR alto."""
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, ".")
from app import analyze, render_master

sr = 44100
t = np.linspace(0, 12, sr * 12, False)
rng = np.random.default_rng(7)
music = 0.30 * np.sin(2 * np.pi * 110 * t) + 0.20 * np.sin(2 * np.pi * 550 * t)
music += 0.05 * rng.standard_normal(len(t))
kick_mask = (t % 0.5) < 0.03
music += rng.standard_normal(len(t)) * kick_mask * 0.8
x = np.stack([music, np.roll(music, 300)], axis=1).astype(np.float32)
x /= np.max(np.abs(x)) / 0.5

a = analyze(x, sr)
curve_c = {  # krautrock
    20: -22, 25: -14, 31.5: -8, 40: -4, 50: 1.0, 63: 4.0, 80: 5.0, 100: 5.5,
    125: 5.0, 160: 4.5, 200: 3.5, 250: 2.8, 315: 2.0, 400: 1.5, 500: 1.0,
    630: 0.3, 800: 0.0, 1000: 0.0, 1250: 0.6, 1600: 1.2, 2000: 1.2, 2500: 0.8,
    3150: 0.2, 4000: -0.5, 5000: -1.5, 6300: -2.5, 8000: -3.5, 10000: -4.5,
    12500: -5.5, 16000: -7.0, 20000: -9.0,
}

base = {"lufs_target": -9.0, "hp_hz": 22.0, "eq_strength": 0.0, "tape_drive": 4.0,
        "tape_mix": 0.4, "comp_threshold": -5.0, "comp_ratio": 1.6,
        "comp_attack": 25.0, "comp_release": 250.0, "low_shelf_freq": 90.0,
        "low_shelf_gain": 0.0, "high_shelf_freq": 9000.0, "high_shelf_gain": 0.0,
        "low_mono_hz": 280.0, "lim_ceiling_db": -1.0, "lim_push_db": 0.0,
        "lim_maxx": 0.0}

def run(tag, **kw):
    p = {**base, **kw}
    y, mv, m = render_master(x.copy(), sr, p, curve_c, a["spectrum"])
    sp = m["spectrum"]
    harm = [sp.get(float(c), -99) for c in (3000, 5000, 10000)]
    print(f"{tag:28s} lufs {m['lufs']:7.2f}  tp {m['true_peak']:6.2f}  "
          f"harm3k/5k/10k: {harm[0]:.0f}/{harm[1]:.0f}/{harm[2]:.0f} dB")

run("factory (tudo off)")
run("push +6", lim_push_db=6.0)
run("push +12", lim_push_db=12.0)
run("maxxizer 60%", lim_maxx=60.0)
run("push +6 + IDR 100% + ceiling -0.3", lim_push_db=6.0, lim_maxx=100.0,
    lim_ceiling_db=-0.3)
run("push +12 + IDR 100% + ceiling -0.3", lim_push_db=12.0, lim_maxx=100.0,
    lim_ceiling_db=-0.3)
