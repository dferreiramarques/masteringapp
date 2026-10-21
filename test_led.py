# -*- coding: utf-8 -*-
"""Teste do LED honesto: distorcao real adicionada pelos estagios saturantes."""
import sys
import numpy as np

sys.path.insert(0, ".")
from app import render_master, default_profile, TARGET_CURVES

sr = 44100
t = np.linspace(0, 12, sr * 12, False)
rng = np.random.default_rng(7)
tone = (0.30 * np.sin(2 * np.pi * 110 * t) +
        0.22 * np.sin(2 * np.pi * 220 * t) +
        0.18 * np.sin(2 * np.pi * 660 * t) +
        0.10 * np.sin(2 * np.pi * 1320 * t))
music = tone + 0.05 * rng.standard_normal(len(t))
music += rng.standard_normal(len(t)) * ((t % 0.77) < 0.04) * 0.7
x = np.stack([music, np.roll(music, 300)], axis=1).astype(np.float32)
x *= (10 ** (0.74 / 20)) / np.max(np.abs(x))     # TP = +0.74 dB como mistura quente

curve = TARGET_CURVES["indie"]

# (a) default limpo: tape_mix=0, IDR=0, exciter=0 -> LED deve dar 0%
p = default_profile("indie")
_, _, m = render_master(x.copy(), sr, p, curve, curve)
print(f"default (tape off): clip_pct={m['clip_pct']}  lufs={m['lufs']:.2f}  tp={m['true_peak']:.2f}")
assert m["clip_pct"] == 0.0, "default devia ter 0% de distorcao adicionada"

# (b) fita quente (o estado que o LED antigo media como 0%): deve acusar
p2 = default_profile("indie")
p2.update(tape_mix=0.40, tape_drive=4.5)
_, _, m2 = render_master(x.copy(), sr, p2, curve, curve)
print(f"fita 4.5dB/mix40%:   clip_pct={m2['clip_pct']}  lufs={m2['lufs']:.2f}  tp={m2['true_peak']:.2f}")
assert m2["clip_pct"] > 0.0, "LED antigo mostrava 0% aqui - agora devia acusar"

# (c) IDR 50 + exciter 30 + push forte: deve acusar tambem
p3 = default_profile("indie")
p3.update(lim_push_db=8.0, lim_maxx=50.0, exc_amount=30.0)
_, _, m3 = render_master(x.copy(), sr, p3, curve, curve)
print(f"IDR50+exc30+push8:   clip_pct={m3['clip_pct']}  lufs={m3['lufs']:.2f}  tp={m3['true_peak']:.2f}")
assert m3["clip_pct"] > 0.0, "distorcao estilistica devia aparecer no LED"

print("OK — LED honesto")
