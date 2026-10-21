"""MasteringApp — lançador desktop (usado pelo .exe PyInstaller).

Abre a UI numa JANELA NATIVA (pywebview + WebView2/Edge): o app corre na
própria janela, sem browser externo. O backend FastAPI continua em localhost
(na mesma máquina, invisível ao utilizador). Se o WebView2 não existir na
máquina, cai graciosamente para o modo anterior (janela de status + browser).
Em modo script (python desktop.py) funciona igual, para testar sem build.
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = BASE_DIR

sys.path.insert(0, str(RESOURCE_DIR if getattr(sys, "frozen", False) else BASE_DIR))
import app as appmod  # noqa: E402  (o backend; garante paths do bundle)


def pick_port(preferred):
    """Primeiro porto livre a partir de `preferred`."""
    port = preferred
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
            port += 1


PORT = int(os.environ["PORT"]) if os.environ.get("PORT") else pick_port(7860)
URL = f"http://127.0.0.1:{PORT}"

server = uvicorn.Server(uvicorn.Config(appmod.app, host="127.0.0.1",
                                       port=PORT, log_config=None,
                                       log_level="warning"))


def wait_ready(timeout_s=20.0):
    """Espera até o backend responder (ou esgotar o tempo)."""
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            urllib.request.urlopen(URL + "/genres", timeout=1)
            return True
        except Exception:
            if server.should_exit:
                return False
            time.sleep(0.3)
    return False


def fallback_status_window():
    """Modo anterior: janela de status tkinter + abrir no browser."""
    import tkinter as tk
    import urllib.request

    root = tk.Tk()
    root.title("MasteringApp")
    root.geometry("430x176")
    root.resizable(False, False)
    root.configure(bg="#141416")
    try:
        root.iconbitmap(str(RESOURCE_DIR / "static" / "app_icon.ico"))
    except Exception:
        pass

    frm = tk.Frame(root, bg="#141416", padx=18, pady=12)
    frm.pack(fill="both", expand=True)
    tk.Label(frm, text="  MasteringApp", fg="#efe9db", bg="#141416",
             font=("Segoe UI Semibold", 15)).pack(anchor="w")
    status_var = tk.StringVar(value=f"A arrancar servidor… porto {PORT}")
    status = tk.Label(frm, textvariable=status_var, fg="#9a958a", bg="#141416",
                      font=("Segoe UI", 10))
    status.pack(anchor="w", pady=(4, 10))
    btns = tk.Frame(frm, bg="#141416")
    btns.pack(anchor="w")

    def quit_app():
        server.should_exit = True
        root.after(150, root.destroy)
        root.after(250, lambda: os._exit(0))

    def mkbtn(txt, cmd, gold=False):
        bg = ("#e7c05a", "#c9a02e") if gold else ("#3a3a3e", "#1b1b1e")
        fg = "#241c07" if gold else "#e9e3d4"
        tk.Button(btns, text=txt, command=cmd, bg=bg[0], fg=fg,
                  activebackground=bg[1], activeforeground=fg,
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  font=("Segoe UI", 10, "bold" if gold else "normal")
                  ).pack(side="left", padx=(0, 10))

    mkbtn("Abrir no browser", lambda: webbrowser.open(URL))
    mkbtn("Sair", quit_app)

    opened = [False]

    def poll():
        try:
            urllib.request.urlopen(URL + "/genres", timeout=1)
        except Exception:
            if not server.should_exit:
                root.after(500, poll)
            return
        if not opened[0]:
            opened[0] = True
            status_var.set(f"A correr em {URL}  —  o app fica no browser")
            status.config(fg="#3fae5a")
            webbrowser.open(URL)

    root.after(400, poll)
    root.protocol("WM_DELETE_WINDOW", quit_app)
    root.mainloop()


def main():
    threading.Thread(target=server.run, daemon=True).start()
    ready = wait_ready()
    if not ready and server.should_exit:
        return os._exit(0)

    try:
        import webview
        # janela nativa: a UI corre dentro, sem browser externo.
        # (WebView2 — se não existir na máquina, ValueError/RuntimeError)
        webview.create_window("MasteringApp", URL, width=1280, height=860,
                              min_size=(980, 640), background_color="#0e0e10")
        webview.start(gui="edgechromium")
    except Exception as e:
        # fallback: browser externo + janela de status
        print("webview indisponível:", e)
        webbrowser.open(URL)
        fallback_status_window()

    server.should_exit = True
    os._exit(0)


if __name__ == "__main__":
    main()
