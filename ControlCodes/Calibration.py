# sally_calibrator.py
# GUI SOLO para calibración de servos de Sally (Wi-Fi)
# - Botones:
#   1) "Mandar 90° (CALIB)"  -> /mode?state=calib    (publica 90° puros)
#   2) "Probar offsets (RUN)"-> POST /calib + /mode?state=run  (aplica offsets y corre)
#   3) "Guardar offsets"     -> POST /calib (persistir en NVS) + feedback
# - Usa la paleta/estética de la GUI previa (oscura).
# - Grupos: Patas1 (4), Osc1–3 (3), Patas2 (4), Osc4–6 (3). Rango offsets: -45..45.

import tkinter as tk
from tkinter import ttk, messagebox
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import json
import threading

# ---------- Estilo (colores/tipografías) ----------
APP_FONT_FAMILY = "Yu Gothic UI Semilight"
APP_FONT_SIZE   = 15

BG   = "#161515"     # fondo
FG   = "#E6E6E6"     # texto claro
FG_DIM = "#B9B9B9"   # texto tenue
BTN_BG = "#222222"
BTN_BG_ACTIVE = "#3A3A3A"
BTN_BG_PRESS  = "#4A4A4A"
ACCENT = "#D65151"   # acento/estado

def style_dark(app: tk.Tk):
    st = ttk.Style(app)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    app.configure(bg=BG)
    st.configure(".", font=(APP_FONT_FAMILY, APP_FONT_SIZE))
    st.configure("Dark.TFrame",  background=BG)
    st.configure("Dark.TLabel",  background=BG, foreground=FG)
    st.configure("Dim.TLabel",   background=BG, foreground=FG_DIM)
    st.configure("Accent.TLabel",background=BG, foreground=ACCENT)
    st.configure("Dark.TButton", background=BTN_BG, foreground=FG, padding=(12,8))
    st.map("Dark.TButton",
           background=[("pressed", BTN_BG_PRESS), ("active", BTN_BG_ACTIVE)],
           relief=[("pressed", "sunken"), ("!pressed", "flat")])
    st.configure("Dark.TEntry", fieldbackground="#2A2727", foreground=FG, background=BG, insertcolor=FG)
    st.configure("Horizontal.TScale", background=BG, troughcolor="#1B1B1B")

# ---------- Red ----------
DEFAULT_HOST = "192.168.4.1"
DEFAULT_PORT = 80

def http_get(url: str, timeout=2.0):
    with urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

def http_post_json(url: str, payload: dict, timeout=2.5):
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type":"application/json"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

# ---------- App ----------
SERVO_COUNT = 14
NAMES = [
    # Patas 1 (4)
    "Patas1-S0","Patas1-S1","Patas1-S2","Patas1-S3",
    # Osc 1–3
    "Osc1","Osc2","Osc3",
    # Patas 2 (4)
    "Patas2-S0","Patas2-S1","Patas2-S2","Patas2-S3",
    # Osc 4–6
    "Osc4","Osc5","Osc6"
]

class CalibApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sally – Calibración de Servos (Wi-Fi)")
        self.geometry("980x720")
        self.minsize(760, 560)
        style_dark(self)

        # Header: Host/Port + Probar conexión
        hdr = ttk.Frame(self, style="Dark.TFrame", padding=(14,12,14,6))
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Host:", style="Dark.TLabel").pack(side="left")
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        ttk.Entry(hdr, textvariable=self.host_var, width=18, style="Dark.TEntry").pack(side="left", padx=(6,14))
        ttk.Label(hdr, text="Puerto:", style="Dark.TLabel").pack(side="left")
        self.port_var = tk.IntVar(value=DEFAULT_PORT)
        ttk.Entry(hdr, textvariable=self.port_var, width=6, style="Dark.TEntry").pack(side="left", padx=(6,14))
        ttk.Button(hdr, text="Probar conexión", style="Dark.TButton", command=self.ping).pack(side="left", padx=(0,10))

        # Acciones principales
        actions = ttk.Frame(self, style="Dark.TFrame", padding=(14,4,14,0))
        actions.pack(fill="x")
        ttk.Button(actions, text="1) Mandar 90° (CALIB)", style="Dark.TButton",
                   command=self.cmd_send_90).pack(side="left", padx=6)
        ttk.Button(actions, text="2) Probar offsets (RUN)", style="Dark.TButton",
                   command=self.cmd_preview_offsets).pack(side="left", padx=6)
        ttk.Button(actions, text="3) Guardar offsets", style="Dark.TButton",
                   command=self.cmd_save_offsets).pack(side="left", padx=6)
        ttk.Button(actions, text="Volver a 90°", style="Dark.TButton",
                   command=self.cmd_send_90).pack(side="left", padx=16)

        # Estado
        status = ttk.Frame(self, style="Dark.TFrame", padding=(14,6,14,10))
        status.pack(fill="x")
        self.status = tk.StringVar(value="Listo. Conéctate al AP de Sally, pulsa Probar conexión.")
        ttk.Label(status, textvariable=self.status, style="Accent.TLabel").pack(side="left")

        # Offsets UI
        self.offset_vars = [tk.IntVar(value=0) for _ in range(SERVO_COUNT)]
        self.build_offsets_panel()

        # Fetch offsets actuales
        self.fetch_offsets_async()

        # Shortcuts
        self.bind("<F5>", lambda e: self.fetch_offsets_async())
        self.bind("<Control-s>", lambda e: self.cmd_save_offsets())
        self.bind("<Control-r>", lambda e: self.cmd_preview_offsets())
        self.bind("<Control-c>", lambda e: self.cmd_send_90())

    # ---------- Layout offsets ----------
    def build_offsets_panel(self):
        wrap = ttk.Frame(self, style="Dark.TFrame", padding=(14,4,14,14))
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(0, weight=1)

        # Tip UX
        tip = ("Ajusta los offsets (°) en cada slider/spinbox.\n"
               "• 1) CALIB envía a 90° puros para centrar mecánicamente\n"
               "• 2) Probar offsets aplica los valores y pone RUN para validar postura\n"
               "• 3) Guardar offsets persiste en NVS (aplicará en RUN)\n"
               "Atajos: F5 recargar, Ctrl+R probar, Ctrl+S guardar, Ctrl+C 90°.")
        ttk.Label(wrap, text=tip, style="Dim.TLabel").grid(row=0, column=0, sticky="w", pady=(0,6))

        grid = ttk.Frame(wrap, style="Dark.TFrame")
        grid.grid(row=1, column=0, sticky="nsew")
        wrap.rowconfigure(1, weight=1)
        grid.columnconfigure(1, weight=1)

        row = 0
        # Grupos
        row = self.add_group(grid, "Módulo de patas 1",  0, 4,   row)
        row = self.add_group(grid, "Oscilatorios 1–3",   4, 7,   row)
        row = self.add_group(grid, "Módulo de patas 2",  7, 11,  row)
        row = self.add_group(grid, "Oscilatorios 4–6",   11, 14, row)

    def add_group(self, parent, title, i0, i1, row):
        lf = ttk.LabelFrame(parent, text=title, style="Dark.TFrame")
        lf.grid(row=row, column=0, sticky="ew", pady=6)
        lf.columnconfigure(2, weight=1)

        for i in range(i0, i1):
            r = ttk.Frame(lf, style="Dark.TFrame")
            r.grid(row=i - i0, column=0, sticky="ew", padx=8, pady=4)
            r.columnconfigure(1, weight=1)

            ttk.Label(r, text=NAMES[i], style="Dark.TLabel", width=14).grid(row=0, column=0, sticky="w")
            s = ttk.Scale(r, from_=-45, to=45, orient="horizontal",
                          variable=self.offset_vars[i], style="Horizontal.TScale")
            s.grid(row=0, column=1, sticky="ew", padx=8)
            sp = ttk.Spinbox(r, from_=-45, to=45, width=5, textvariable=self.offset_vars[i])
            sp.grid(row=0, column=2, sticky="e")
        return row + 1

    # ---------- Helpers ----------
    def base_url(self):
        host = self.host_var.get().strip()
        port = int(self.port_var.get())
        return f"http://{host}:{port}"

    def ping(self):
        def task():
            try:
                url = f"{self.base_url()}/drive?dir=stop"
                payload = http_get(url, timeout=2.0)
                self.status.set(f"OK conectado. Respuesta: {payload[:90]}")
            except (URLError, HTTPError) as e:
                self.status.set(f"No conectado: {e}")
        threading.Thread(target=task, daemon=True).start()

    def fetch_offsets_async(self):
        def task():
            try:
                data = http_get(f"{self.base_url()}/calib", timeout=2.0)
                js = json.loads(data)
                offs = js.get("offsets", [])
                if isinstance(offs, list) and len(offs) == SERVO_COUNT:
                    for i, v in enumerate(offs):
                        v = int(max(-45, min(45, int(v))))
                        self.offset_vars[i].set(v)
                    self.status.set("Offsets cargados desde Sally.")
                else:
                    self.status.set("Respuesta /calib inválida; usando 0.")
            except (URLError, HTTPError) as e:
                self.status.set(f"Error leyendo /calib: {e}")
        threading.Thread(target=task, daemon=True).start()

    # ---------- Comandos ----------
    def cmd_send_90(self):
        # modo calibración (90° puros)
        def task():
            try:
                http_get(f"{self.base_url()}/mode?state=calib", timeout=2.0)
                self.status.set("Modo CALIB: publicando 90° en todos los canales.")
            except (URLError, HTTPError) as e:
                self.status.set(f"Error /mode calib: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _collect_offsets(self):
        offs = [int(max(-45, min(45, v.get()))) for v in self.offset_vars]
        return {"offsets": offs}

    def cmd_preview_offsets(self):
        # Enviar offsets actuales y pasar a RUN para validar visualmente
        def task():
            try:
                payload = self._collect_offsets()
                # Nota: el firmware actual persiste en NVS al POST /calib.
                # Se aplica y se pone RUN para verlos en marcha.
                http_post_json(f"{self.base_url()}/calib", payload, timeout=2.5)
                http_get(f"{self.base_url()}/mode?state=preview", timeout=2.0)
                self.status.set("Offsets aplicados y PREVIEW (90°+offset) para validar.")
            except (URLError, HTTPError) as e:
                self.status.set(f"Error en preview offsets: {e}")
        threading.Thread(target=task, daemon=True).start()

    def cmd_save_offsets(self):
        # Persistir offsets en NVS (POST /calib). Mantener estado actual.
        def task():
            try:
                payload = self._collect_offsets()
                http_post_json(f"{self.base_url()}/calib", payload, timeout=2.5)
                self.status.set("Offsets guardados en NVS.")
                messagebox.showinfo("Calibración", "Offsets guardados correctamente en Sally (NVS).")
            except (URLError, HTTPError) as e:
                self.status.set(f"Error guardando offsets: {e}")
                messagebox.showerror("Calibración", f"No se pudieron guardar:\n{e}")
        threading.Thread(target=task, daemon=True).start()

if __name__ == "__main__":
    CalibApp().mainloop()
