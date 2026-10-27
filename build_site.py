"""Monta o site estático do GitHub Pages (cópia index de produto + app + help).

Uso:  python build_site.py [destino]     (default: site/)
      python build_site.py site          (usado pelo workflow .github/workflows/pages.yml)

Resultado:
  <destino>/index.html       ← static/product.html (links /app e /static/help relativizados)
  <destino>/help.html        ← static/help.html
  <destino>/app/index.html   ← static/index.html (a UI deteta github.io e fala
                               com o backend local 127.0.0.1:7860 — ver API_BASE)
  <destino>/.nojekyll
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "site")


def main():
    static = ROOT / "static"
    (OUT / "app").mkdir(parents=True, exist_ok=True)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    product = (static / "product.html").read_text(encoding="utf-8")
    product = product.replace('href="/app"', 'href="app/"')
    product = product.replace('href="/static/help.html"', 'href="help.html"')
    (OUT / "index.html").write_text(product, encoding="utf-8")

    (OUT / "help.html").write_text(
        (static / "help.html").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "app" / "index.html").write_text(
        (static / "index.html").read_text(encoding="utf-8"), encoding="utf-8")

    print(f"site montado em {OUT}:")
    for p in sorted(OUT.rglob("*")):
        rel = p.relative_to(OUT)
        print(f"  {'d ' if p.is_dir() else 'f '}{rel}")


if __name__ == "__main__":
    main()
