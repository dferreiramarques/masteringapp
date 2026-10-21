"""Teste de distorcao: senoide 1 kHz a -6 dBFS pela cadeia de masterizacao.
Numa cadeia limpa, harmonicos (>1 kHz) devem ficar muito abaixo do fundamental."""
import sys
import numpy as np

sys.path.insert(0, ".")
from app import analyze, render_master, default_profile, GENRES

sr = 44100
t = np.linspace(0, 8, sr * 8, False)
sine = 0.5 * np.sin(2 * np.pi * 1000 * t)  # -6 dBFS
# leve envolvente de "musica" para o limitador ter trabalho (amplitude modulada)
mod = 0.5 + 0.35 * np.sin(2 * np.pi * 0.5 * t)
sig = (sine * mod)[:, None] * np.array([1.0, 0.98])
# "sweeps" de energia: cortes breves
sig[::2] = 0.05 * sig[::2]  # alternar fraco/forte (metade das amostras baixas)

sig = sig.astype(np.float32)
a = analyze(sig, sr)
p = default_profile("indie")
x, moves, m = render_master(sig.copy(), sr, p, GENRES["indie"], a["spectrum"])

print(f"master: lufs={m['lufs']:.2f}  tp={m['true_peak']:.2f}")
sp = m["spectrum"]
print("harmnicos (dB relativo a 1 kHz, alvo: <= -45):")
for c in [2000, 3000, 4000, 5000, 8000, 10000]:
    v = sp.get(float(c))
    if v is not None:
        print(f"  {c} Hz: {v:+.1f} dB")
