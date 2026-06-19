from ultralytics import YOLO
import cv2, time, torch, numpy as np, requests

# ========= Config =========
MODEL_PATH  = r"C:\Users\lukis\Documents\NEURO\SALLY\Coding\YOLO Sally\my_model\my_model.pt"
CAM_URL     = "http://192.168.4.9/frame"   # ajusta si tu ESP32-CAM usa otra IP
DESIRED_FPS = 10
WINDOW_NAME = "YOLO Salamandra - Detección + Lógica de Movimiento"

COLORS = {'Obstacle': (255, 0, 0), 'Prey': (0, 0, 255), 'Predator': (0, 140, 255)}
CONF_THR = 0.65
ANG_FRONT_ABS = 15.0  # ±15° se considera FRENTE para apetente

# ====== RANGOS DE ÁREA (CLAMP por clase) ======
AREA_RANGES = {
    "Predator": dict(far=2500,  near=35000),
    "Obstacle": dict(far=700,   near=8000),
    "Prey":     dict(far=1600,  near=25000)
}

# ====== ÚNICO CAMBIO: rango configurable de k_response ======
K_MIN = 1.0
K_MAX = 3.0

# ========= Utils =========
def get_esp32_frame(url: str, timeout: float = 2.0):
    try:
        r = requests.get(url, timeout=timeout, headers={"Cache-Control":"no-cache","Pragma":"no-cache"})
        if r.status_code != 200: return None
        arr = np.frombuffer(r.content, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None

def horiz_angle_from_centroid(cx: float, W: int) -> float:
    norm = (cx - (W/2.0)) / (W/2.0)   # [-1,1]
    return float(np.clip(norm * 90.0, -90.0, 90.0))

def dir_from_angle(angle: float) -> str:
    if angle < -ANG_FRONT_ABS: return "IZQ"
    if angle >  ANG_FRONT_ABS: return "DER"
    return "FRENTE"

def dir_por_naturaleza(angle: float, naturaleza: str) -> str:
    # Para aversivo/obstáculo: IZQ/DER sin FRENTE; para apetente: usa zona FRENTE
    if naturaleza in ("aversivo", "obstaculo"):
        return "DER" if angle >= 0 else "IZQ"
    return dir_from_angle(angle)

def movimiento_por_naturaleza(naturaleza: str, dir_estimulo: str) -> str:
    if naturaleza == "apetente":
        return {"IZQ":"IR_IZQUIERDA","DER":"IR_DERECHA","FRENTE":"IR_FRENTE"}[dir_estimulo]
    return {"IZQ":"GIRAR_DERECHA","DER":"GIRAR_IZQUIERDA","FRENTE":"RETROCEDER"}[dir_estimulo]

# ====== Cálculos de pct y k_response ======
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def normalize_between(v, lo, hi):
    if hi == lo: return 0.0
    t = (v - lo) / (hi - lo)
    return clamp(t, 0.0, 1.0)

def compute_pct(angle_deg: float, naturaleza: str) -> float:
    a = clamp(abs(angle_deg), 0.0, 90.0)
    if naturaleza == "apetente":          # mayor |ángulo| ⇒ mayor pct
        pct = a / 90.0
    else:                                  # obstáculo/aversivo: menor |ángulo| ⇒ mayor pct
        pct = 1.0 - (a / 90.0)
    if naturaleza == "aversivo":           # depredador = doble que obstáculo
        pct *= 2.0
    return clamp(pct, 0.0, 1.0)

def compute_k_response(area_px: float, naturaleza: str) -> float:
    """
    k_response ∈ [K_MIN, K_MAX] (configurable)
    - Prey (apetente): lejos (área chica) ⇒ k alto; cerca ⇒ k bajo
      k = K_MAX - (K_MAX-K_MIN)*t
    - Obstacle: cerca ⇒ k alto; lejos ⇒ k bajo
      k = K_MIN + (K_MAX-K_MIN)*t
    - Predator: doble que obstáculo (y clamp a [K_MIN, K_MAX])
    """
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

    if naturaleza == "apetente":
        k = K_MAX - span * t
    elif naturaleza == "obstaculo":
        k = K_MIN + span * t
    else:
        k_obs = K_MIN + span * t
        k = 2.0 * k_obs  # doble que obstáculo
    return clamp(k, K_MIN, K_MAX)

# ========= Modelo =========
model  = YOLO(MODEL_PATH)
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model.to(device)
print(f"Modelo cargado en: {device.upper()}  |  'q' para salir")

prev_t, last_print = 0.0, time.time()

while True:
    now = time.time()
    if now - prev_t < (1.0 / DESIRED_FPS):
        if (cv2.waitKey(1) & 0xFF) == ord("q"): break
        continue
    prev_t = now

    frame = get_esp32_frame(CAM_URL, timeout=2.0)
    if frame is None:
        cv2.imshow(WINDOW_NAME, np.zeros((240,320,3), np.uint8))
        if (cv2.waitKey(1) & 0xFF) == ord("q"): break
        continue

    H, W = frame.shape[:2]
    results = model(frame, stream=True, imgsz=320, verbose=False)

    areas = {'Obstacle': [], 'Prey': [], 'Predator': []}
    dets  = []

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf   = float(box.conf[0])
            label  = model.names[cls_id]
            if conf < CONF_THR: continue

            x1,y1,x2,y2 = map(int, box.xyxy[0])
            area = max(0, (x2-x1)*(y2-y1))
            cx, cy = (x1+x2)/2.0, (y1+y2)/2.0
            angle  = horiz_angle_from_centroid(cx, W)

            if label == "Predator":   naturaleza = "aversivo"
            elif label == "Obstacle": naturaleza = "obstaculo"
            elif label == "Prey":     naturaleza = "apetente"
            else:                     naturaleza = "obstaculo"

            if label in areas: areas[label].append(area)
            dets.append({"label":label,"area":area,"cx":cx,"cy":cy,"angle":angle,"naturaleza":naturaleza})

            color = COLORS.get(label,(0,255,0))
            cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)
            cv2.circle(frame,(int(cx),int(cy)),3,color,-1)
            cv2.putText(frame,f"{label} {area}px ang={angle:.1f}",
                        (x1, max(20,y1-7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Prioridad: aversivo > obstáculo > apetente
    objetivo = None
    for nat in ("aversivo","obstaculo","apetente"):
        cand = [d for d in dets if d["naturaleza"] == nat]
        if cand:
            objetivo = max(cand, key=lambda d: d["area"])
            break

    dir_estimulo, movimiento, angulo, nat = "N/A","N/A",0.0,"ninguno"
    pct, k_response = 0.0, K_MIN

    if objetivo:
        angulo = objetivo["angle"]
        nat = objetivo["naturaleza"]
        dir_estimulo = dir_por_naturaleza(angulo, nat)
        movimiento   = movimiento_por_naturaleza(nat, dir_estimulo)

        # Solo con el estímulo que rige:
        pct         = compute_pct(angulo, nat)
        k_response  = compute_k_response(objetivo["area"], nat)

        cv2.putText(frame,
            f"OBJ:{objetivo['label']} nat={nat} ang={angulo:.1f} ({dir_estimulo}) MOV={movimiento}  pct={pct:.2f}  k={k_response:.2f}",
            (10, H-20), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (50,255,50), 2)
    else:
        cv2.putText(frame, "Sin objetivos", (10, H-20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,200,200), 2)

    cv2.imshow(WINDOW_NAME, frame)

    if time.time() - last_print >= 2:
        print("─"*42)
        for k in ['Obstacle','Prey','Predator']:
            if areas[k]:
                print(f"- {k}: áreas = {areas[k]} (prom={np.mean(areas[k]):.1f})")
            else:
                print(f"- {k}: N/A")
        print(f"> Decisión: nat={nat} estímulo={dir_estimulo} ángulo={angulo:.1f}°  pct={pct:.2f}  k_response={k_response:.2f}  movimiento={movimiento}")
        last_print = time.time()

    if (cv2.waitKey(1) & 0xFF) == ord("q"): break

cv2.destroyAllWindows()
print("Cámara cerrada.")
