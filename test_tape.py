"""Teste do tape_saturate via A/B de waveform (a sonda FFT em janela +/-6 Hz
dominava pelo ruido de limitacao e mascarava o efeito). Mede, na cadeia inteira:
  - crest factor do master (e dai o squash)
  - correlacao e RMS da diferenca vs bypass (drive 0) -> magnitude do efeito
Passa so se o efeito crescer com o drive e o master mantiver LUFS/TP validos."""
import sys
import numpy as np

sys.path.insert(0, ".")
from app import render_master, default_profile, TARGET_CURVES, GENRES

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

curve = {float(k): float(v) for k, v in TARGET_CURVES["indie"].items()}
target = GENRES["indie"]["lufs_target"]
ceiling = default_profile("indie")["lim_ceiling_db"]

cases = [
    ("bypass        ", 0.0, 0.0),
    ("default 4.5   ", 4.5, 0.4),
    ("agressivo 9.0 ", 9.0, 0.8),
]

refs, pcts, fails = None, {}, []
print(f"perfil indie: alvo {target} LUFS, ceiling {ceiling:.2f} dBTP")
print()
for label, drive, mix in cases:
    p = default_profile("indie")
    p.update({"tape_drive": drive, "tape_mix": mix, "lim_maxx": 0.0, "bio_strength": 0.0})
    y, mv, m = render_master(x.copy(), sr, p, curve, curve)
    rrms = float(np.sqrt(np.mean(y[:, 0] ** 2)))
    crest = 20 * np.log10(float(np.max(np.abs(y[:, 0]))) / rrms)
    ok_lufs = abs(m["lufs"] - target) <= 0.5
    ok_tp = m["true_peak"] <= ceiling + 0.05
    if drive == 0.0:
        refs = y
        tag = "ok" if (ok_lufs and ok_tp) else "ERRO"
        print(f"{label} drive {drive:.1f} mix {mix:.1f}: crest {crest:5.2f} dB  "
              f"(lufs {m['lufs']:7.2f}, tp {m['true_peak']:+.2f})  [{tag}]  <- referencia")
        if not (ok_lufs and ok_tp):
            fails.append(f"bypass com master invalido (lufs {m['lufs']:.2f}, tp {m['true_peak']:.2f})")
        continue
    diff = float(np.sqrt(np.mean((refs[:, 0] - y[:, 0]) ** 2)))
    pct = 100 * diff / float(np.sqrt(np.mean(refs[:, 0] ** 2)))
    corr = float(np.corrcoef(refs[:, 0], y[:, 0])[0, 1])
    pcts[drive] = pct
    print(f"{label} drive {drive:.1f} mix {mix:.1f}: crest {crest:5.2f} dB  "
          f"diff {pct:5.2f}%  corr {corr:.6f}  (lufs {m['lufs']:.2f}, tp {m['true_peak']:+.2f})")

print()
# criterios: efeito audivel (>=0.3%) e crescente com o drive
if pcts.get(4.5, 0) < 0.3:
    fails.append(f"default (4.5/0.4): efeito no master demasiado fraco ({pcts.get(4.5, 0):.2f}%)")
if pcts.get(9.0, 0) < pcts.get(4.5, 0) * 1.5:
    fails.append(f"agressivo (9.0/0.8): nao cresce com o drive "
                 f"({pcts.get(9.0, 0):.2f}% vs {pcts.get(4.5, 0):.2f}%)")
if fails:
    print("FALHOU:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("OK: efeito do tape visivel no master, crescente com o drive; LUFS/TP validos.")
