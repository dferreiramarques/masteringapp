"""Gera um mix curto de teste (8 s, stereo 16-bit, ~1.4 MB) para testes de UI."""
import numpy as np
import soundfile as sf

sr = 44100
t = np.linspace(0, 8, sr * 8, False)
rng = np.random.default_rng(3)
tone = (0.30 * np.sin(2 * np.pi * 110 * t) + 0.22 * np.sin(2 * np.pi * 220 * t) +
        0.18 * np.sin(2 * np.pi * 660 * t) + 0.10 * np.sin(2 * np.pi * 1320 * t))
music = tone + 0.05 * rng.standard_normal(len(t))
music += rng.standard_normal(len(t)) * ((t % 0.7) < 0.05) * 0.6
x = np.stack([music, np.roll(music, 260)], axis=1)
x = x / np.max(np.abs(x)) * 0.95
sf.write("test_mix_short.wav", x.astype(np.float32), sr, subtype="PCM_16")
print("ok")
