"""Gera static/app_icon.ico — ícone do MasteringApp (knob dourado sobre
chassis de rack escuro + LED de clipping). Desenho supersampled 4x."""
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024                      # canvas supersampled
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# ---- chassis arredondado (rack) -------------------------------------------
m = 30
d.rounded_rectangle([m, m, S - m, S - m], 170, fill=(23, 23, 27, 255),
                    outline=(0, 0, 0, 255), width=10)
d.rounded_rectangle([m + 20, m + 20, S - m - 20, S - m - 20], 150,
                    outline=(58, 58, 68, 255), width=6)

# ---- knob dourado (gradiente radial por anéis) ----------------------------
cx, cy, R = S // 2, S // 2 + 46, 330
ring = 3
d.ellipse([cx - R - 14, cy - R - 14, cx + R + 14, cy + R + 14],
          fill=(10, 10, 12, 255))                    # aro externo escuro
for r in range(R, 0, -ring):
    t = r / R                                        # 1 na borda, 0 no centro
    # borda ouro escuro -> centro ouro claro
    col = (int(120 + (250 - 120) * (1 - t) ** 1.6),
           int(92 + (205 - 92) * (1 - t) ** 1.6),
           int(24 + (105 - 24) * (1 - t) ** 1.6), 255)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)

# brilho especular deslocado (topo-esquerda)
hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
dh = ImageDraw.Draw(hl)
dh.ellipse([cx - R * 0.62, cy - R * 0.72, cx + R * 0.18, cy + R * 0.02],
           fill=(255, 245, 200, 70))
hl = hl.filter(__import__("PIL.ImageFilter", fromlist=["ImageFilter"]).GaussianBlur(60))
img = Image.alpha_composite(img, hl)
d = ImageDraw.Draw(img)

# ponteiro do knob (posição ~10h)
import math
ang = math.radians(232)                              # 10 horas
px, py = cx + R * 0.88 * math.cos(ang), cy + R * 0.88 * math.sin(ang)
hx, hy = cx + R * 0.30 * math.cos(ang), cy + R * 0.30 * math.sin(ang)
d.line([hx, hy, px, py], fill=(28, 25, 19, 255), width=40)
d.ellipse([cx - 74, cy - 74, cx + 74, cy + 74], fill=(32, 28, 22, 255))
d.ellipse([cx - 74 + 8, cy - 74 + 8, cx + 74 - 8, cy + 74 - 8],
          fill=(52, 46, 36, 255))

# ---- LED de clipping (topo-direita) ---------------------------------------
led_x, led_y, led_r = int(S * 0.78), int(S * 0.235), 42
d.ellipse([led_x - led_r - 26, led_y - led_r - 26,
           led_x + led_r + 26, led_y + led_r + 26], fill=(140, 30, 24, 110))
d.ellipse([led_x - led_r, led_y - led_r, led_x + led_r, led_y + led_r],
          fill=(228, 72, 64, 255))
d.ellipse([led_x - led_r * 0.45, led_y - led_r * 0.45,
           led_x + led_r * 0.35, led_y + led_r * 0.35],
          fill=(255, 170, 160, 200))                 # brilho do LED

# ---- reduz e grava ---------------------------------------------------------
icon = img.resize((256, 256), Image.LANCZOS)
out = Path(__file__).resolve().parent / "static" / "app_icon.ico"
out.parent.mkdir(exist_ok=True)
icon.save(out, format="ICO",
          sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                 (128, 128), (256, 256)])
icon.save(out.with_suffix(".png"), format="PNG")
print("ok:", out, f"({out.stat().st_size / 1024:.0f} KB)")
