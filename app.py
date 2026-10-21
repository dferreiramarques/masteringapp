"""
MasteringApp - backend (FastAPI)
Analisa uma mistura stereo, compara-a com curvas-alvo de genero e aplica uma
cadeia de masterizacao estilo "rock vintage", com perfis de parametros
ajustaveis (fine-tuning), re-masterizacao sem novo upload e pre-escuta rapida
(excerto de 20 s) para ajustes quase em tempo real.

Cadeia: HPF -> EQ corretivo -> saturacao de fita -> pre-ganho -> compressor lento
-> shelves tonais -> low-end mono (M/S) -> loudness para LUFS alvo com limitador
APENAS de ganho (look-ahead, sem waveshaping) -> TP garantido <= -1 dBTP.
"""

import io
import json
import sys
import uuid
import hashlib
from pathlib import Path
from urllib.parse import quote

import numpy as np
import scipy.signal as sp
import soundfile as sf
import pyloudnorm as pyln
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Body, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pedalboard import Compressor

# ---------------------------------------------------------------------------
# Caminhos: em script corre da pasta do ficheiro; no .exe (PyInstaller) os
# estáticos vêm do bundle (_MEIPASS) e os uploads/cache ficam ao lado do
# executável (persistem entre runs).
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    STATIC_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "static"
else:
    BASE_DIR = Path(__file__).resolve().parent
    STATIC_DIR = BASE_DIR / "static"

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

JOBS = {}  # uid -> {"orig": path, "name": str, "analysis": {...}, "genre": str}

# ---------------------------------------------------------------------------
# Bandas de 1/3 de oitava (centros ISO)
# ---------------------------------------------------------------------------
BAND_CENTERS = np.array([
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
    800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000,
    12500, 16000, 20000
])

# Curtvas-alvo (dB relativos ao valor em 1 kHz) para masters contemporaneos
TARGET_CURVES = {
    "indie": {
        20: -22, 25: -14, 31.5: -8, 40: -4, 50: 0.5, 63: 3.5, 80: 5.5,
        100: 6.0, 125: 5.0, 160: 4.0, 200: 3.0, 250: 2.5, 315: 1.5, 400: 1.0,
        500: 0.5, 630: 0.0, 800: 0.0, 1000: 0.0, 1250: 0.5, 1600: 1.0,
        2000: 1.0, 2500: 0.5, 3150: 0.0, 4000: -1.0, 5000: -2.0, 6300: -3.0,
        8000: -3.5, 10000: -4.0, 12500: -5.0, 16000: -6.0, 20000: -8.0,
    },
    "post-punk": {
        20: -24, 25: -16, 31.5: -10, 40: -5, 50: 0.0, 63: 3.0, 80: 4.0,
        100: 4.5, 125: 4.0, 160: 3.5, 200: 2.5, 250: 2.0, 315: 1.5, 400: 1.2,
        500: 0.8, 630: 0.3, 800: 0.0, 1000: 0.0, 1250: 0.8, 1600: 1.5,
        2000: 1.8, 2500: 1.5, 3150: 0.8, 4000: 0.0, 5000: -1.0, 6300: -2.0,
        8000: -3.0, 10000: -3.5, 12500: -4.5, 16000: -6.0, 20000: -8.0,
    },
    "krautrock": {
        20: -22, 25: -14, 31.5: -8, 40: -4, 50: 1.0, 63: 4.0, 80: 5.0,
        100: 5.5, 125: 5.0, 160: 4.5, 200: 3.5, 250: 2.8, 315: 2.0, 400: 1.5,
        500: 1.0, 630: 0.3, 800: 0.0, 1000: 0.0, 1250: 0.6, 1600: 1.2,
        2000: 1.2, 2500: 0.8, 3150: 0.2, 4000: -0.5, 5000: -1.5, 6300: -2.5,
        8000: -3.5, 10000: -4.5, 12500: -5.5, 16000: -7.0, 20000: -9.0,
    },
    "pop": {
        20: -22, 25: -15, 31.5: -9, 40: -4.5, 50: 1.0, 63: 4.0, 80: 6.0,
        100: 6.0, 125: 5.0, 160: 4.5, 200: 3.5, 250: 3.0, 315: 2.0, 400: 1.4,
        500: 0.9, 630: 0.3, 800: 0.0, 1000: 0.0, 1250: 0.6, 1600: 1.2,
        2000: 1.4, 2500: 1.2, 3150: 0.6, 4000: -0.5, 5000: -1.5, 6300: -2.8,
        8000: -3.6, 10000: -4.0, 12500: -5.0, 16000: -6.0, 20000: -8.0,
    },
    "electronic": {
        20: -18, 25: -10, 31.5: -4, 40: 0.0, 50: 2.0, 63: 4.0, 80: 6.0,
        100: 6.5, 125: 6.0, 160: 4.5, 200: 2.5, 250: 2.2, 315: 1.8, 400: 1.2,
        500: 0.7, 630: 0.2, 800: 0.0, 1000: 0.0, 1250: 0.8, 1600: 1.4,
        2000: 1.5, 2500: 1.2, 3150: 0.6, 4000: -0.3, 5000: -1.5, 6300: -2.5,
        8000: -3.4, 10000: -4.0, 12500: -5.0, 16000: -6.5, 20000: -8.5,
    },
    "acoustic": {
        20: -26, 25: -18, 31.5: -12, 40: -6, 50: -1.0, 63: 2.0, 80: 3.5,
        100: 4.5, 125: 4.5, 160: 4.0, 200: 3.5, 250: 3.0, 315: 2.4, 400: 1.8,
        500: 1.2, 630: 0.5, 800: 0.0, 1000: 0.0, 1250: 0.3, 1600: 0.8,
        2000: 0.8, 2500: 0.5, 3150: 0.0, 4000: -0.5, 5000: -1.2, 6300: -2.0,
        8000: -3.0, 10000: -3.8, 12500: -4.8, 16000: -6.0, 20000: -8.0,
    },
    "ambient": {
        20: -24, 25: -16, 31.5: -10, 40: -5, 50: 0.0, 63: 2.5, 80: 3.5,
        100: 4.0, 125: 3.5, 160: 3.0, 200: 2.2, 250: 1.8, 315: 1.2, 400: 0.8,
        500: 0.4, 630: 0.1, 800: 0.0, 1000: 0.0, 1250: 0.3, 1600: 0.6,
        2000: 0.5, 2500: 0.2, 3150: -0.3, 4000: -1.0, 5000: -2.0, 6300: -3.0,
        8000: -4.0, 10000: -5.0, 12500: -6.0, 16000: -7.5, 20000: -9.0,
    },
    "noise": {
        20: -20, 25: -12, 31.5: -6, 40: -2, 50: 0.5, 63: 2.5, 80: 3.5,
        100: 3.5, 125: 3.0, 160: 2.8, 200: 2.5, 250: 2.4, 315: 2.2, 400: 2.0,
        500: 1.6, 630: 1.0, 800: 0.4, 1000: 0.0, 1250: 0.4, 1600: 0.8,
        2000: 1.0, 2500: 0.8, 3150: 0.4, 4000: -0.5, 5000: -1.5, 6300: -2.5,
        8000: -3.5, 10000: -4.5, 12500: -5.5, 16000: -7.0, 20000: -9.0,
    },
}

GENRES = {
    "indie": {
        "label": "Indie Rock",
        "lufs_target": -9.0,
        "tape_drive": 4.5, "tape_mix": 0.40,
        "comp_threshold": -5, "comp_ratio": 1.6, "comp_attack": 25, "comp_release": 250,
        "low_mono_hz": 240, "hp_hz": 24,
        "low_shelf_freq": 90, "low_shelf_gain": 1.5,
        "high_shelf_freq": 9000, "high_shelf_gain": 1.5,
    },
    "post-punk": {
        "label": "Post-Punk",
        "lufs_target": -9.0,
        "tape_drive": 5.5, "tape_mix": 0.45,
        "comp_threshold": -4, "comp_ratio": 1.8, "comp_attack": 30, "comp_release": 220,
        "low_mono_hz": 260, "hp_hz": 26,
        "low_shelf_freq": 90, "low_shelf_gain": 1.0,
        "high_shelf_freq": 9000, "high_shelf_gain": 2.0,
    },
    "krautrock": {
        "label": "Krautrock / Vintage",
        "lufs_target": -10.0,
        "tape_drive": 6.5, "tape_mix": 0.50,
        "comp_threshold": -6, "comp_ratio": 1.4, "comp_attack": 40, "comp_release": 300,
        "low_mono_hz": 280, "hp_hz": 22,
        "low_shelf_freq": 90, "low_shelf_gain": 2.0,
        "high_shelf_freq": 9000, "high_shelf_gain": 1.0,
    },
    "pop": {
        "label": "Pop",
        "lufs_target": -8.0,
        "tape_drive": 3.5, "tape_mix": 0.35,
        "comp_threshold": -5, "comp_ratio": 2.2, "comp_attack": 15, "comp_release": 180,
        "low_mono_hz": 200, "hp_hz": 24,
        "low_shelf_freq": 100, "low_shelf_gain": 1.2,
        "high_shelf_freq": 9000, "high_shelf_gain": 2.5,
    },
    "electronic": {
        "label": "Electrónica",
        "lufs_target": -8.0,
        "tape_drive": 3.0, "tape_mix": 0.30,
        "comp_threshold": -6, "comp_ratio": 2.5, "comp_attack": 5, "comp_release": 120,
        "low_mono_hz": 200, "hp_hz": 26,
        "low_shelf_freq": 80, "low_shelf_gain": 1.0,
        "high_shelf_freq": 9500, "high_shelf_gain": 2.0,
    },
    "acoustic": {
        "label": "Acústico / Cantor-autor",
        "lufs_target": -11.0,
        "tape_drive": 3.0, "tape_mix": 0.30,
        "comp_threshold": -6, "comp_ratio": 1.3, "comp_attack": 20, "comp_release": 260,
        "low_mono_hz": 220, "hp_hz": 20,
        "low_shelf_freq": 110, "low_shelf_gain": 1.2,
        "high_shelf_freq": 10000, "high_shelf_gain": 1.8,
    },
    "ambient": {
        "label": "Experimental / Ambiental",
        "lufs_target": -14.0,
        "tape_drive": 2.0, "tape_mix": 0.25,
        "comp_threshold": -10, "comp_ratio": 1.2, "comp_attack": 80, "comp_release": 400,
        "low_mono_hz": 160, "hp_hz": 18,
        "low_shelf_freq": 100, "low_shelf_gain": 1.0,
        "high_shelf_freq": 11000, "high_shelf_gain": 0.5,
    },
    "noise": {
        "label": "Noise / Drone",
        "lufs_target": -8.0,
        "tape_drive": 8.0, "tape_mix": 0.70,
        "comp_threshold": -2, "comp_ratio": 2.5, "comp_attack": 10, "comp_release": 150,
        "low_mono_hz": 320, "hp_hz": 28,
        "low_shelf_freq": 90, "low_shelf_gain": 1.5,
        "high_shelf_freq": 8000, "high_shelf_gain": 1.5,
    },
}

CATEGORIES = [
    ("graves (63-160 Hz)", 63, 160),
    ("low-mids (200-400 Hz)", 200, 400),
    ("mids (500-800 Hz)", 500, 800),
    ("presenca (1-3 kHz)", 1000, 3150),
    ("agudos (4-8 kHz)", 4000, 8000),
    ("ar (10 kHz+)", 10000, 16000),
]

# ---------------------------------------------------------------------------
# Perfis de masterizacao (defaults por genero + overrides do usuario)
# ---------------------------------------------------------------------------
LIMITS = {
    "lufs_target": (-20.0, -6.0),
    "hp_hz": (16.0, 60.0),
    "eq_strength": (0.0, 1.5),
    "tape_drive": (0.0, 12.0),
    "tape_mix": (0.0, 1.0),
    "comp_threshold": (-20.0, 0.0),
    "comp_ratio": (1.0, 4.0),
    "comp_attack": (1.0, 100.0),
    "comp_release": (50.0, 600.0),
    "low_shelf_freq": (40.0, 160.0),
    "low_shelf_gain": (-4.0, 4.0),
    "high_shelf_freq": (4000.0, 14000.0),
    "high_shelf_gain": (-4.0, 4.0),
    "low_mono_hz": (80.0, 400.0),
    "st_width": (0.0, 2.0),
    "verb_mix": (0.0, 100.0),   # % de ambiencia (reverb de mix); default 0 (off)
    "lim_ceiling_db": (-3.0, -0.01),
    "lim_push_db": (0.0, 15.0),
    "lim_maxx": (0.0, 100.0),
    "bio_strength": (0.0, 100.0),
    "exc_amount": (0.0, 100.0),
}
PARAM_KEYS = ["lufs_target", "hp_hz", "eq_strength", "tape_drive", "tape_mix",
              "comp_threshold", "comp_ratio", "comp_attack", "comp_release",
              "low_shelf_freq", "low_shelf_gain", "high_shelf_freq",
              "high_shelf_gain", "low_mono_hz", "st_width", "verb_mix",
              "lim_ceiling_db", "lim_push_db", "lim_maxx",
              "bio_strength", "exc_amount"]

PROFILE_DEFAULTS = {"eq_strength": 1.0, "lim_ceiling_db": -1.0,
                    "lim_push_db": 0.0, "lim_maxx": 0.0,
                    "bio_strength": 0.0, "exc_amount": 0.0,
                    "st_width": 1.0, "verb_mix": 0.0}


def default_profile(genre):
    g = GENRES[genre]
    p = {k: float(g[k]) for k in PARAM_KEYS if k in g}
    for k, v in PROFILE_DEFAULTS.items():
        p[k] = float(v)
    # default limpo: saturacao de fita desligada (o gozo fica para o user ativar
    # por estilo); exciter/IDR ja nascem a 0
    p["tape_mix"] = 0.0
    return p


def merge_profile(genre, overrides):
    p = default_profile(genre)
    for k, v in (overrides or {}).items():
        if k in LIMITS and v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            lo, hi = LIMITS[k]
            p[k] = min(hi, max(lo, fv))
    return p


def build_chain_text(p, moves):
    txt = [
        f"HPF {p['hp_hz']:.0f} Hz",
        f"EQ corretivo (intensidade {int(p['eq_strength'] * 100)}%; {len(moves)} bandas)",
    ]
    if p.get("bio_strength", 0.0) > 0:
        txt.append(f"Mitigação biológica {p['bio_strength']:.0f}% "
                   "(2–5 kHz / sibilância / boxy / boomy)")
    if p.get("exc_amount", 0.0) > 0:
        txt.append(f"Exciter harmónico {p['exc_amount']:.0f}% "
                   "(réplicas de 2.ª/3.ª harmónica na banda 2.8–8.5 kHz)")
    txt += [
        f"Saturacao de fita (drive {p['tape_drive']:.1f} dB, mix {int(p['tape_mix'] * 100)}%)",
        f"Compressor {p['comp_ratio']:.1f}:1, atk {p['comp_attack']:.0f} ms, rel {p['comp_release']:.0f} ms",
        f"Low shelf {p['low_shelf_freq']:.0f} Hz {p['low_shelf_gain']:+.1f} dB",
        f"High shelf {p['high_shelf_freq']:.0f} Hz {p['high_shelf_gain']:+.1f} dB",
    ]
    vm = p.get("verb_mix", 0.0)
    if vm > 0.0:
        txt.append(f"Ambiência {vm:.0f}% (reverb de mix de rescate: sala curta, "
                   "pre-delay, graves/agudos filtrados — só para colar)")
    txt += [
        f"Low-end mono < {p['low_mono_hz']:.0f} Hz",
    ]
    if abs(p.get("st_width", 1.0) - 1.0) > 1e-6:
        txt.append(f"Largura de imagem {int(p.get('st_width', 1.0) * 100)}% (M/S; side escalado)")
    txt += [
        f"LUFS alvo {p['lufs_target']:.1f} + push {p['lim_push_db']:.1f} dB",
        f"Maximizer estilo L2: ceiling {p['lim_ceiling_db']:.2f} dBTP, Maxximizer {p['lim_maxx']:.0f}%",
    ]
    return txt


# ---------------------------------------------------------------------------
# Biquads RBJ (devolvem (b, a) normalizados a a0 = 1)
# ---------------------------------------------------------------------------
def rbj_peak(sr, f0, gain_db, q=2.0):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    b = np.array([1 + alpha * A, -2 * cw, 1 - alpha * A])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def rbj_lowshelf(sr, f0, gain_db, slope=1.0):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / 2 * np.sqrt((A + 1 / A) * (1 / slope - 1) + 2)
    tsa = 2 * np.sqrt(A) * alpha
    b = np.array([A * ((A + 1) - (A - 1) * cw + tsa),
                  2 * A * ((A - 1) - (A + 1) * cw),
                  A * ((A + 1) - (A - 1) * cw - tsa)])
    a = np.array([(A + 1) + (A - 1) * cw + tsa,
                  -2 * ((A - 1) + (A + 1) * cw),
                  (A + 1) + (A - 1) * cw - tsa])
    return b / a[0], a / a[0]


def rbj_highshelf(sr, f0, gain_db, slope=1.0):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / 2 * np.sqrt((A + 1 / A) * (1 / slope - 1) + 2)
    tsa = 2 * np.sqrt(A) * alpha
    b = np.array([A * ((A + 1) + (A - 1) * cw + tsa),
                  -2 * A * ((A - 1) + (A + 1) * cw),
                  A * ((A + 1) + (A - 1) * cw - tsa)])
    a = np.array([(A + 1) - (A - 1) * cw + tsa,
                  2 * ((A - 1) - (A + 1) * cw),
                  (A + 1) - (A - 1) * cw - tsa])
    return b / a[0], a / a[0]


def rbj_highpass(sr, f0, q=0.7071):
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    b = np.array([(1 + cw) / 2, -(1 + cw), (1 + cw) / 2])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def rbj_lowpass(sr, f0, q=0.7071):
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    b = np.array([(1 - cw) / 2, 1 - cw, (1 - cw) / 2])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def aural_exciter(x, sr, amount):
    """Exciter harmonico: gera replicas (2.a/3.a harmonicas) do conteudo da banda
    dos agudos (2.8–8.5 kHz) por saturacao suave e mistura de volta SO os produtos
    harmonicos (sat − banda), nunca o sinal saturado em si. Brilho 'harmonizado'
    em frequency-replicas, sem tocar o corpo e sem estilo; amount 0..1."""
    if amount <= 0.0:
        return x
    hp, ha = rbj_highpass(sr, 2800.0, q=0.9)
    lp, la = rbj_lowpass(sr, 8500.0, q=0.7)
    band = apply_sos(x, [(hp, ha), (lp, la)]).astype(np.float64)
    T = 10 ** (-12.0 / 20)                       # joelho a -12 dBFS dentro da banda
    K = 18.0
    absb = np.abs(band)
    over = np.maximum(absb - T, 0.0)
    sat = np.where(over > 0.0, T + over / (1.0 + over * K), absb)
    harm = np.sign(band) * sat - band            # replica harmonica apenas
    return x + harm * (0.8 * amount)



def apply_sos(x, filters):
    rows = [[*b, *a] for b, a in filters]
    return sp.sosfilt(np.array(rows), x, axis=0).astype(np.float32)


# ---------------------------------------------------------------------------
# Analise
# ---------------------------------------------------------------------------
def true_peak_db(x, sr):
    peak = 0.0
    for c in range(x.shape[1]):
        up = sp.resample_poly(x[:, c], 4, 1, window=("kaiser", 8.0))
        peak = max(peak, float(np.max(np.abs(up))))
    return 20 * np.log10(peak + 1e-12)


def integrated_lufs(x, sr):
    meter = pyln.Meter(sr)
    try:
        return float(meter.integrated_loudness(x))
    except Exception:
        return -70.0


def short_term_lra(x, sr):
    meter = pyln.Meter(sr, block_size=3.0)
    hop, win = sr, 6 * sr   # janela de 6 s (2 blocos) para o gating funcionar
    vals = []
    for start in range(0, max(1, x.shape[0] - win + 1), hop):
        w = x[start:start + win]
        if w.shape[0] < win:
            w = np.pad(w, ((0, win - w.shape[0]), (0, 0)))
        try:
            l = meter.integrated_loudness(w)
            if np.isfinite(l):
                vals.append(l)
        except Exception:
            pass
    if len(vals) < 3:
        return None
    vals = np.array(vals)
    return float(np.percentile(vals, 95) - np.percentile(vals, 10))


def stereo_correlation(x):
    mc = x[:, 0] - x[:, 0].mean()
    sc = x[:, 1] - x[:, 1].mean()
    num = float(np.sum(mc * sc))
    den = np.sqrt(np.sum(mc ** 2) * np.sum(sc ** 2)) + 1e-12
    return float(np.clip(num / den, -1.0, 1.0))


def band_spectrum(x, sr):
    """Energia em dB por banda de 1/3 de oitava, relativa ao valor em 1 kHz."""
    mono = x.mean(axis=1)
    nfft = 8192 if sr <= 64000 else 16384
    f, _, Z = sp.stft(mono, fs=sr, nperseg=nfft, noverlap=nfft // 2,
                      window="hann", padded=False, boundary=None)
    total = (np.abs(Z) ** 2).sum(axis=1)
    edges = np.sqrt(BAND_CENTERS[:-1] * BAND_CENTERS[1:])
    edges = np.insert(edges, 0, 10.0)
    edges = np.append(edges, sr / 2 + 10)
    out = {}
    for i, c in enumerate(BAND_CENTERS):
        mask = (f >= edges[i]) & (f < edges[i + 1])
        e = float(total[mask].sum()) + 1e-20
        out[float(c)] = 10 * np.log10(e)
    ref = out.get(1000.0)
    if ref is not None:
        out = {k: v - ref for k, v in out.items()}
    return out


def find_anchor(x, sr, seconds=20):
    """Inicio do excerto mais energetico (janelas sem sobreposicao)."""
    win = int(sr * seconds)
    n = x.shape[0] // win
    if n <= 0:
        return 0, x.shape[0]
    sums = [float(np.mean(x[i * win:(i + 1) * win] ** 2)) for i in range(n)]
    best = int(np.argmax(sums))
    return best * win, best * win + win


def analyze(x, sr):
    a0, a1 = find_anchor(x, sr)
    return {
        "lufs": integrated_lufs(x, sr),
        "true_peak": true_peak_db(x, sr),
        "lra": short_term_lra(x, sr),
        "corr": stereo_correlation(x),
        "spectrum": band_spectrum(x, sr),
        "anchor": [int(a0), int(a1)],
        "sr": sr,
    }


def spectral_moves(spec, curve, strength=1.0, max_moves=6):
    """Correcoes (centro, ganho dB) quando a mistura desvia da curva-alvo."""
    moves = []
    for c in BAND_CENTERS:
        c = float(c)
        if 150 <= c <= 8000 and c in curve and c in spec:
            d = spec[c] - curve[c]
            if d > 2.5:
                moves.append((c, -min(4.0, (d - 2.0) * 0.8) * strength))
            elif d < -3.5:
                moves.append((c, min(2.0, (abs(d) - 3.0) * 0.5) * strength))
    moves = [(c, g) for c, g in moves if abs(g) > 0.05]
    moves.sort(key=lambda m: -abs(m[1]))
    return moves[:max_moves]


def build_suggestions(spec, curve):
    sugg = []
    for label, lo, hi in CATEGORIES:
        diffs = [spec[c] - curve[c] for c in BAND_CENTERS
                 if lo <= c <= hi and float(c) in spec and float(c) in curve]
        if not diffs:
            continue
        diff = float(np.mean(diffs))
        a = abs(diff)
        if a < 1.5:
            msg = "equilibrada com o alvo do genero."
        elif diff > 0:
            msg = f"acima do alvo (+{round(diff, 1)} dB). Sugestao: reduzir {round(min(4, (a - 1.5) * 0.8), 1)} dB nesta zona."
        else:
            msg = f"abaixo do alvo ({round(diff, 1)} dB). Sugestao: reforcar {round(min(2.5, (a - 1.5) * 0.6), 1)} dB nesta zona."
        sugg.append({"cat": label, "diff": round(diff, 1), "msg": msg})
    return sugg


# ---------------------------------------------------------------------------
# F2.1/F2.2/F2.3 — biologia do ouvido, interpretacao tecnica, dinamica
# ---------------------------------------------------------------------------
BIO_ZONES = {
    "boomy": [40.0, 50.0, 63.0, 80.0, 100.0, 125.0],
    "boxy":  [200.0, 250.0, 315.0, 400.0, 500.0],
    "harsh": [2000.0, 2500.0, 3150.0, 4000.0],
    "sibil": [5000.0, 6300.0, 8000.0, 10000.0],
}
BIO_EQ = {  # (centro do corte, Q) por zona
    "boomy": (90.0, 3.0),
    "boxy":  (350.0, 3.5),
    "harsh": (3150.0, 4.0),
    "sibil": (7300.0, 4.0),
}
BIO_LABELS = {
    "boomy": "Boomy — excesso de graves/subs (<125 Hz)",
    "boxy": "Boxy — excesso de médios 'caixa' (200–500 Hz)",
    "harsh": "Harsh — agudos duros para o ouvido (2–5 kHz)",
    "sibil": "Sibilância (5–10 kHz)",
}


def psycho_indices(spec, curve):
    """F2.1: excesso medio (dB) por zona biologica, relativo a curva-alvo."""
    idx = {}
    for k, bands in BIO_ZONES.items():
        ds = [spec[b] - curve[b] for b in bands if b in spec and b in curve]
        idx[k] = float(np.mean(ds)) if ds else 0.0
    return idx


def tech_labels(idx):
    """F2.2: interpretacao tecnica — rotulos quando o desvio 'soa mal'."""
    out = []
    lims = {"boomy": 2.5, "boxy": 2.5, "harsh": 1.8, "sibil": 2.0}
    for k, lim in lims.items():
        e = idx.get(k, 0.0)
        if e > lim:
            out.append({"key": k, "label": BIO_LABELS[k], "db": round(e, 1),
                        "level": "excesso"})
        elif e < -2.5 and k in ("harsh", "sibil"):
            out.append({"key": k, "label": f"{BIO_LABELS[k]} — deficit",
                        "db": round(e, 1), "level": "deficit"})
    return out


def bio_moves(idx, strength):
    """F2.1: cortes ergonomicos (centro, gain, Q) escalados por bio_strength 0..1.
    Aplicam-se so as zonas com excesso; mesmo estilo: corte statico, sem
    waveshaping (zero distorcao harmonica)."""
    mv = []
    for k, (f, q) in BIO_EQ.items():
        e = idx.get(k, 0.0)
        if e > 1.0:
            g = -min(4.0, (e - 1.0) * 0.6) * strength
            if g < -0.15:
                mv.append((f, round(g, 2), q))
    return mv


def auto_dynamics(analysis, p):
    """F2.3: decisao de dinâmica (esmagar vs dar espaco) a partir do LRA/TP."""
    o, labels = {}, []
    if analysis.get("true_peak", -99) > -0.2:
        labels.append(("TP entrada",
                       f"TP de entrada {analysis['true_peak']:.2f} dB — exporta a mistura "
                       "com headroom (<= -3 dB), o master pode ficar limitado a mais"))
    lra = analysis.get("lra")
    if lra is not None:
        if lra < 3.5:
            o["comp_ratio"] = max(1.0, p["comp_ratio"] * 0.85)
            o["comp_threshold"] = min(0.0, p["comp_threshold"] + 1.5)
            o["comp_release"] = min(600.0, p["comp_release"] * 1.25)
            labels.append((f"LRA {lra:.1f}", "master já muito comprimido — soltar a compressão"))
        elif lra > 8.5:
            o["comp_threshold"] = max(-20.0, p["comp_threshold"] - 2.0)
            o["comp_ratio"] = min(4.0, p["comp_ratio"] + 0.25)
            labels.append((f"LRA {lra:.1f}", "mistura muito dinâmica — acrescentar densidade"))
        else:
            labels.append((f"LRA {lra:.1f}", "dinâmica equilibrada — preservada"))
    return o, labels


def auto_profile(genre, analysis, current=None):
    """F2 'Auto': decisão (bio + dinamica) sobre a mistura.
    `current` = perfil EM USO (sliders): o auto ajusta SOBRE ele — respeita
    escolhas manuais (não volta ao default do género). Sem `current`, usa o
    perfil puro do género. bio_strength: se o user já ativou, fica como está
    (auto nunca reduz); se está off, ativa a 50%."""
    p = merge_profile(genre, current) if current else default_profile(genre)
    dyn_o, dyn_labels = auto_dynamics(analysis, p)
    bio = p.get("bio_strength", 0.0)
    p = {**p, **dyn_o, "bio_strength": bio if bio > 0 else 50.0}
    idx = psycho_indices(analysis["spectrum"], TARGET_CURVES[genre])
    return p, idx, dyn_labels


# ---------------------------------------------------------------------------
# Cadeia de masterizacao
# ---------------------------------------------------------------------------
def tape_saturate(x, drive_db, mix):
    """Rode de fita APENAS nos picos (acima de -6 dBFS): slope unitaria no corpo
    do sinal (corpo e silencios intactos -> zero distorcao harmonica fora dos
    transcendentes), joelho suave nos picos; drive escala a dureza, mix cruza.
    Antes usava tanh na forma de onda toda -> satura brutalmente p/ misturas
    quentes (TP ~ 0 dB) e enchia o master de harmonicos."""
    T = 10 ** (-6.0 / 20)                    # joelho fixo em -6 dBFS
    g = max(drive_db, 0.0) / 12.0
    K = 20.0 * g                             # drive 0 -> K=0 -> identidade
    absx = np.abs(x)
    over = np.maximum(absx - T, 0.0)
    soft = np.where(over > 0.0, T + over / (1.0 + over * K), absx)
    y = np.sign(x) * soft
    return mix * y + (1 - mix) * x


def peak_limit(x, sr, ceiling=10 ** (-1.0 / 20), lookahead_ms=4.0, release_ms=80.0):
    """Limitador look-ahead APENAS de ganho (sem waveshaping => sem distorcao harmonica),
    operando no envelope TRUE PEAK (sinal 4x oversampled): limita os picos
    intersample reais, nao so os por-amostra. Ganho suavizado numa janela A FRENTE
    (pre-distorcao evita saltos de ganho por-amostra), release gradual.
    Antes usava o envelope por-amostra + um fator de margem global no chamador:
    picos intersample de material limitado a ferro (amostras alternadas em fs/2)
    forcavam over-limit de uma tacada seguido de re-ganho global -> dinamica
    esmagada e crest capaz de sair igual para inputs distintos."""
    from scipy.ndimage import minimum_filter1d, maximum_filter1d
    # pico verdadeiro (oversampled) associado a cada amostra original: max do
    # up-sample num bloco de 4 + vizinhos +-1 (a reconstrucao mistura vizinhos)
    envup = None
    for c in range(x.shape[1]):
        up = np.abs(sp.resample_poly(x[:, c], 4, 1, window=("kaiser", 8.0)))
        envup = up if envup is None else np.maximum(envup, up)
    pad = np.concatenate([np.zeros(4), envup, np.zeros(4)])
    idx = np.arange(x.shape[0])
    base = 4 * idx
    env = np.maximum.reduce([pad[base + k] for k in range(9)])   # 4*(i-1) .. 4*(i+1)
    need = np.minimum(1.0, ceiling / np.maximum(env, 1e-12))     # requisito instantaneo
    la = max(3, int(sr * lookahead_ms / 1000.0))
    rel = max(1, int(sr * release_ms / 1000.0))
    # requisito adiantado 'la' amostras, minimizado numa janela de ataque
    need_shift = np.concatenate([np.full(la, 1.0), need])[: need.shape[0]]
    g_att = minimum_filter1d(need_shift, size=la, mode="nearest")   # ataque (antecedência)
    g = maximum_filter1d(g_att, size=rel, mode="nearest")           # release gradual
    # suaviza a borda de ataque (janela a frente ~2 ms) -> sem 'zipper' de ganho
    att_s = max(3, int(sr * 0.002))
    g = minimum_filter1d(g, size=att_s, mode="nearest", origin=-att_s // 2)
    g = np.minimum(g, need)                                         # nunca viola o requisito
    return x * g[:, None]


def mid_side_low_mono(x, sr, cutoff):
    mid = x[:, 0] + x[:, 1]
    side = x[:, 0] - x[:, 1]
    bp, ap = rbj_highpass(sr, cutoff)
    rows = np.array([[*bp, *ap], [*bp, *ap]])  # cascata de 2 -> 12 dB/oct
    side_f = sp.sosfilt(rows, side, axis=0)
    return np.stack([(mid + side_f) / 2, (mid - side_f) / 2], axis=1)


def mix_ambience(x, sr, mix, decay_s=0.9, predelay_ms=24.0,
                 damp_hz=7000.0, hp_hz=220.0, seed=1234):
    """Ambiência de masterização ("reverb de mix" de rescate, estágio 5b).

    Convolução FFT com um IR de sala sintético, CURTO e amortecido. Não serve
    para "dar ambiente" — existe só para colar/difundir uma mistura que vem
    muito seca e separada (prática comum de depth em masterização a mix de
    5–15%; o slider tem teto interno de 20%). O IR tem:
      - pre-delay ~24 ms -> o transiente/punch da imagem não é borrado;
      - decay exponencial curto (~0.9 s até -60 dB), tipo sala pequena/média;
      - agudos amortecidos (absorção da sala) e graves fora (hp) -> a chuva de
        "s" não ganha cauda e o low-end nunca embacia (o low-mono seguinte
        também garante mono por baixo do cutoff);
      - canais esquerdo/direito descorrelacionados -> difunde sem estreitar.

    O wet é normalizado em RMS contra a entrada e escalado por `mix` (0..0.2),
    i.e. equal-power simplificado: wet ao mesmo nível RMS do dry a mix=1.
    Saída com o MESMO comprimento da entrada (a cauda final é cortada — só
    afeta os últimos ~0.9 s do ficheiro e evita desalinhar A/B e previews).
    """
    if mix <= 0.0:
        return x
    n = x.shape[0]
    pre = max(int(sr * predelay_ms / 1000.0), 1)
    tail = max(int(sr * decay_s), 4)
    ir_n = pre + tail
    ir = np.zeros((2, ir_n))
    rng = np.random.default_rng(seed)          # IR determinístico entre renders
    bl, al = rbj_lowpass(sr, damp_hz, 0.9)     # damping dos agudos
    bh, ah = rbj_highpass(sr, hp_hz, 0.8)      # graves fora do IR
    env = np.exp(-6.9078 * np.arange(tail) / max(tail - 1.0, 1.0))  # -60 dB fim
    for ch in range(2):
        noise = rng.standard_normal(ir_n)
        noise = sp.lfilter(bl, al, noise)
        noise = sp.lfilter(bl, al, noise)      # cascata 2x -> densidade sala
        noise = sp.lfilter(bh, ah, noise)
        ir[ch, pre:] = noise[pre:] * env
    wet = np.empty_like(x)
    for ch in range(2):
        wet[:, ch] = sp.fftconvolve(x[:, ch], ir[ch])[:n]
    rd = float(np.sqrt(np.mean(x * x)))
    rw = float(np.sqrt(np.mean(wet * wet)))
    if rw > 1e-12 and rd > 1e-12:
        wet *= rd / rw
    return x + (mix * wet)


def idr_over(x, C_lin, s):
    """Maxximizer (estilo IDR do Waves L2): soft-clip UMA passada, apenas nos
    excessos acima do ceiling. s = amount (0..1): quanto maior, mais duro o joelho.
    Amostras abaixo do ceiling ficam intactas (slope unitaria, sem distorcao alai)."""
    absx = np.abs(x)
    over = np.maximum(absx - C_lin, 0.0)
    soft = np.where(over > 0.0,
                    C_lin + over / (1.0 + over * (2.0 + 40.0 * s)),
                    absx)
    return np.sign(x) * soft


def render_master(x, sr, p, curve, spectrum):
    x = x.astype(np.float64)

    moves = spectral_moves(spectrum, curve, p["eq_strength"])

    # 1) HPF  2) EQ corretivo
    fis = [rbj_highpass(sr, p["hp_hz"])] + [
        rbj_peak(sr, c, gain, 2.2) for c, gain in moves]
    x = apply_sos(x, fis)

    # 1b) F2.1 mitigação biológica: cortes nas zonas agressivas p/ o ouvido,
    #     escalados por bio_strength; evita bandas ja tocadas pelo EQ corretivo
    biov = p.get("bio_strength", 0.0) / 100.0
    if biov > 0.0:
        idx0 = psycho_indices(spectrum, curve)
        bio = bio_moves(idx0, biov)
        taken = {c for c, _ in moves}
        for f, g, q in bio:
            if not any(abs(np.log((f + 1e-6) / (c + 1e-6))) < 0.25 for c in taken):
                fis = [rbj_peak(sr, f, g, q)]
                x = apply_sos(x, fis)
                taken.add(f)

    # 3) saturacao de fita (slope unitaria, comprime so os picos)
    sat_pct = 0.0                     # distorcao real adicionada (p/ o LED)
    if p["tape_mix"] > 0.0:
        pre = x.copy()
        x = tape_saturate(x, p["tape_drive"], p["tape_mix"])
        sat_pct += float(np.mean(np.abs(x - pre) > 0.01)) * 100.0

    # 3b) pre-ganho leve p/ o compressor trabalhar sempre no mesmo nivel
    lin = integrated_lufs(x, sr)
    if np.isfinite(lin) and lin > -68:
        x *= 10 ** ((p["lufs_target"] + 5.0 - lin) / 20)

    # 4) compressao lenta "glue"
    comp = Compressor(threshold_db=p["comp_threshold"], ratio=p["comp_ratio"],
                      attack_ms=p["comp_attack"], release_ms=p["comp_release"])
    x = comp(x.astype(np.float32), sr).astype(np.float64)

    # 5) shelves tonais largos
    x = apply_sos(x, [rbj_lowshelf(sr, p["low_shelf_freq"], p["low_shelf_gain"]),
                      rbj_highshelf(sr, p["high_shelf_freq"], p["high_shelf_gain"])])

    # 5b) ambiência (reverb de mix de rescate; default desligado): só para
    #     colar uma mistura muito seca e separada. Mix interno = slider/100
    #     * 0.2 -> teto de 20% mesmo a 100% (prática de depth = % baixas).
    #     Vai ANTES do low-mono para os graves do wet ficarem mono também.
    vmix = p.get("verb_mix", 0.0) / 100.0
    if vmix > 0.0:
        x = mix_ambience(x, sr, vmix * 0.2)

    # 6) low-end mono
    x = mid_side_low_mono(x, sr, p["low_mono_hz"])

    # 6a) largura da imagem (M/S): escala o sinal side; 1.0 = neutro
    # funciona no MID real (soma preservada), so muda a diferenca -> o low-end
    # mono fica intacto porque o side < cutoff ja e quase zero
    wid = p.get("st_width", 1.0)
    if abs(wid - 1.0) > 1e-6:
        mid = (x[:, 0] + x[:, 1]) / 2.0
        side = (x[:, 0] - x[:, 1]) / 2.0
        x = np.stack([mid + wid * side, mid - wid * side], axis=1)

    # 6b) exciter harmonico (replicas de freq da banda alta; default desligado)
    exc = p.get("exc_amount", 0.0) / 100.0
    if exc > 0.0:
        pre = x.copy()
        x = aural_exciter(x, sr, exc)
        sat_pct += float(np.mean(np.abs(x - pre) > 0.01)) * 100.0

    # 7) loudness + Maxximizer estilo Waves L2:
    #    push estatico -> [TP: limita c/ margem intersample -> loudness: sobe ate ao
    #    ceiling] -> IDR 1x (quem da o extra de loudness quando o limitador satura).
    C_db = p["lim_ceiling_db"]
    C_lin = 10 ** (C_db / 20.0)
    final_target = p["lufs_target"] + p["lim_push_db"]
    x *= 10 ** (p["lim_push_db"] / 20.0)          # push estatico

    amt = p["lim_maxx"] / 100.0

    for _ in range(8):
        tp = true_peak_db(x, sr)
        if tp > C_db + 0.05:
            # excesso: ou gain-limiting de TP, ou IDR quando ativo
            # (o peak_limit opera no envelope oversampled -> converge sem over-limit)
            if amt > 0.0:
                pre = x.copy()
                x = idr_over(x, C_lin, amt)          # IDR corta os excessos
                sat_pct += float(np.mean(np.abs(x - pre) > 0.01)) * 100.0
                tp2 = true_peak_db(x, sr)
                if tp2 > C_db + 0.05:                # re-garante TP em seguida
                    x = peak_limit(x, sr, ceiling=C_lin)
            else:
                x = peak_limit(x, sr, ceiling=C_lin)
            continue
        l = integrated_lufs(x, sr)
        if not np.isfinite(l) or l < -69:
            break
        need = final_target - l
        if need <= 0.3:
            if need < -0.3:            # acima do alvo: baixar (o TP so desce, seguro)
                x *= 10 ** (need / 20)
            break
        head = max(C_db - tp, 0.0)
        if head <= 0.05 and amt <= 0.0:
            break                      # sem IDR: saturado no ceiling, ponto final
        # com headroom: sobe sem exceder o ceiling; sem headroom (c/ IDR):
        # sobe a alvo e deixa o IDR cortar os excessos (semantica do Waves L2)
        x *= 10 ** ((need if head <= 0.05 else min(need, head)) / 20)

    # garantia final de ceiling (so ganho, sem distorcao)
    tp = true_peak_db(x, sr)
    if tp > C_db + 0.05:
        x = peak_limit(x, sr, ceiling=C_lin)
        tp = true_peak_db(x, sr)
        if tp > C_db + 0.05:           # salvaguarda absoluta (ganho global)
            x *= 10 ** ((C_db - tp) / 20)

    # metricas p/ o LED (F2): distorcao REAL adicionada pelos estagios saturantes
    # (fita / IDR / exciter) = % de amostras alteradas em mais de -40 dBFS.
    # Substitui a metrica antiga de "amostras no topo" (que dava 0% mesmo com
    # saturacao massiva a meio da cadeia — ex.: fita com joelho -6 dBFS numa
    # mistura quente).
    clip_pct = min(sat_pct, 100.0)

    x = x.astype(np.float32)
    return x, moves, {
        "lufs": integrated_lufs(x, sr),
        "true_peak": true_peak_db(x, sr),
        "lra": None,           # pre-escuta nao mede LRA (rapidez)
        "corr": stereo_correlation(x),
        "spectrum": band_spectrum(x, sr),
        "clip_pct": round(clip_pct, 3),
    }


def slice_anchor(x, sr, anchor, fade_s=0.1):
    """Excerto do 'anchor' com fades curtos nas pontas (evita cliques)."""
    start, end = anchor
    end = min(end, x.shape[0])
    seg = x[start:end].copy()
    nf = min(seg.shape[0] // 2, int(sr * fade_s))
    if nf > 4:
        ramp = np.linspace(0.0, 1.0, nf)[:, None]
        seg[:nf] *= ramp
        seg[-nf:] *= ramp[::-1]
    return seg, start / sr, end / sr


# ---------------------------------------------------------------------------
# Serializacao / resposta
# ---------------------------------------------------------------------------
def _sp(k):
    return str(int(k)) if float(k) == int(k) else str(k)


def _spec_json(spec):
    return {_sp(k): round(v, 2) for k, v in spec.items()}


def _metrics_json(a):
    return {
        "lufs": round(a["lufs"], 2) if a["lufs"] is not None else None,
        "true_peak": round(a["true_peak"], 2),
        "lra": None if a["lra"] is None else round(a["lra"], 2),
        "corr": round(a["corr"], 3),
        "spectrum": _spec_json(a["spectrum"]),
        "clip_pct": round(a["clip_pct"], 3) if "clip_pct" in a else None,
    }


def build_response(uid, name, genre, profile, orig_path, out_path,
                   analysis, master_info, preview=False):
    curve = TARGET_CURVES[genre]
    moves, master_metrics, y = master_info
    sf.write(out_path, y, analysis["sr"], subtype="PCM_24")
    # o link de download aponta sempre para o master completo, com nome do input
    dl = f"/download/{uid}_master.wav?as={quote(name + '_master.wav')}"
    idx = psycho_indices(analysis["spectrum"], curve)
    return {
        "ok": True,
        "uid": uid,
        "genre": genre,
        "genre_label": GENRES[genre]["label"],
        "filename": name,
        "preview": preview,
        "slice": None,
        "original": {
            "url": f"/audio/{orig_path.name}",
            "download": f"/download/{orig_path.name}?as={quote(name + '_original.wav')}",
            "download_name": f"{name}_original.wav",
            **_metrics_json(analysis),
        },
        "master": {
            "url": f"/audio/{out_path.name}",
            "download": dl,
            "download_name": f"{name}_master.wav",
            **_metrics_json(master_metrics),
        },
        "eq_moves": [{"band": int(c) if float(c) == int(c) else c,
                      "gain": round(gain, 1)} for c, gain in moves],
        "target": {"curve": {_sp(k): v for k, v in curve.items()},
                   "lufs": profile["lufs_target"]},
        "suggestions": build_suggestions(analysis["spectrum"], curve),
        "psycho": {"indices": {k: round(v, 1) for k, v in idx.items()},
                   "tech": tech_labels(idx)},
        "params": {k: round(v, 3) for k, v in profile.items()},
        "chain": build_chain_text(profile, moves),
    }


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="MasteringApp")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/genres")
def genres():
    return [{"id": gid, "label": g["label"], "lufs": g["lufs_target"]}
            for gid, g in GENRES.items()]


@app.post("/process")
async def process(audio: UploadFile = File(...), genre: str = Form("indie"),
                  auto: str = Form("1")):
    if genre not in GENRES:
        raise HTTPException(400, "genero invalido")
    data = await audio.read()
    if len(data) > 300 * 1024 * 1024:
        raise HTTPException(413, "ficheiro demasiado grande (max 300 MB)")

    buf, sr = sf.read(io.BytesIO(data), always_2d=True)
    if sr < 32000 or sr > 192000:
        raise HTTPException(400, "sample rate nao suportado")
    if buf.shape[1] > 2:
        buf = buf[:, :2]
    if buf.shape[0] / sr > 20 * 60:
        raise HTTPException(400, "duracao maxima: 20 minutos")

    uid = uuid.uuid4().hex[:10]
    name = (Path(audio.filename or "mix.wav").stem[:40].replace(" ", "_")) or "mix"

    orig_path = UPLOAD_DIR / f"{uid}_orig.wav"
    master_path = UPLOAD_DIR / f"{uid}_master.wav"
    x = buf.astype(np.float32)
    sf.write(orig_path, x, sr, subtype="PCM_24")

    analysis = await run_in_threadpool(analyze, x, sr)

    if auto == "1":
        profile, idx, dyn_labels = await run_in_threadpool(
            auto_profile, genre, analysis)
    else:
        profile = merge_profile(genre, None)
        dyn_labels = []
        idx = psycho_indices(analysis["spectrum"], TARGET_CURVES[genre])

    JOBS[uid] = {"orig": orig_path, "name": name, "analysis": analysis, "genre": genre}

    y, moves, mm = await run_in_threadpool(
        render_master, x, sr, profile, TARGET_CURVES[genre], analysis["spectrum"])

    resp = build_response(uid, name, genre, profile, orig_path, master_path,
                          analysis, (moves, mm, y), preview=False)
    resp["auto"] = {"applied": auto == "1",
                    "dyn": [{"metric": m, "msg": s} for m, s in dyn_labels]}
    return resp


def _do_remaster(job, genre, profile, preview):
    analysis = job["analysis"]
    sr = analysis["sr"]
    x, _ = sf.read(job["orig"], always_2d=True)
    if preview:
        seg, s0, s1 = slice_anchor(x, sr, analysis["anchor"])
        # A/B em paridade: o original também é servido cortado à mesma janela
        oslice = UPLOAD_DIR / f"{job['uid']}_origslice.wav"
        sf.write(oslice, seg, sr, subtype="PCM_24")
        y, moves, mm = render_master(seg, sr, profile, TARGET_CURVES[genre],
                                     analysis["spectrum"])
        out = UPLOAD_DIR / f"{job['uid']}_preview.wav"
        resp = build_response(job["uid"], job["name"], genre, profile,
                              job["orig"], out, analysis,
                              (moves, mm, y), preview=True)
        resp["slice"] = [round(s0, 1), round(s1, 1)]
        resp["original"]["preview_url"] = f"/audio/{oslice.name}"
        return resp
    y, moves, mm = render_master(x, sr, profile, TARGET_CURVES[genre],
                                 analysis["spectrum"])
    out = UPLOAD_DIR / f"{job['uid']}_master.wav"
    resp = build_response(job["uid"], job["name"], genre, profile,
                          job["orig"], out, analysis, (moves, mm, y),
                          preview=False)
    return resp


@app.get("/profile/{genre}")
def profile_of(genre: str):
    """Perfil PURO do género (p/ o botão «Repor perfil»)."""
    if genre not in GENRES:
        raise HTTPException(404, "género desconhecido")
    return {"ok": True, "genre": genre, "params": default_profile(genre)}


# ---------------------------------------------------------------------------
# Product page + downloads dos binários (servidos de dist/ sem os embutir no
# bundle: o instalador/zip NÃO vão para dentro do exe — procuram-se ao lado).
_SETUP_NAME = "MasteringApp-Setup-1.0.0.exe"


def _dist_artifact(name: str):
    """Procura um binário de distribuição: junto ao exe (dist/MasteringApp/..)
    quando empacotado, ou em <projeto>/dist/ em desenvolvimento."""
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(Path(sys.executable).parent.parent / name)
    cands.append(Path(__file__).parent / "dist" / name)
    for c in cands:
        if c.is_file():
            return c
    return None


@app.get("/product")
async def product_page():
    return FileResponse(STATIC_DIR / "product.html")


@app.head("/get-setup")
@app.get("/get-setup")
async def get_setup():
    p = _dist_artifact(_SETUP_NAME)
    if not p:
        raise HTTPException(404, "instalador não incluído nesta instalação")
    return FileResponse(p, filename=_SETUP_NAME,
                        media_type="application/vnd.microsoft.portable-executable")


@app.head("/get-portable")
@app.get("/get-portable")
async def get_portable():
    p = _dist_artifact("MasteringApp-portable.zip")
    if not p:
        raise HTTPException(404, "zip portátil não incluído nesta instalação")
    return FileResponse(p, filename="MasteringApp-portable.zip", media_type="application/zip")


@app.post("/auto")
async def auto(body: dict = Body(...)):
    """F2 'Auto': decisao completa (biologia + tecnica + dinamica) sem render,
    a partir da analise do upload anterior. Devolve perfil + diagnosticos."""
    uid = str(body.get("uid", ""))
    job = JOBS.get(uid)
    if not job:
        raise HTTPException(404, "mistura nao encontrada — recarrega o ficheiro")
    genre = body.get("genre")
    if genre not in GENRES:
        genre = job["genre"]
    job["genre"] = genre
    analysis = job["analysis"]
    current = body.get("params") or None    # perfil em uso (sliders atuais)
    if current is not None and not isinstance(current, dict):
        current = None
    profile, idx, dyn_labels = await run_in_threadpool(
        auto_profile, genre, analysis, current)
    return {
        "ok": True,
        "uid": uid,
        "genre": genre,
        "params": {k: round(v, 3) for k, v in profile.items()},
        "psycho": {"indices": {k: round(v, 1) for k, v in idx.items()},
                   "tech": tech_labels(idx)},
        "auto": {"applied": True,
                 "dyn": [{"metric": m, "msg": s} for m, s in dyn_labels]},
    }


# ---------------------------------------------------------------------------
# F2.6 — export normalizado por plataforma de streaming
# (metas conforme a documentacao publica de cada plataforma). Especs IDENTICAS
# (Spotify/YouTube/Amazon/Tidal a -14) partilham um unico render — cache de WAV.
PLATFORM_GROUPS = [
    {"label": "Spotify", "serves": ["Spotify", "YouTube", "Amazon", "Tidal"],
     "lufs": -14.0, "tp": -1.0,
     "nota": "os 4 serviços normalizam a −14 LUFS na reprodução"},
    {"label": "Deezer", "serves": ["Deezer"],
     "lufs": -15.0, "tp": -1.0,
     "nota": "ajustado para -15 LUFS na reproducao"},
    {"label": "Apple Music", "serves": ["Apple Music"],
     "lufs": -16.0, "tp": -1.0,
     "nota": "Sound Check mira -16 LUFS; manter TP <= -1 dBTP"},
]
# nomes antigos continuam aceite (apontam para o mesmo grupo/ficheiro)
PLATFORM_TO_GROUP = {
    "spotify": 0, "youtube": 0, "amazon": 0, "tidal": 0,
    "deezer": 1, "apple": 2,
}


@app.post("/export_platform")
async def export_platform(body: dict = Body(...)):
    """Render completo ajustado ao spec da plataforma escolhida. Mantém a cadeia
    criativa do user; só loudness/ceiling seguem o spec (push desativado no
    export). Especs iguais partilham o MESMO WAV: 1.º pedido renderiza, os
    restantes devolvem o ficheiro em cache (só re-medição, quase instantâneo)."""
    uid = str(body.get("uid", ""))
    job = JOBS.get(uid)
    if not job:
        raise HTTPException(404, "mistura nao encontrada — recarrega o ficheiro")
    gid = PLATFORM_TO_GROUP.get(str(body.get("platform", "")))
    if gid is None:
        raise HTTPException(400, "plataforma invalida")
    group = PLATFORM_GROUPS[gid]
    genre = body.get("genre")
    if genre not in GENRES:
        genre = job["genre"]
    job["genre"] = genre

    overrides = dict(body.get("params") or {})
    overrides.update({
        "lufs_target": group["lufs"],
        "lim_push_db": 0.0,
        "lim_ceiling_db": min(float(overrides.get("lim_ceiling_db", -1.0)),
                              group["tp"]),
    })
    profile = merge_profile(genre, overrides)

    analysis = job["analysis"]
    curve = TARGET_CURVES[genre]
    moves = spectral_moves(analysis["spectrum"], curve, profile["eq_strength"])

    # cache: mesmo ficheiro original + perfil final + alvo -> mesmo WAV
    key = hashlib.md5(json.dumps(
        {"uid": uid, "genre": genre, "lufs": group["lufs"],
         "params": [round(profile[k], 6) for k in PARAM_KEYS]},
        sort_keys=True).encode()).hexdigest()[:12]
    out = UPLOAD_DIR / f"{uid}_xp_{key}.wav"
    cached = out.is_file()
    if cached:
        x, _ = sf.read(out, always_2d=True)
        sr = analysis["sr"]
        lufs_cm = integrated_lufs(x, sr)
        tp_cm = true_peak_db(x, sr)
        top_edge = 10 ** (profile["lim_ceiling_db"] / 20.0) * 10 ** (-0.06 / 20.0)
        clip_pct = float(np.mean(np.abs(x) >= top_edge)) * 100.0
        mm = {"lufs": lufs_cm, "true_peak": tp_cm, "clip_pct": clip_pct}
    else:
        x, _ = sf.read(job["orig"], always_2d=True)
        y, moves, mm = await run_in_threadpool(
            render_master, x, analysis["sr"], profile, curve, analysis["spectrum"])
        sf.write(out, y, analysis["sr"], subtype="PCM_24")

    lufs = float(mm["lufs"])
    tp = float(mm["true_peak"])
    spec_ok = bool((abs(lufs - group["lufs"]) <= 0.6) and (tp <= group["tp"] + 0.05))
    dl_name = f"{job['name']}_master_{int(group['lufs'])}LUFS.wav"
    return {
        "ok": True,
        "uid": uid,
        "platform": str(body.get("platform", "")),
        "platform_label": group["label"],
        "serves": group["serves"],
        "spec": {"lufs": group["lufs"], "tp": group["tp"], "nota": group["nota"]},
        "master": {"url": f"/audio/{out.name}",
                   "download": f"/download/{out.name}?as={quote(dl_name)}",
                   "download_name": dl_name,
                   "lufs": round(lufs, 2), "true_peak": round(tp, 2),
                   "clip_pct": round(float(mm.get("clip_pct", 0.0)), 3)},
        "spec_ok": spec_ok,
        "cached": bool(cached),
        "chain": build_chain_text(profile, moves),
    }


@app.post("/remaster")
async def remaster(body: dict = Body(...)):
    uid = str(body.get("uid", ""))
    job = JOBS.get(uid)
    if not job:
        raise HTTPException(404, "mistura nao encontrada — recarrega o ficheiro")
    genre = body.get("genre")
    if genre not in GENRES:
        genre = job["genre"]
    profile = merge_profile(genre, body.get("params"))
    preview = bool(body.get("preview", False))
    job["uid"] = uid
    job["genre"] = genre
    return await run_in_threadpool(_do_remaster, job, genre, profile, preview)


@app.get("/audio/{name}")
def audio_file(name: str):
    p = (UPLOAD_DIR / name).resolve()
    if not p.is_file() or UPLOAD_DIR.resolve() not in p.parents:
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/wav")


@app.get("/download/{name}")
def download_file(name: str, as_name: str = Query("", alias="as")):
    p = (UPLOAD_DIR / name).resolve()
    if not p.is_file() or UPLOAD_DIR.resolve() not in p.parents:
        raise HTTPException(404)
    # `?as=` permite servir o mesmo ficheiro em disco com nome de descarga
    # amigável (ex.: MinhaMix_master_-14LUFS.wav) sem colisões de cache
    nice = "".join(c for c in (as_name or name) if c not in '\\/:*?"<>|').strip()
    return FileResponse(p, media_type="audio/wav", filename=nice or name)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import sys
    import os
    import time
    import socket
    import uvicorn

    def _pick_port(preferred):
        """Primeiro porto livre a partir de `preferred` (7860 seguido de
        7861, ... se já houver outra instância a correr)."""
        port = preferred
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:   # não conectável = livre
                    return port
                port += 1

    host = os.environ.get("HOST", "127.0.0.1")
    # PORT de ambiente (Railway) tem prioridade; sem ela, porto automático
    port = int(os.environ["PORT"]) if os.environ.get("PORT") else _pick_port(7860)

    if getattr(sys, "frozen", False):
        # .exe: abrir o browser quando o servidor estiver a responder
        import threading
        import webbrowser

        def _open_browser():
            import urllib.request
            url = f"http://127.0.0.1:{port}"
            for _ in range(60):
                try:
                    urllib.request.urlopen(url + "/genres", timeout=1)
                    break
                except Exception:
                    time.sleep(0.5)
            webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(app, host=host, port=port)
