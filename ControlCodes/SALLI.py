# SALLY_DEMO_LOCALCAM.py — Demo: cámara local + decisiones de Sally sin saturar Wi-Fi
# - Fuente de video: "Local webcam" (cv2.VideoCapture) o "HTTP /frame" (opcional)
# - Teleoperación manual: /drive?dir=...&pct=..&resp=..
# - Modo neuronal (YOLO): sin dibujar boxes; solo envía comandos cada nn_cmd_period
# - Cámara en Tkinter sin afectar la red (cuando se usa webcam local)

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading, time, io, os, sys
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

DEFAULT_MODEL_PATH = r"C:\Users\lukis\Documents\NEURO\SALLY\Coding\YOLO Sally\my_model\my_model.pt"

# ====== LIMITES DEL VISOR DE CÁMARA ======
CAM_MAX_W = 640   # ancho máximo del visor
CAM_MAX_H = 480   # alto máximo del visor

# ---- Imagen (Pillow) ----
try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None

# ---- OpenCV (webcam local) ----
try:
    import cv2
    import numpy as np
    _CV_OK = True
except Exception:
    _CV_OK = False
    cv2 = None
    np  = None

# ---- YOLO (modo neuronal) ----
try:
    from ultralytics import YOLO
    _YOLO_OK = True
except Exception:
    _YOLO_OK = False

# ===================== Defaults =====================
DEFAULT_HOST      = "192.168.4.1"   # ESP32 (SallyAP)
DEFAULT_PORT      = 80
DEFAULT_CAM_HOST  = "10.224.7.99"   # Solo si usas HTTP /frame
DEFAULT_CAM_PORT  = 80

APP_FONT_FAMILY = "Yu Gothic UI Semilight"
APP_FONT_SIZE   = 13

# ===================== Utilidades red =====================
def http_get(url: str, timeout=2.0) -> str:
    with urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

def http_get_bytes(url: str, timeout=2.0) -> bytes:
    req = Request(url, headers={"Cache-Control":"no-cache","Pragma":"no-cache"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()

# ===================== Lógica neuronal =====================
CONF_THR = 0.5
ANG_FRONT_ABS = 15.0  # ±15° = FRENTE para apetente

AREA_RANGES = {
    "Predator": dict(far=2500,  near=45000),
    "Obstacle": dict(far=700,   near=40000),
    "Prey":     dict(far=1600,  near=25000)
}

K_MIN = 0.25
K_MAX = 2.0

def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v

def normalize_between(v, lo, hi):
    if hi == lo: return 0.0
    t = (v - lo) / (hi - lo)
    return clamp(t, 0.0, 1.0)

def horiz_angle_from_centroid(cx: float, W: int) -> float:
    norm = (cx - (W/2.0)) / (W/2.0)   # [-1, 1]
    return float(clamp(norm * 90.0, -90.0, 90.0))

def dir_from_angle(angle: float) -> str:
    if angle < -ANG_FRONT_ABS: return "IZQ"
    if angle >  ANG_FRONT_ABS: return "DER"
    return "FRENTE"

def dir_por_naturaleza(angle: float, naturaleza: str) -> str:
    # aversivo/obstáculo: forzar IZQ/DER (sin FRENTE)
    if naturaleza in ("aversivo", "obstaculo"):
        return "DER" if angle >= 0 else "IZQ"
    return dir_from_angle(angle)

def movimiento_por_naturaleza(naturaleza: str, dir_estimulo: str) -> str:
    if naturaleza == "apetente":
        return {"IZQ":"IR_IZQUIERDA","DER":"IR_DERECHA","FRENTE":"IR_FRENTE"}[dir_estimulo]
    return {"IZQ":"GIRAR_DERECHA","DER":"GIRAR_IZQUIERDA","FRENTE":"RETROCEDER"}[dir_estimulo]

def compute_pct(angle_deg: float, naturaleza: str) -> float:
    a = clamp(abs(angle_deg), 0.0, 90.0)
    if naturaleza == "apetente":          # mayor |ángulo| ⇒ mayor pct
        pct = 1.0 - (a / 90.0)
    else:                                  # obstáculo/aversivo: menor |ángulo| ⇒ mayor pct
        pct = a / 90.0
    if naturaleza == "aversivo":           # depredador = doble que obstáculo
        pct *= 2.0
    return clamp(pct, 0.0, 1.0)

def compute_k_response(area_px: float, naturaleza: str, pct: float) -> float:
    if naturaleza == "apetente":
        key = "Prey"
    elif naturaleza == "obstaculo":
        key = "Obstacle"
    else:
        key = "Predator"
    r = AREA_RANGES[key]
    a = clamp(area_px, r["far"], r["near"])
    t = normalize_between(a, r["far"], r["near"])  # far→0, near→1
    span = (K_MAX - K_MIN)

    if naturaleza == "apetente":          # lejos ⇒ k alto
        k = K_MAX - span * t
    elif naturaleza == "obstaculo":       # cerca ⇒ k alto
        k = K_MIN + span * t
    else:                                 # depredador = doble del obstáculo
        k_obs = K_MIN + span * t
        k = 2.0 * k_obs
    return clamp(k*pct, K_MIN, K_MAX)

def choose_objective(dets):
    for nat in ("aversivo","obstaculo","apetente"):
        cand = [d for d in dets if d["naturaleza"] == nat]
        if cand: return max(cand, key=lambda d: d["area"])
    return None

def guess_nature(label: str) -> str:
    if label == "Predator":   return "aversivo"
    if label == "Obstacle":   return "obstaculo"
    if label == "Prey":       return "apetente"
    return "obstaculo"

# ===================== App =====================
class SallyDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sally — Demo cámara local + decisiones")
        self.geometry("1120x840")
        self.minsize(880, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Estado
        self._cam_running = False
        self._cam_thread  = None
        self._cap         = None           # cv2.VideoCapture
        self._latest_bgr  = None           # último frame (BGR)
        self._latest_lock = threading.Lock()

        self._nn_running  = False
        self._nn_thread   = None
        self._nn_model    = None

        self._cam_imgtk   = None

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        st = ttk.Style(self); st.theme_use("clam")
        st.configure(".", font=(APP_FONT_FAMILY, APP_FONT_SIZE))
        st.configure("TLabel", background="#111", foreground="#eee")
        st.configure("TFrame", background="#111")
        st.configure("TLabelframe", background="#111", foreground="#ddd")
        st.configure("TButton", background="#1d1d1d", foreground="#eee")
        self.configure(bg="#111")

        top = ttk.Frame(self, padding=10); top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(10, weight=1)

        ttk.Label(top, text="Host SallyAP:").grid(row=0, column=0, sticky="e", padx=(0,6))
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        ttk.Entry(top, textvariable=self.host_var, width=16).grid(row=0, column=1, sticky="w")

        ttk.Label(top, text="Puerto:").grid(row=0, column=2, sticky="e", padx=(12,6))
        self.port_var = tk.IntVar(value=DEFAULT_PORT)
        ttk.Entry(top, textvariable=self.port_var, width=6).grid(row=0, column=3, sticky="w")

        ttk.Button(top, text="Probar /drive", command=self.ping).grid(row=0, column=4, padx=8)

        # Botón Offsets (RUN)
        ttk.Button(top, text="Modo Seguro", command=self.preview_offsets).grid(row=0, column=5, padx=8)

        # Fuente de cámara
        ttk.Label(top, text="Fuente:").grid(row=1, column=0, sticky="e", padx=(0,6), pady=(8,0))
        self.cam_source = tk.StringVar(value="Local webcam")
        ttk.Combobox(top, textvariable=self.cam_source, values=["Local webcam","HTTP /frame"], width=16, state="readonly")\
            .grid(row=1, column=1, sticky="w", pady=(8,0))

        self.cam_index_var = tk.IntVar(value=0)
        ttk.Label(top, text="Index cam:").grid(row=1, column=2, sticky="e", padx=(12,6), pady=(8,0))
        ttk.Entry(top, textvariable=self.cam_index_var, width=5).grid(row=1, column=3, sticky="w", pady=(8,0))

        ttk.Label(top, text="Cam IP:").grid(row=1, column=4, sticky="e", padx=(12,6), pady=(8,0))
        self.cam_host_var = tk.StringVar(value=DEFAULT_CAM_HOST)
        ttk.Entry(top, textvariable=self.cam_host_var, width=16).grid(row=1, column=5, sticky="w", pady=(8,0))

        ttk.Label(top, text="Cam Port:").grid(row=1, column=6, sticky="e", padx=(12,6), pady=(8,0))
        self.cam_port_var = tk.IntVar(value=DEFAULT_CAM_PORT)
        ttk.Entry(top, textvariable=self.cam_port_var, width=6).grid(row=1, column=7, sticky="w", pady=(8,0))

        # Sliders pct/resp
        sliders = ttk.Frame(self, padding=(10,0)); sliders.grid(row=1, column=0, sticky="ew")
        sliders.grid_columnconfigure(1, weight=1)

        self.pct_var = tk.IntVar(value=50)
        self.resp_var = tk.IntVar(value=50)

        ttk.Label(sliders, text="Lateralidad (pct)").grid(row=0, column=0, sticky="w")
        ttk.Scale(sliders, from_=0, to=100, orient="horizontal", variable=self.pct_var)\
            .grid(row=0, column=1, sticky="ew", padx=8)

        ttk.Label(sliders, text="Respuesta (resp)").grid(row=1, column=0, sticky="w", pady=(8,0))
        ttk.Scale(sliders, from_=0, to=100, orient="horizontal", variable=self.resp_var)\
            .grid(row=1, column=1, sticky="ew", padx=8)

        # Botones manuales
        btns = ttk.Frame(self, padding=(10,10)); btns.grid(row=2, column=0, sticky="ew")
        btns.grid_columnconfigure((0,1,2,3), weight=1)

        ttk.Button(btns, text="← Izquierda", command=lambda: self.drive("left")).grid(row=0, column=0, padx=6, sticky="ew")
        ttk.Button(btns, text="↑ Adelante",  command=lambda: self.drive("fwd")).grid (row=0, column=1, padx=6, sticky="ew")
        ttk.Button(btns, text="→ Derecha",   command=lambda: self.drive("right")).grid(row=0, column=2, padx=6, sticky="ew")
        ttk.Button(btns, text="■ Stop",      command=lambda: self.drive("stop")).grid (row=0, column=3, padx=6, sticky="ew")

        # Estado
        status = ttk.Frame(self, padding=(10,0)); status.grid(row=3, column=0, sticky="ew")
        status.grid_columnconfigure(0, weight=1)
        self.status = tk.StringVar(value="Listo.")
        ttk.Label(status, textvariable=self.status).grid(row=0, column=0, sticky="w")

        # Cámara
        cam = ttk.Frame(self, padding=(10,10)); cam.grid(row=4, column=0, sticky="nsew")
        cam.grid_columnconfigure(6, weight=1)
        ttk.Label(cam, text="FPS visor").grid(row=0, column=0, sticky="e")
        self.cam_fps_var = tk.IntVar(value=12)
        ttk.Spinbox(cam, from_=1, to=60, textvariable=self.cam_fps_var, width=5).grid(row=0, column=1, sticky="w", padx=(6,12))
        ttk.Button(cam, text="Iniciar cámara", command=self.cam_start).grid(row=0, column=2, padx=6)
        ttk.Button(cam, text="Detener cámara", command=self.cam_stop).grid (row=0, column=3, padx=6)

        self.cam_panel = ttk.Label(cam, text="(sin imagen)")
        self.cam_panel.grid(row=1, column=0, columnspan=8, sticky="nsew", pady=(10,0))
        cam.grid_rowconfigure(1, weight=1)

        # Modo neuronal
        nn = ttk.LabelFrame(self, text="Modo Neuronal (YOLO → /drive)", padding=(10,8))
        nn.grid(row=5, column=0, sticky="ew", padx=10, pady=(0,10))
        nn.grid_columnconfigure(10, weight=1)

        ttk.Label(nn, text="Modelo (.pt):").grid(row=0, column=0, sticky="e")
        self.model_path = tk.StringVar(value=DEFAULT_MODEL_PATH)
        ttk.Entry(nn, textvariable=self.model_path, width=60).grid(row=0, column=1, columnspan=6, sticky="ew", padx=6)
        ttk.Button(nn, text="…", command=self._pick_model).grid(row=0, column=7, padx=4)

        ttk.Label(nn, text="Hz inferencia").grid(row=1, column=0, sticky="e", pady=(6,0))
        self.nn_hz = tk.IntVar(value=8)
        ttk.Spinbox(nn, from_=1, to=30, textvariable=self.nn_hz, width=5).grid(row=1, column=1, sticky="w", padx=(6,12), pady=(6,0))

        ttk.Label(nn, text="Período cmd (s)").grid(row=1, column=2, sticky="e", pady=(6,0))
        self.nn_cmd_period = tk.DoubleVar(value=1.0)
        ttk.Spinbox(nn, from_=0.1, to=5.0, increment=0.1, textvariable=self.nn_cmd_period, width=6)\
            .grid(row=1, column=3, sticky="w", padx=(6,12), pady=(6,0))

        ttk.Button(nn, text="▶ Activar neuronal", command=self.nn_start).grid(row=1, column=4, padx=6, pady=(6,0))
        ttk.Button(nn, text="■ Detener neuronal", command=self.nn_stop).grid (row=1, column=5, padx=6, pady=(6,0))

        self.last_nn = tk.StringVar(value="Neuronal: inactivo.")
        ttk.Label(nn, textvariable=self.last_nn).grid(row=2, column=0, columnspan=8, sticky="w", pady=(8,0))

        # Expandir
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Atajos
        self.bind("<Left>",  lambda e: self.drive("left"))
        self.bind("<Right>", lambda e: self.drive("right"))
        self.bind("<Up>",    lambda e: self.drive("fwd"))
        self.bind("<space>", lambda e: self.drive("stop"))

    # ---------- Helpers ----------
    def base_url(self):
        return f"http://{self.host_var.get().strip()}:{int(self.port_var.get())}"

    def cam_base_url(self):
        return f"http://{self.cam_host_var.get().strip()}:{int(self.cam_port_var.get())}"

    # ---------- Comandos ----------
    def ping(self):
        def task():
            try:
                data = http_get(f"{self.base_url()}/drive?dir=stop", timeout=1.5)
                self.status.set(f"OK SallyAP: {data[:90]}")
            except Exception as e:
                self.status.set(f"No conectado: {e}")
        threading.Thread(target=task, daemon=True).start()

    def drive(self, direction: str):
        def task():
            params = {
                "dir":  direction,
                "pct":  max(0, min(100, self.pct_var.get())),
                "resp": max(0, min(100, self.resp_var.get()))
            }
            try:
                url = f"{self.base_url()}/drive?{urlencode(params)}"
                payload = http_get(url, timeout=1.8)
                self.status.set(f"Enviado: {direction} • {payload[:100]}")
            except Exception as e:
                self.status.set(f"Error /drive: {e}")
        threading.Thread(target=task, daemon=True).start()

    def preview_offsets(self):
        def task():
            try:
                payload = http_get(f"{self.base_url()}/mode?state=preview", timeout=2.0)
                self.status.set(f"Offsets: PREVIEW/RUN aplicado. Respuesta: {payload[:90]}")
            except Exception as e:
                self.status.set(f"Error preview offsets: {e}")
        threading.Thread(target=task, daemon=True).start()

    # ---------- Cámara ----------
    def cam_start(self):
        if Image is None or ImageTk is None:
            self.status.set("Falta Pillow: pip install pillow")
            return
        if self._cam_running:
            self.status.set("Cámara ya en marcha.")
            return

        src = self.cam_source.get()
        if src == "Local webcam" and not _CV_OK:
            self.status.set("Falta OpenCV: pip install opencv-python")
            return

        if src == "Local webcam":
            idx = int(self.cam_index_var.get())
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap or not cap.isOpened():
                self.status.set(f"No se pudo abrir webcam index {idx}.")
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap = cap

        self._cam_running = True
        self._cam_thread = threading.Thread(target=self._cam_loop, daemon=True)
        self._cam_thread.start()
        self.status.set(f"Cámara iniciada ({src}).")

    def cam_stop(self):
        self._cam_running = False
        if self._cap is not None:
            try: self._cap.release()
            except: pass
            self._cap = None
        self.status.set("Cámara detenida.")

    def _cam_loop(self):
        last_err_t = 0.0
        src = self.cam_source.get()
        while self._cam_running:
            t0 = time.time()
            frame_bgr = None

            try:
                if src == "Local webcam":
                    ok, frame_bgr = self._cap.read()
                    if not ok or frame_bgr is None:
                        raise RuntimeError("webcam no entrega frames")
                else:
                    raw = http_get_bytes(f"{self.cam_base_url()}/frame", timeout=1.5)
                    arr = np.frombuffer(raw, dtype=np.uint8)
                    frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame_bgr is None:
                        raise RuntimeError("cv2.imdecode()=None")
            except Exception as e:
                if time.time() - last_err_t > 1.5:
                    self.status.set(f"Cam error: {e}")
                    last_err_t = time.time()
                time.sleep(0.05)
                continue

            # Publicar frame para el modo neuronal
            with self._latest_lock:
                self._latest_bgr = frame_bgr.copy()

            # Redimensionar con límites fijos
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            h, w = frame_rgb.shape[:2]
            scale = min(CAM_MAX_W / float(w), CAM_MAX_H / float(h), 1.0)
            new_w = int(w * scale)
            new_h = int(h * scale)
            disp = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

            img = Image.fromarray(disp)
            imgtk = ImageTk.PhotoImage(img)
            self.after(0, lambda imgtk=imgtk: self._update_cam(imgtk))

            # fps loop
            fps = int(self.cam_fps_var.get()) if str(self.cam_fps_var.get()).isdigit() else 10
            fps = max(1, min(60, fps))
            period = 1.0 / float(fps)
            dt = time.time() - t0
            if dt < period: time.sleep(period - dt)

    def _update_cam(self, imgtk):
        self._cam_imgtk = imgtk
        self.cam_panel.configure(image=imgtk, text="")

    # ---------- Modo neuronal ----------
    def _pick_model(self):
        p = filedialog.askopenfilename(title="Seleccionar modelo YOLO (.pt)",
                                       filetypes=[("PyTorch/Ultralytics", "*.pt *.pth"), ("Todos", "*.*")])
        if p: self.model_path.set(p)

    def nn_start(self):
        if self._nn_running:
            self.last_nn.set("Neuronal: ya activo.")
            return
        if not _YOLO_OK or not _CV_OK:
            messagebox.showerror("YOLO", "Instala 'ultralytics' y 'opencv-python' para el modo neuronal.")
            return
        model_file = self.model_path.get().strip()
        if not os.path.exists(model_file):
            messagebox.showerror("YOLO", f"No se encontró el modelo:\n{model_file}")
            return
        try:
            self._nn_model = YOLO(model_file)
            self.last_nn.set("Modelo cargado. Iniciando…")
        except Exception as e:
            messagebox.showerror("YOLO", f"Falló carga del modelo:\n{e}")
            return

        self._nn_running = True
        self._nn_thread = threading.Thread(target=self._nn_loop, daemon=True)
        self._nn_thread.start()

    def nn_stop(self):
        self._nn_running = False
        self.last_nn.set("Neuronal: detenido.")

    def _nn_loop(self):
        cmd_period = max(0.1, float(self.nn_cmd_period.get()))
        send_interval = cmd_period
        last_send = 0.0

        MEMORY_WINDOW = 5.0   # segundos de "memoria" del último estímulo
        IDLE_TIMEOUT  = 5.5   # tras esto, si no hay estímulo, sí se va a idle

        last_detection_time = time.time()
        idle_sent = False

        # memoria del último comando derivado de un estímulo
        last_cmd = None  # dict con dir_net, pct_100, resp_100, nat, mov, angle, area

        while self._nn_running:
            t0 = time.time()
            # Toma el último frame local disponible
            with self._latest_lock:
                if self._latest_bgr is None:
                    need_sleep = True
                else:
                    frame = self._latest_bgr.copy()
                    need_sleep = False

            if need_sleep:
                time.sleep(0.05)
                continue

            H, W = frame.shape[:2]

            try:
                results = self._nn_model(frame, stream=True, imgsz=320, verbose=False)
            except Exception as e:
                self.after(0, lambda: self.last_nn.set(f"Neuronal: error inferencia ({e})"))
                time.sleep(0.2)
                continue

            dets = []
            try:
                for r in results:
                    for box in r.boxes:
                        conf   = float(box.conf[0])
                        if conf < CONF_THR:
                            continue
                        cls_id = int(box.cls[0])
                        label  = self._nn_model.names[cls_id] if hasattr(self._nn_model, "names") else str(cls_id)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        area = max(0, (x2 - x1) * (y2 - y1))
                        cx   = (x1 + x2) / 2.0
                        angle = horiz_angle_from_centroid(cx, W)
                        nat   = guess_nature(label)
                        dets.append({"label": label, "area": area, "angle": angle, "naturaleza": nat})
            except Exception:
                pass

            objetivo = choose_objective(dets)
            now = time.time()

            # -------- SIN OBJETIVO: usar memoria si existe y no han pasado > MEMORY_WINDOW --------
            if objetivo is None:
                time_since = now - last_detection_time

                # Si aún estamos dentro de la "memoria" y hay un último comando, lo repetimos
                if last_cmd is not None and time_since <= MEMORY_WINDOW:
                    if now - last_send >= send_interval:
                        last_send = now

                        def send_mem(cmd=last_cmd, t_since=time_since):
                            try:
                                params = {
                                    "dir":  cmd["dir_net"],
                                    "pct":  cmd["pct_100"],
                                    "resp": cmd["resp_100"],
                                }
                                payload = http_get(f"{self.base_url()}/drive?{urlencode(params)}", timeout=1.8)
                                txt = (f"Neuronal (mem {t_since:.1f}s) → /drive "
                                       f"dir={cmd['dir_net']} pct={cmd['pct_100']} resp={cmd['resp_100']} "
                                       f"| nat={cmd['nat']} mov={cmd['mov']}")
                                self.after(0, lambda: self.last_nn.set(txt))
                                self.after(0, lambda: self.status.set(f"OK /drive (memoria): {payload[:90]}"))
                            except Exception as e:
                                self.after(0, lambda: self.last_nn.set(f"Neuronal: error /drive (mem) ({e})"))
                        threading.Thread(target=send_mem, daemon=True).start()

                    dt = time.time() - t0
                    sleep_t = max(0.0, send_interval - dt)
                    if sleep_t > 0:
                        time.sleep(sleep_t)
                    continue

                # Si no hay memoria o ya pasó la ventana, sí se detiene y eventualmente pasa a idle
                if now - last_send >= send_interval:
                    last_send = now

                    def send_stop():
                        try:
                            payload = http_get(
                                f"{self.base_url()}/drive?{urlencode({'dir': 'stop', 'pct': 0, 'resp': 0})}",
                                timeout=1.5,
                            )
                            self.after(0, lambda: self.last_nn.set("Neuronal: sin objetivo → stop"))
                            self.after(0, lambda: self.status.set(f"OK /drive stop: {payload[:90]}"))
                        except Exception as e:
                            self.after(0, lambda: self.last_nn.set(f"Neuronal: error /drive stop ({e})"))
                    threading.Thread(target=send_stop, daemon=True).start()

                if (now - last_detection_time) > IDLE_TIMEOUT and not idle_sent:
                    idle_sent = True

                    def send_idle():
                        try:
                            payload = http_get(
                                f"{self.base_url()}/mode?{urlencode({'state': 'idle'})}",
                                timeout=1.5,
                            )
                            self.after(0, lambda: self.last_nn.set("Neuronal: >5s sin estímulo → mode=idle"))
                            self.after(0, lambda: self.status.set(f"OK /mode idle: {payload[:90]}"))
                        except Exception as e:
                            self.after(0, lambda: self.last_nn.set(f"Neuronal: error /mode idle ({e})"))
                    threading.Thread(target=send_idle, daemon=True).start()

                dt = time.time() - t0
                sleep_t = max(0.0, send_interval - dt)
                if sleep_t > 0:
                    time.sleep(sleep_t)
                continue

            # -------- HUBO OBJETIVO: se actualiza memoria y se envía acción --------
            last_detection_time = now
            idle_sent = False

            angle = objetivo["angle"]
            nat   = objetivo["naturaleza"]
            dir_est = dir_por_naturaleza(angle, nat)
            mov    = movimiento_por_naturaleza(nat, dir_est)
            pct    = compute_pct(angle, nat)
            kresp  = compute_k_response(objetivo["area"], nat, pct)

            if mov in ("IR_IZQUIERDA", "GIRAR_IZQUIERDA"):
                dir_net = "left"
            elif mov in ("IR_DERECHA", "GIRAR_DERECHA"):
                dir_net = "right"
            elif mov == "IR_FRENTE":
                dir_net = "fwd"
            elif mov == "RETROCEDER":
                dir_net = "back"
            else:
                dir_net = "stop"

            pct_100  = int(round(pct * 100))
            resp_100 = int(
                round(((kresp - K_MIN) / max(1e-6, (K_MAX - K_MIN))) * 100)
            )

            # actualizar memoria del último comando
            last_cmd = {
                "dir_net": dir_net,
                "pct_100": pct_100,
                "resp_100": resp_100,
                "nat": nat,
                "mov": mov,
                "angle": angle,
                "area": objetivo["area"],
            }

            if now - last_send >= send_interval:
                last_send = now

                def send_task(cmd=last_cmd):
                    try:
                        params = {"dir": cmd["dir_net"], "pct": cmd["pct_100"], "resp": cmd["resp_100"]}
                        payload = http_get(f"{self.base_url()}/drive?{urlencode(params)}", timeout=1.8)
                        txt = (
                            f"Neuronal → /drive dir={cmd['dir_net']} pct={cmd['pct_100']} resp={cmd['resp_100']} | "
                            f"nat={cmd['nat']} ang={cmd['angle']:.1f}° area={cmd['area']} mov={cmd['mov']}"
                        )
                        self.after(0, lambda: self.last_nn.set(txt))
                        self.after(0, lambda: self.status.set(f"OK /drive: {payload[:90]}"))
                    except Exception as e:
                        self.after(0, lambda: self.last_nn.set(f"Neuronal: error /drive ({e})"))
                threading.Thread(target=send_task, daemon=True).start()

            dt = time.time() - t0
            sleep_t = max(0.0, send_interval - dt)
            if sleep_t > 0:
                time.sleep(sleep_t)

        self.after(0, lambda: self.last_nn.set("Neuronal: detenido."))

    # ---------- Cierre ----------
    def _on_close(self):
        try:
            self._nn_running  = False
            self._cam_running = False
        except:
            pass
        try:
            if self._cap is not None:
                self._cap.release()
        except:
            pass
        self.destroy()

# ===================== Main =====================
if __name__ == "__main__":
    app = SallyDemo()
    app.mainloop()
