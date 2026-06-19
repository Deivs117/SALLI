# ===== sally_driver.py =====
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
import json, threading, time, io
import os, sys, subprocess  # <— para lanzar la GUI de calibración como proceso

# --- Imagen (JPEG) ---
try:
    from PIL import Image, ImageTk  # pip install pillow
except Exception:
    Image = ImageTk = None

# ===================== Defaults =====================
DEFAULT_HOST      = "192.168.4.1"     # ESP32 (Sally main)
DEFAULT_PORT      = 80
DEFAULT_CAM_HOST  = "192.168.61.99"     # ESP32-CAM IP (ajústalo si es otra)
DEFAULT_CAM_PORT  = 80

APP_FONT_FAMILY = "Yu Gothic UI Semilight"
APP_FONT_SIZE   = 15

CAM_MAX_W = 640   # ancho máximo del visor
CAM_MAX_H = 480   # alto máximo del visor

# ===================== UI Style (oscuro) =====================
def style_dark(app: tk.Tk):
    style = ttk.Style(app)
    try:
        app.tk.call("source", "azure.tcl")
        style.theme_use("azure-dark")
    except Exception:
        style.theme_use("clam")
        app.configure(bg="#161515")
        style.configure(".", font=(APP_FONT_FAMILY, APP_FONT_SIZE))
        style.configure("Dark.TFrame",  background="#161515")
        style.configure("Dark.TLabel",  background="#161515", foreground="#E6E6E6")
        style.configure("Dim.TLabel",   background="#161515", foreground="#B9B9B9")
        style.configure("Dark.TButton", background="#222222", foreground="#E6E6E6", padding=(10,6))
        style.map("Dark.TButton",
                  background=[("pressed", "#4A4A4A"), ("active", "#3A3A3A")])
        style.configure("Dark.TEntry", fieldbackground="#2A2727", foreground="#E6E6E6",
                        background="#161515", insertcolor="#E6E6E6")
        style.configure("Horizontal.TScale", background="#161515", troughcolor="#1B1B1B")

# ===================== App =====================
class SallyDriver(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sally – Driver Wi-Fi + Cámara")
        self.geometry("1080x900")
        self.minsize(720, 560)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Estado cámara
        self._cam_running = False
        self._cam_imgtk = None

        style_dark(self)

        row = 0
        # ---- Cabecera conexión Sally ----
        hdr = ttk.Frame(self, style="Dark.TFrame", padding=(10,10,10,6))
        hdr.grid(row=row, column=0, sticky="ew")
        hdr.grid_columnconfigure(7, weight=1)

        ttk.Label(hdr, text="Host:", style="Dark.TLabel").grid(row=0, column=0, sticky="e", padx=6)
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        ttk.Entry(hdr, textvariable=self.host_var, width=18, style="Dark.TEntry").grid(row=0, column=1, sticky="w")

        ttk.Label(hdr, text="Puerto:", style="Dark.TLabel").grid(row=0, column=2, sticky="e", padx=(12,6))
        self.port_var = tk.IntVar(value=DEFAULT_PORT)
        ttk.Entry(hdr, textvariable=self.port_var, width=6, style="Dark.TEntry").grid(row=0, column=3, sticky="w")

        ttk.Button(hdr, text="Probar", style="Dark.TButton", command=self.ping).grid(row=0, column=4, padx=10)

        # Botón para abrir la GUI de calibración (proceso separado)
        ttk.Button(hdr, text="Calibración…", style="Dark.TButton",
                   command=self.open_calibrator).grid(row=0, column=5, padx=(4,10))

        # ---- Cabecera Cámara ----
        ttk.Label(hdr, text="Cam IP:", style="Dark.TLabel").grid(row=1, column=0, sticky="e", padx=6, pady=(6,0))
        self.cam_host_var = tk.StringVar(value=DEFAULT_CAM_HOST)
        ttk.Entry(hdr, textvariable=self.cam_host_var, width=18, style="Dark.TEntry").grid(row=1, column=1, sticky="w", pady=(6,0))

        ttk.Label(hdr, text="Cam Puerto:", style="Dark.TLabel").grid(row=1, column=2, sticky="e", padx=(12,6), pady=(6,0))
        self.cam_port_var = tk.IntVar(value=DEFAULT_CAM_PORT)
        ttk.Entry(hdr, textvariable=self.cam_port_var, width=6, style="Dark.TEntry").grid(row=1, column=3, sticky="w", pady=(6,0))

        # ---- Sliders: Lateralidad (pct) y Respuesta (resp) ----
        row += 2
        sliders = ttk.Frame(self, style="Dark.TFrame", padding=(10,8,10,0))
        sliders.grid(row=row, column=0, sticky="ew")
        sliders.grid_columnconfigure(1, weight=1)

        self.pct_var  = tk.IntVar(value=50)   # 0..100
        self.resp_var = tk.IntVar(value=50)   # 0..100

        ttk.Label(sliders, text="Lateralidad (pct)", style="Dark.TLabel").grid(row=0, column=0, sticky="w", pady=(0,4))
        ttk.Scale(sliders, from_=0, to=100, variable=self.pct_var, orient="horizontal",
                  style="Horizontal.TScale").grid(row=0, column=1, sticky="ew", padx=8)

        ttk.Label(sliders, text="Respuesta (resp)", style="Dark.TLabel").grid(row=1, column=0, sticky="w", pady=(6,0))
        ttk.Scale(sliders, from_=0, to=100, variable=self.resp_var, orient="horizontal",
                  style="Horizontal.TScale").grid(row=1, column=1, sticky="ew", padx=8, pady=(6,0))

        # ---- Botonera de dirección ----
        row += 1
        btns = ttk.Frame(self, style="Dark.TFrame", padding=(10,12,10,0))
        btns.grid(row=row, column=0, sticky="ew")
        btns.grid_columnconfigure((0,1,2), weight=1)

        ttk.Button(btns, text="← Izquierda", style="Dark.TButton",
                   command=lambda: self.drive("left")).grid(row=0, column=0, padx=6, pady=4, sticky="ew")
        ttk.Button(btns, text="↑ Adelante",  style="Dark.TButton",
                   command=lambda: self.drive("fwd")).grid (row=0, column=1, padx=6, pady=4, sticky="ew")
        ttk.Button(btns, text="→ Derecha",   style="Dark.TButton",
                   command=lambda: self.drive("right")).grid(row=0, column=2, padx=6, pady=4, sticky="ew")
        ttk.Button(btns, text="■ Stop",      style="Dark.TButton",
                   command=lambda: self.drive("stop")).grid (row=1, column=1, padx=6, pady=6, sticky="ew")

        # ---- Estado + Atajos ----
        row += 1
        status = ttk.Frame(self, style="Dark.TFrame", padding=(10,8,10,10))
        status.grid(row=row, column=0, sticky="ew")
        status.grid_columnconfigure(0, weight=1)

        self.status = tk.StringVar(value="Listo.")
        ttk.Label(status, textvariable=self.status, style="Dark.TLabel").grid(row=0, column=0, sticky="w")
        shortcuts = "Atajos: ←/→/↑/Espacio  |  WASD"
        ttk.Label(status, text=shortcuts, style="Dim.TLabel").grid(row=1, column=0, sticky="w", pady=(6,0))

        # Atajos de teclado
        self.bind("<Left>",  lambda e: self.drive("left"))
        self.bind("<Right>", lambda e: self.drive("right"))
        self.bind("<Up>",    lambda e: self.drive("fwd"))
        self.bind("<space>", lambda e: self.drive("stop"))
        self.bind("a",       lambda e: self.drive("left"))
        self.bind("d",       lambda e: self.drive("right"))
        self.bind("w",       lambda e: self.drive("fwd"))
        self.bind("s",       lambda e: self.drive("stop"))

        # ---- Cámara (visualización JPEG + FPS) ----
        row += 1
        cam = ttk.Frame(self, style="Dark.TFrame", padding=(10,8,10,10))
        cam.grid(row=row, column=0, sticky="nsew")
        cam.grid_columnconfigure(1, weight=1)

        ttk.Label(cam, text="FPS", style="Dark.TLabel").grid(row=0, column=0, sticky="e")
        self.cam_fps_var = tk.IntVar(value=10)  # 1..60
        self.cam_fps_spin = ttk.Spinbox(cam, from_=1, to=60, textvariable=self.cam_fps_var, width=5)
        self.cam_fps_spin.grid(row=0, column=1, sticky="w", padx=(6,12))
        ttk.Button(cam, text="Iniciar cámara", style="Dark.TButton",
                   command=self.cam_start).grid(row=0, column=2, padx=6)
        ttk.Button(cam, text="Detener cámara", style="Dark.TButton",
                   command=self.cam_stop).grid (row=0, column=3, padx=6)

        # Lienzo/Label de imagen
        self.cam_panel = ttk.Label(cam, text="(sin imagen)", style="Dim.TLabel", anchor="center")
        self.cam_panel.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(10,0))
        cam.grid_rowconfigure(1, weight=1)

        # Expandir
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(row, weight=1)

    # ---------------- Helpers ----------------
    def base_url(self):
        host = self.host_var.get().strip()
        port = int(self.port_var.get())
        return f"http://{host}:{port}"

    def cam_base_url(self):
        host = self.cam_host_var.get().strip()
        port = int(self.cam_port_var.get())
        return f"http://{host}:{port}"

    # ---------------- Acciones ----------------
    def ping(self):
        threading.Thread(target=self._do_ping, daemon=True).start()

    def _do_ping(self):
        try:
            url = f"{self.base_url()}/drive?dir=stop"
            with urlopen(url, timeout=2) as r:
                data = r.read().decode("utf-8", errors="ignore").strip()
            self.status.set(f"OK conectado. Respuesta: {data[:90]}")
        except (URLError, HTTPError) as e:
            self.status.set(f"No conectado: {e}")

    def drive(self, direction: str):
        threading.Thread(target=self._do_drive, args=(direction,), daemon=True).start()

    def _do_drive(self, direction: str):
        params = {
            "dir":  direction,                            # fwd|left|right|stop
            "pct":  max(0, min(100, self.pct_var.get())), # lateralidad %
            "resp": max(0, min(100, self.resp_var.get())) # K de respuesta
        }
        try:
            url = f"{self.base_url()}/drive?{urlencode(params)}"
            with urlopen(url, timeout=2) as r:
                payload = r.read().decode("utf-8", errors="ignore").strip()
            try:
                js = json.loads(payload)
                msg = f"dir={js.get('dir')} pct={js.get('pct',js.get('pct_sent'))} resp={js.get('resp')}"
            except Exception:
                msg = payload
            self.status.set(f"Enviado: {direction} • {msg[:100]}")
        except (URLError, HTTPError) as e:
            self.status.set(f"Error enviando {direction}: {e}")

    # -------- Abrir Calibración (nuevo) --------
    def open_calibrator(self):
        """
        Lanza sally_driver_wcal.py como PROCESO independiente, pasando host/port actuales.
        No bloquea la GUI de comandos ni elimina funciones.
        """
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            script = os.path.join(here, "sally_driver_wcal.py")
            host = self.host_var.get().strip()
            port = str(int(self.port_var.get()))
            subprocess.Popen([sys.executable, script, host, port], close_fds=True)
            self.status.set("Calibración abierta.")
        except Exception as e:
            self.status.set(f"No se pudo abrir calibración: {e}")

    # ---------------- Cámara (pull a /frame) ----------------
    def cam_start(self):
        if Image is None or ImageTk is None:
            self.status.set("Pillow no disponible: instala 'pip install pillow' para ver JPEG.")
            return
        if self._cam_running:
            self.status.set("Cámara ya en marcha.")
            return
        self._cam_running = True
        threading.Thread(target=self._cam_loop, daemon=True).start()
        self.status.set("Cámara: iniciada.")

    def cam_stop(self):
        self._cam_running = False
        self.status.set("Cámara: detenida.")

    def _cam_loop(self):
        last_err_t = 0.0
        while self._cam_running:
            t0 = time.time()
            url = f"{self.cam_base_url()}/frame"
            try:
                req = Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
                with urlopen(req, timeout=3) as r:
                    raw = r.read()
                img = Image.open(io.BytesIO(raw)).convert("RGB")

                try:
                    max_w = max(480, min(self.winfo_width()-40, 960))
                except Exception:
                    max_w = 640
                ratio = max_w / float(img.width) if img.width else 1.0
                new_h = max(1, int(img.height * ratio))
                img = img.resize((int(max_w), new_h), Image.BILINEAR)

                imgtk = ImageTk.PhotoImage(img)
                def _update():
                    self._cam_imgtk = imgtk  # evita GC
                    self.cam_panel.configure(image=imgtk, text="")
                self.after(0, _update)
            except Exception as e:
                if time.time() - last_err_t > 1.5:
                    self.after(0, lambda: self.status.set(f"Cam error: {e}"))
                    last_err_t = time.time()

            fps = self.cam_fps_var.get() if isinstance(self.cam_fps_var.get(), int) else 10
            fps = max(1, min(60, fps))
            period = 1.0 / float(fps)
            dt = time.time() - t0
            if dt < period:
                time.sleep(period - dt)

    def _on_close(self):
        try:
            self._cam_running = False
        except Exception:
            pass
        self.destroy()

# ===================== Main =====================
if __name__ == "__main__":
    app = SallyDriver()
    app.mainloop()
