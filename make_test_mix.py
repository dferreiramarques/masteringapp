import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt

sr = 44100
t = np.linspace(0, 30, sr * 30, False)
rng = np.random.default_rng(1)

n = rng.standard_normal(len(t)) * 0.05
bass = 0.4 * np.sin(2 * np.pi * 55 * t) + 0.2 * np.sin(2 * np.pi * 110 * t)
mids = 0.15 * np.sin(2 * np.pi * 400 * t) + 0.1 * np.sin(2 * np.pi * 2500 * t)

kick_mask = (t % 0.5) < 0.02
kick = filtfilt(*butter(2, 90 / (sr / 2), "lowpass"),
                rng.standard_normal(len(t)) * kick_mask * 3.0)

L = n + bass + mids + 0.6 * kick
R = n + 0.92 * bass + mids + 0.6 * kick + 0.03 * np.roll(n, 200)
x = np.stack([L, R], axis=1).astype(np.float32)
x = x / np.max(np.abs(x)) * 0.5  # -6 dBFS

sf.write(r"test_mix.wav", x, sr, subtype="PCM_24")
print("test_mix.wav ok:", x.shape)
