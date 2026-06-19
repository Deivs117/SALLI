// Sally - Maestro SoftAP con marchas + calibración por offsets (NVS)
// Basado en tu código base de marchas; integra /mode (run|calib|idle) y /calib (GET/POST).
// - En MODE_CALIB publica 90° en todos los canales (vista neutra).
// - En MODE_RUN aplica offsets guardados a las LUT antes de publicar.
// - Offsets persistidos en NVS ("sally"/"offsets") como 14 enteros signed (-45..+45).

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_mac.h"
#include "esp_http_server.h"
#include "esp_timer.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ======= AP config =======
static const char *TAG = "Master_AP";
#define AP_SSID     "SallyAP"
#define AP_PASS     "Sally1234"
#define AP_CHANNEL  6
#define AP_MAX_CONN 8

// ======= Banco de 8 IDs (mixto 1 o 4 ángulos) =======
typedef struct {
    uint8_t count;  // 1 o 4
    int     a[4];   // usa a[0..count-1]
} dev_payload_t;

static dev_payload_t bank[8] = {
    {4, { 90, 90, 90, 90}}, // ID 0  (patas frente: 4)
    {1, { 90,  0,  0,  0}}, // ID 1  (spine 0)
    {1, { 90,  0,  0,  0}}, // ID 2  (spine 1)
    {1, { 90,  0,  0,  0}}, // ID 3  (spine 2)
    {4, { 90, 90, 90, 90}}, // ID 4  (patas traseras: 4)
    {1, { 90,  0,  0,  0}}, // ID 5  (spine 3)
    {1, { 90,  0,  0,  0}}, // ID 6  (spine 4)
    {1, { 90,  0,  0,  0}}, // ID 7  (spine 5)
};

// ======= Parámetros de marcha =======
static volatile int   period_ms       = 50;         // periodo de actualización ("FPS")
static volatile int   gait_period_ms  = 1300;       // ciclo de marcha
static volatile float max_dps         = 125.0f;     // límite vel. (°/s)

// Modos de paso
typedef enum { GAIT_TROT = 0, GAIT_WALK = 1 } gait_t;
static volatile gait_t gait_mode = GAIT_WALK;

// Bias/amplitudes (°)
static volatile float hip_amp_deg    = 50.0f;
static volatile float hip_bias_deg   = 90.0f;
static volatile float knee_amp_deg   = 18.0f;
static volatile float knee_bias_deg  = 110.0f;

static volatile float spine_amp_deg  = 50.0f;
static volatile float spine_bias_deg = 90.0f;
static volatile float spine_dphi_rad = (float)M_PI/6.0f;

// LUTs
#define LUT_N 200
static int16_t lut_legs_front[4][LUT_N]; // [FR_hip, FR_knee, FL_hip, FL_knee]
static int16_t lut_legs_rear [4][LUT_N]; // [RR_hip, RR_knee, RL_hip, RL_knee]
static int16_t lut_spine     [6][LUT_N]; // spine 0..5
static volatile int lut_idx = 0;

// Estado suavizado
static int16_t cur_id0[4], cur_id4[4], cur_spine[6];
static esp_timer_handle_t g_timer = NULL;

// Acoplamiento columna↔patas
static volatile float spine_gain_fore_deg = 15.0f;
static volatile float spine_gain_hind_deg = 15.0f;
// ===== Pesos de columna (acople patas↔columna) por marcha =====
// Marcha frontal (recto)
static const float W_fore_F[6] = { 1.25f, 0.00f,  0.4f, 0.5f, 0.2f, 0.0f };
static const float W_hind_F[6] = { 0.40f, 1.00f, -5.25f, 0.8f, 1.25f, 2.0f };
// Marcha hacia la IZQUIERDA
static const float W_fore_L[6] = { 5.25f, 0.00f, 0.40f, 0.5f, 0.2f, 0.0f };
static const float W_hind_L[6] = { 0.40f, 3.00f, -5.25f, 0.8f, 1.25f, 2.0f };
// Marcha hacia la DERECHA
static const float W_fore_R[6] = { 1.25f, 0.75f, 0.40f, 0.50f, 0.20f, 0.00f };
static const float W_hind_R[6] = { 0.40f, 0.75f, 1.25f, 0.80f, 1.25f, 2.00f };

// Dirección (ya existente en tu lógica)
volatile int8_t  turn_cmd          = 0;     // -1 der, 0 recto, +1 izq
volatile float   turning_percentage = 0.50f; // 0..1
volatile float   k_response         = 0.50f; // 0..1

// ===== Drift lateral constante (bias de giro) =====
// turn_bias ∈ [-1..+1]; positivo favorece GIRO A LA IZQUIERDA.
// Para compensar centro de masa cargado a la derecha, usa +0.30 (30%).
static volatile float turn_bias = 0.35;

// Conducción / congelado
typedef enum { DRIVE_STOP=0, DRIVE_FORWARD=1, DRIVE_LEFT=2, DRIVE_RIGHT=3 } drive_mode_t;
static volatile drive_mode_t drive_mode = DRIVE_STOP;
static volatile bool freeze_motion = false;

// ======= NUEVO: Modo general de control (incluye calibración) =======
typedef enum { MODE_IDLE=0, MODE_DRIVE=1, MODE_CALIB=2, MODE_PREVIEW=3 } ctrl_mode_t;
static volatile ctrl_mode_t g_mode = MODE_IDLE;

static volatile float spine_skew = 1.0f;       // -1 ó +1
static volatile float SPINE_SKEW_GAIN = 0.75f;  // 60% de asimetría máxima

// ======= NUEVO: Offsets de calibración (mapa 14 canales) =======
// Orden de offsets ↔ banco:
// 0..3  -> bank[0].a[0..3]
// 4..6  -> bank[{1,2,3}].a[0]
// 7..10 -> bank[4].a[0..3]
// 11..13-> bank[{5,6,7}].a[0]
#define SERVO_COUNT 14
static int8_t g_offset_deg[SERVO_COUNT]; // -45..+45

// ======= Helpers =======
static inline float smoothstepf(float t) {
    if (t <= 0.0f) return 0.0f;
    if (t >= 1.0f) return 1.0f;
    return t*t*(3.0f - 2.0f*t);
}
static inline int clamp_deg(int v) { if (v < 0) return 0; if (v > 180) return 180; return v; }
static inline int16_t approach_deg(int16_t cur, int16_t target, float dt_s, float max_deg_per_s) {
    float max_step = max_deg_per_s * dt_s;
    float d = (float)target - (float)cur;
    if (d >  max_step) d =  max_step;
    if (d < -max_step) d = -max_step;
    int val = (int)lrintf((float)cur + d);
    return (int16_t)clamp_deg(val);
}

// Perfil de pata (apoyo/vuelo)
static inline void leg_profile(float u, float duty, float dir,
                               float hip_bias, float hip_amp_stance, float hip_amp_swing,
                               float knee_bias, float knee_amp_stance, float knee_amp_swing,
                               float* hip_out, float* knee_out)
{
    u = u - floorf(u);
    if (u < duty) {
        float s  = u / duty;
        float sh = smoothstepf(s);
        float hip_rel  = (1.0f - 2.0f*sh);
        float hip_val  = hip_bias + dir * -1.0f * hip_amp_stance * hip_rel;
        float k_rel    = 1.0f - 0.2f * cosf((float)M_PI * (2.0f*sh - 1.0f));
        float knee_val = knee_bias + dir * -1.0f * (knee_amp_stance * (k_rel - 1.0f));
        *hip_out  = hip_val;
        *knee_out = knee_val;
    } else {
        float s  = (u - duty) / (1.0f - duty);
        float sh = smoothstepf(s);
        float hip_rel  = (-1.0f + 2.0f*sh);
        float hip_val  = hip_bias + dir * -1.0f * hip_amp_swing * hip_rel;
        float bell     = sinf((float)M_PI * sh);
        float knee_val = knee_bias + dir * -1.0f * (knee_amp_swing * bell);
        *hip_out  = hip_val;
        *knee_out = knee_val;
    }
}

static inline float stance_weight_soft(float u, float duty, float soft_edge) {
    u = u - floorf(u);
    float half = duty * 0.5f;
    if (half > 0.5f - 1e-6f) half = 0.5f - 1e-6f;
    if (half < 1e-6f)        half = 1e-6f;

    float edge = soft_edge;
    if (edge > half - 1e-6f) edge = half - 1e-6f;
    if (edge < 1e-6f)        edge = 1e-6f;

    float uc = u - half;
    uc = uc - floorf(uc);
    uc -= 0.5f;
    float x = fabsf(uc);

    float a = half - edge;
    float b = half + edge;

    if (x <= a) return 1.0f;
    if (x >= b) return 0.0f;

    float t = (x - a) / (b - a);
    return 0.5f * (1.0f + cosf((float)M_PI * t));
}

// ======= Generación de LUTs (marcha) =======
static void generarTrayectoria(void) {
    // --- NUEVO: preservar la fase actual y el estado suavizado ---
    // Guardamos el índice de fase actual para no “resetear” a 0
    // cada vez que se re-genera la trayectoria por cambios de marcha.
    int preserve_idx = lut_idx % LUT_N;
    if (preserve_idx < 0) preserve_idx += LUT_N;
    static bool s_first_build = true;

    const float DIR_RIGHT = 1.0f; // FR, RR
    const float DIR_LEFT  = -1.0f; // FL, RL
    const float DUTY_STANCE = 0.45f;

    const float HIP_AMP_STANCE = 30.0f;
    const float HIP_AMP_SWING  = 40.0f;
    const float HIP_BIAS       = hip_bias_deg;

    const float KNEE_BIAS       = knee_bias_deg;
    const float KNEE_AMP_STANCE = -5.0f;
    const float KNEE_AMP_SWING  = 30.0f;

    float phi_FR=0.0f, phi_FL=0.0f, phi_RR=0.0f, phi_RL=0.0f;
    if (gait_mode == GAIT_TROT) {
        phi_FR = 0.0f;          phi_RL = (float)M_PI;
        phi_FL = (float)M_PI;   phi_RR = 0.0f;
    } else { // WALK
        phi_FR = 0.0f;
        phi_FL = 0.5f*(float)M_PI;
        phi_RR = (float)M_PI;
        phi_RL = 1.5f*(float)M_PI;
        if(turn_cmd< 0.0f){
            phi_RR = 1.5f*(float)M_PI;
            phi_RL = (float)M_PI;
            SPINE_SKEW_GAIN = 0.75f;
        }
    }

    // --- Nuevo: giro por inversión de swing en HIP para la pata interior ---
    // Base: sin lateralidad por amplitud; solo k_response (mantiene tu compensación de columna).
    const float base_FR = k_response;
    const float base_FL = k_response;
    const float base_RR = k_response;
    const float base_RL = k_response;

    // Signos de swing HIP según giro (turn_cmd: +1=IZQ, -1=DER, 0=recto).
    // Exterior:  +1.0  (normal)
    // Interior:  -turning_percentage  (invierte y escala por pct)
    float s_FR = 1.0f, s_FL = 1.0f, s_RR = 1.0f, s_RL = 1.0f;
    if (turn_cmd > 0) {        // girar IZQ → interior = FL, RL
        s_FL = -1.0f;
        s_RL = -1.0f;
    } else if (turn_cmd < 0) { // girar DER → interior = FR, RR
        s_FR = -1.0f;
        s_RR = -1.0f;
    }

    // ---- Compensación de drift (turn_bias) ----
    // turn_bias ∈ [-1..+1]; >0 favorece IZQUIERDA (deriva a la izq)
    // turning_percentage es tu 0.30 (30%)
    float tb = fminf(fmaxf(turn_bias, -1.0f), 1.0f);
    if (tb != 0.0f) {
        float mag = turning_percentage * fabsf(tb); // p.ej. 0.30 * |tb|
        if (turn_cmd == 0) {
            SPINE_SKEW_GAIN = 0.00f;
            turn_bias = 0.00;
            spine_skew = 1.0f;
            // Solo sesgo cuando no hay giro comandado (deja la lógica de giro intacta)
            if (tb > 0.0f) { // sesgo a IZQ: invierte un 30% las patas izquierdas
                s_FL = -mag;
                s_RL = -mag;
            } else {         // sesgo a DER
                s_FR = -mag;
                s_RR = -mag;
            }
        }
    }
    // Clamp final por seguridad
    s_FR = fminf(fmaxf(s_FR, -1.0f), 1.0f);
    s_FL = fminf(fmaxf(s_FL, -1.0f), 1.0f);
    s_RR = fminf(fmaxf(s_RR, -1.0f), 1.0f);
    s_RL = fminf(fmaxf(s_RL, -1.0f), 1.0f);

    // Escalas finales: afectan SOLO el HIP_AMP_SWING (no stance ni rodillas).
    const float scale_FR = base_FR * s_FR;
    const float scale_FL = base_FL * s_FL;
    const float scale_RR = base_RR * s_RR;
    const float scale_RL = base_RL * s_RL;

    for (int i = 0; i < LUT_N; ++i) {
        float theta = 2.0f * (float)M_PI * ((float)i / (float)LUT_N);
        float u_FR = (theta + phi_FR) / (2.0f*(float)M_PI);
        float u_FL = (theta + phi_FL) / (2.0f*(float)M_PI);
        float u_RR = (theta + phi_RR) / (2.0f*(float)M_PI);
        float u_RL = (theta + phi_RL) / (2.0f*(float)M_PI);

        float FR_hip, FR_knee, FL_hip, FL_knee, RR_hip, RR_knee, RL_hip, RL_knee;

        leg_profile(u_FR, DUTY_STANCE, DIR_RIGHT,
                    HIP_BIAS, HIP_AMP_STANCE * scale_FR, HIP_AMP_SWING * scale_FR,
                    KNEE_BIAS + 9.0f, KNEE_AMP_STANCE, KNEE_AMP_SWING,
                    &FR_hip, &FR_knee);

        leg_profile(u_FL, DUTY_STANCE, DIR_LEFT,
                    HIP_BIAS, HIP_AMP_STANCE * scale_FL, HIP_AMP_SWING * scale_FL,
                    KNEE_BIAS - KNEE_AMP_SWING*2 + 15.0f, KNEE_AMP_STANCE, KNEE_AMP_SWING,
                    &FL_hip, &FL_knee);

        leg_profile(u_RR, DUTY_STANCE, DIR_RIGHT,
                    HIP_BIAS, HIP_AMP_STANCE * scale_RR, HIP_AMP_SWING * scale_RR,
                    KNEE_BIAS + 9.0f, KNEE_AMP_STANCE, KNEE_AMP_SWING,
                    &RR_hip, &RR_knee);

        leg_profile(u_RL, DUTY_STANCE, DIR_LEFT,
                    HIP_BIAS, HIP_AMP_STANCE * scale_RL, HIP_AMP_SWING * scale_RL,
                    KNEE_BIAS - KNEE_AMP_SWING*2 + 15.0f, KNEE_AMP_STANCE, KNEE_AMP_SWING,
                    &RL_hip, &RL_knee);

        lut_legs_front[0][i] = (int16_t)clamp_deg((int)lrintf(FR_hip));
        lut_legs_front[1][i] = (int16_t)clamp_deg((int)lrintf(FR_knee));
        lut_legs_front[2][i] = (int16_t)clamp_deg((int)lrintf(FL_hip));
        lut_legs_front[3][i] = (int16_t)clamp_deg((int)lrintf(FL_knee));

        lut_legs_rear [0][i] = (int16_t)clamp_deg((int)lrintf(RR_hip));
        lut_legs_rear [1][i] = (int16_t)clamp_deg((int)lrintf(RR_knee));
        lut_legs_rear [2][i] = (int16_t)clamp_deg((int)lrintf(RL_hip));
        lut_legs_rear [3][i] = (int16_t)clamp_deg((int)lrintf(RL_knee));
    }

    for (int i = 0; i < LUT_N; ++i) {
        float theta = 2.0f * (float)M_PI * ((float)i / (float)LUT_N);
        float u_FR = (theta + phi_FR) / (2.0f*(float)M_PI);
        float u_FL = (theta + phi_FL) / (2.0f*(float)M_PI);
        float u_RR = (theta + phi_RR) / (2.0f*(float)M_PI);
        float u_RL = (theta + phi_RL) / (2.0f*(float)M_PI);

        float w_FR = stance_weight_soft(u_FR, DUTY_STANCE, 0.10f);
        float w_FL = stance_weight_soft(u_FL, DUTY_STANCE, 0.10f);
        float w_RR = stance_weight_soft(u_RR, DUTY_STANCE, 0.10f);
        float w_RL = stance_weight_soft(u_RL, DUTY_STANCE, 0.10f);

        float d_fore = (w_FL - w_FR);
        float d_hind = (w_RL - w_RR);

        float boost_fore = 1.0f;
        float boost_hind = 1.0f;
        if ((turn_cmd < 0 && d_fore >  0.0f) || (turn_cmd > 0 && d_fore <= 0.0f)) boost_fore += k_response;
        if ((turn_cmd < 0 && d_hind >  0.0f) || (turn_cmd > 0 && d_hind <= 0.0f)) boost_hind += k_response;

        // turn_cmd: +1 = izquierda, 0 = recto, -1 = derecha
        const float *WF = W_fore_F;
        const float *WH = W_hind_F;
        if (turn_cmd > 0) {       // giro/marcha a la IZQUIERDA
            WF = W_fore_L; WH = W_hind_L; spine_skew = 1.0f; turn_bias = 0.0; SPINE_SKEW_GAIN = 1.0f;
        } else if (turn_cmd < 0) { // giro/marcha a la DERECHA
            WF = W_fore_R;
            WH = W_hind_R;
            spine_skew = -1.0f;
        }

        for (int k = 0; k < 6; ++k) {
            // Bend "crudo" según acoplamiento columna↔patas
            float bend_deg_raw =
                spine_gain_fore_deg * d_fore * WF[k] * boost_fore +
                spine_gain_hind_deg * d_hind * WH[k] * boost_hind;
            // clamp para estabilidad (evitar 0 o negativos).
            float sgn   = (bend_deg_raw >= 0.0f) ? 1.0f : -1.0f;
            float scale = 1.0f + sgn * spine_skew * SPINE_SKEW_GAIN;
            if (scale < 0.2f) scale = 0.2f;
            if (scale > 1.8f) scale = 1.8f;
            float bend_deg = bend_deg_raw * scale;

        float ang = spine_bias_deg + bend_deg;
            lut_spine[k][i] = (int16_t)clamp_deg((int)lrintf(ang));
        }
    }

    // --- NUEVO: no reiniciar la fase ni forzar los “cur_*” a la muestra 0 ---
    // 1) Si es la primera vez que se construyen las LUT, sí inicializamos
    //    los valores “cur_*” en la fase preservada (normalmente 0 al arranque).
    // 2) En llamadas posteriores, mantenemos cur_* tal cual; el timer_cb
    //    hará el “approach” hacia los nuevos objetivos sin saltos.
    if (s_first_build) {
        for (int j = 0; j < 4; ++j) { cur_id0[j]  = lut_legs_front[j][preserve_idx]; }
        for (int j = 0; j < 4; ++j) { cur_id4[j]  = lut_legs_rear [j][preserve_idx]; }
        for (int k = 0; k < 6; ++k) { cur_spine[k]= lut_spine     [k][preserve_idx]; }
        s_first_build = false;
    }
    // Mantener fase actual:
    lut_idx = preserve_idx;
}

// ======= NVS: offsets =======
static void calib_defaults(void) {
    for (int i=0;i<SERVO_COUNT;i++) g_offset_deg[i]=0;
}

static esp_err_t calib_nvs_load(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }
    nvs_handle_t h;
    err = nvs_open("sally", NVS_READONLY, &h);
    if (err != ESP_OK) return err;
    size_t size = SERVO_COUNT;
    err = nvs_get_blob(h, "offsets", g_offset_deg, &size);
    nvs_close(h);
    return err;
}
static esp_err_t calib_nvs_save(void) {
    nvs_handle_t h;
    ESP_ERROR_CHECK(nvs_open("sally", NVS_READWRITE, &h));
    ESP_ERROR_CHECK(nvs_set_blob(h, "offsets", g_offset_deg, SERVO_COUNT));
    esp_err_t err = nvs_commit(h);
    nvs_close(h);
    ESP_LOGI(TAG, "Offsets (SAVE NVS): %d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
             g_offset_deg[0], g_offset_deg[1], g_offset_deg[2], g_offset_deg[3],
             g_offset_deg[4], g_offset_deg[5], g_offset_deg[6], g_offset_deg[7],
             g_offset_deg[8], g_offset_deg[9], g_offset_deg[10], g_offset_deg[11],
             g_offset_deg[12], g_offset_deg[13]);
    return err;
}

// ======= Wi-Fi SoftAP =======
static void wifi_init_softap(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = {
        .ap = {
            .ssid = AP_SSID,
            .ssid_len = 0,
            .channel = AP_CHANNEL,
            .password = AP_PASS,
            .max_connection = AP_MAX_CONN,
            .authmode = WIFI_AUTH_WPA_WPA2_PSK,
            // Desactiva 802.11w (PMF) en el AP para evitar SA Query
            .pmf_cfg = { .capable = false, .required = false },
        },
    };
    if (strlen(AP_PASS) == 0) wifi_config.ap.authmode = WIFI_AUTH_OPEN;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));
    // Fuerza 20 MHz en 2.4 GHz (evita "40U" y mejora compatibilidad)
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_AP, WIFI_BW_HT20));

    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "SoftAP iniciado: SSID=%s PASS=%s channel=%d", AP_SSID, AP_PASS, AP_CHANNEL);
}

// ======= HTTP utils =======
static bool qs_get_str(httpd_req_t* req, const char* key, char* out, size_t outlen) {
    size_t qlen = httpd_req_get_url_query_len(req) + 1;
    if (qlen <= 1) return false;
    char *buf = (char*)malloc(qlen);
    if (!buf) return false;
    bool ok = false;
    if (httpd_req_get_url_query_str(req, buf, qlen) == ESP_OK) {
        if (httpd_query_key_value(buf, key, out, outlen) == ESP_OK) ok = true;
    }
    free(buf);
    return ok;
}
static int qs_get_int(httpd_req_t* req, const char* key, int defv) {
    char tmp[16];
    if (!qs_get_str(req, key, tmp, sizeof(tmp))) return defv;
    return atoi(tmp);
}

// ======= Handlers existentes (JSON angles/angle/set/cfg) =======
static esp_err_t angles_get_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "application/json");
    char out[512];
    int n = snprintf(out, sizeof(out),
        "{\"period_ms\":%d,"
        "\"ids\":["
          "{\"id\":0,\"count\":4,\"angles\":[%d,%d,%d,%d]},"
          "{\"id\":1,\"count\":1,\"angle\":%d},"
          "{\"id\":2,\"count\":1,\"angle\":%d},"
          "{\"id\":3,\"count\":1,\"angle\":%d},"
          "{\"id\":4,\"count\":4,\"angles\":[%d,%d,%d,%d]},"
          "{\"id\":5,\"count\":1,\"angle\":%d},"
          "{\"id\":6,\"count\":1,\"angle\":%d},"
          "{\"id\":7,\"count\":1,\"angle\":%d}"
        "]}",
        period_ms,
        bank[0].a[0], bank[0].a[1], bank[0].a[2], bank[0].a[3],
        bank[1].a[0], bank[2].a[0], bank[3].a[0],
        bank[4].a[0], bank[4].a[1], bank[4].a[2], bank[4].a[3],
        bank[5].a[0], bank[6].a[0], bank[7].a[0]
    );
    if (n < 0 || n >= (int)sizeof(out)) return httpd_resp_send_500(req);
    return httpd_resp_send(req, out, n);
}

static esp_err_t angle_get_handler(httpd_req_t *req) {
    char q[64]; int qlen = httpd_req_get_url_query_len(req) + 1;
    int id = -1;
    if (qlen > 1 && qlen < (int)sizeof(q)) {
        httpd_req_get_url_query_str(req, q, qlen);
        char val[8];
        if (httpd_query_key_value(q, "id", val, sizeof(val)) == ESP_OK) id = atoi(val);
    }
    if (id < 0 || id >= 8) {
        httpd_resp_set_status(req, "400 Bad Request");
        return httpd_resp_sendstr(req, "{\"error\":\"id must be 0..7\"}");
    }

    httpd_resp_set_type(req, "application/json");
    char buf[256];

    if (bank[id].count == 1) {
        int n = snprintf(buf, sizeof(buf),
            "{\"id\":%d,\"count\":1,\"angle\":%d,\"period_ms\":%d}",
            id, bank[id].a[0], period_ms);
        if (n < 0 || n >= (int)sizeof(buf)) return httpd_resp_send_500(req);
        return httpd_resp_send(req, buf, n);
    } else {
        int n = snprintf(buf, sizeof(buf),
            "{\"id\":%d,\"count\":4,\"angles\":[%d,%d,%d,%d],\"period_ms\":%d}",
            id, bank[id].a[0], bank[id].a[1], bank[id].a[2], bank[id].a[3], period_ms);
        if (n < 0 || n >= (int)sizeof(buf)) return httpd_resp_send_500(req);
        return httpd_resp_send(req, buf, n);
    }
}

static esp_err_t set_get_handler(httpd_req_t *req) {
    char q[128]; int qlen = httpd_req_get_url_query_len(req) + 1;
    int id = -1, ok = 0;
    if (qlen > 1 && qlen < (int)sizeof(q)) {
        httpd_req_get_url_query_str(req, q, qlen);
        char v[16];

        if (httpd_query_key_value(q, "id", v, sizeof(v)) == ESP_OK) id = atoi(v);
        if (id >= 0 && id < 8) {
            if (bank[id].count == 1) {
                if (httpd_query_key_value(q, "angle", v, sizeof(v)) == ESP_OK) {
                    int a = atoi(v); if (a < 0) a = 0; if (a > 180) a = 180;
                    bank[id].a[0] = a; ok = 1;
                }
            } else {
                int t[4] = { bank[id].a[0], bank[id].a[1], bank[id].a[2], bank[id].a[3] };
                const char* keys[4] = {"a0","a1","a2","a3"};
                for (int i=0;i<4;i++) {
                    if (httpd_query_key_value(q, keys[i], v, sizeof(v)) == ESP_OK) {
                        int a = atoi(v); if (a < 0) a = 0; if (a > 180) a = 180;
                        t[i] = a; ok = 1;
                    }
                }
                if (ok) { bank[id].a[0]=t[0]; bank[id].a[1]=t[1]; bank[id].a[2]=t[2]; bank[id].a[3]=t[3]; }
            }
        }
        if (httpd_query_key_value(q, "period_ms", v, sizeof(v)) == ESP_OK) {
            int p = atoi(v); if (p >= 20 && p <= 5000) { period_ms = p; ok = 1; }
        }
    }
    httpd_resp_set_type(req, "application/json");
    if (!ok) return httpd_resp_sendstr(req, "{\"ok\":false}");
    return httpd_resp_sendstr(req, "{\"ok\":true}");
}

static esp_err_t cfg_get_handler(httpd_req_t *req) {
    char q[128];
    int qlen = httpd_req_get_url_query_len(req) + 1;
    if (qlen > 1 && qlen < (int)sizeof(q)) {
        httpd_req_get_url_query_str(req, q, qlen);
        char val[16];
        if (httpd_query_key_value(q, "period_ms", val, sizeof(val)) == ESP_OK) {
            int p = atoi(val);
            if (p >= 20 && p <= 5000) { period_ms = p; }
        }
        // ======= NUEVO: aceptar skew/spine_skew en -100..+100 =======
        if (httpd_query_key_value(q, "spine_skew", val, sizeof(val)) == ESP_OK ||
            httpd_query_key_value(q, "skew",       val, sizeof(val)) == ESP_OK) {
            int pct = atoi(val); if (pct < -100) pct = -100; if (pct > 100) pct = 100;
            spine_skew = ((float)pct) / 100.0f; // [-1..+1]
        }
        // ======= NUEVO: sesgo de giro (turn_bias_pct) en -100..+100 =======
        if (httpd_query_key_value(q, "turn_bias_pct", val, sizeof(val)) == ESP_OK ||
            httpd_query_key_value(q, "turnbias",      val, sizeof(val)) == ESP_OK) {
            int pct = atoi(val); if (pct < -100) pct = -100; if (pct > 100) pct = 100;
            turn_bias = ((float)pct) / 100.0f;  // -1..+1  (p.ej. +30 → 0.30 hacia IZQ)
        }
    }
    httpd_resp_set_type(req, "application/json");
    char buf[144];
    int n = snprintf(buf, sizeof(buf),
                     "{\"period_ms\":%d,\"spine_skew\":%.3f,\"turn_bias_pct\":%.1f}",
                     period_ms, (double)spine_skew, (double)(turn_bias*100.0f));
    return httpd_resp_send(req, buf, n);
}

// ======= NUEVO: /drive (ya en base) =======
static esp_err_t drive_get_handler(httpd_req_t *req)
{
    char dir[12] = {0};
    if (!qs_get_str(req, "dir", dir, sizeof(dir))) {
        const char* msg = "{\"ok\":false,\"err\":\"missing dir\"}\n";
        httpd_resp_set_type(req, "application/json");
        httpd_resp_send(req, msg, HTTPD_RESP_USE_STRLEN);
        return ESP_OK;
    }

    int pct  = qs_get_int(req, "pct",  -1);
    int resp = qs_get_int(req, "resp", -1);
    if (pct  >= 0) turning_percentage = fminf(1.0f, fmaxf(0.0f, pct  / 100.0f));
    if (resp >= 0) k_response         = fminf(1.5f, fmaxf(0.0f, resp / 100.0f));

    freeze_motion = true;

    if      (!strcasecmp(dir, "fwd"))  { drive_mode = DRIVE_FORWARD; turn_cmd = 0;  generarTrayectoria(); g_mode = MODE_DRIVE; }
    else if (!strcasecmp(dir, "left")) { drive_mode = DRIVE_LEFT;    turn_cmd = +1; generarTrayectoria(); g_mode = MODE_DRIVE; }
    else if (!strcasecmp(dir, "right")){ drive_mode = DRIVE_RIGHT;   turn_cmd = -1; generarTrayectoria(); g_mode = MODE_DRIVE; }
    else if (!strcasecmp(dir, "stop")) { drive_mode = DRIVE_STOP; /* g_mode mantiene */ }
    else {
        freeze_motion = false;
        const char* msg = "{\"ok\":false,\"err\":\"dir must be fwd|left|right|stop\"}\n";
        httpd_resp_set_type(req, "application/json");
        httpd_resp_send(req, msg, HTTPD_RESP_USE_STRLEN);
        return ESP_OK;
    }

    freeze_motion = false;

    char out[160];
    snprintf(out, sizeof(out),
             "{\"ok\":true,\"dir\":\"%s\",\"turn_cmd\":%d,\"pct\":%.2f,\"resp\":%.2f}\n",
             dir, (int)turn_cmd, (double)turning_percentage, (double)k_response);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, out, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// ======= NUEVO: /mode (calib|run|idle) =======
static esp_err_t mode_get_handler(httpd_req_t *req)
{
    char state[16] = {0};
    if (!qs_get_str(req, "state", state, sizeof(state))) {
        httpd_resp_set_status(req, "400 Bad Request");
        return httpd_resp_sendstr(req, "{\"ok\":false,\"err\":\"missing state\"}");
    }
    if      (!strcasecmp(state, "calib"))   g_mode = MODE_CALIB;
    else if (!strcasecmp(state, "preview")) g_mode = MODE_PREVIEW;
    else if (!strcasecmp(state, "run"))     g_mode = MODE_DRIVE;
    else if (!strcasecmp(state, "idle"))    g_mode = MODE_IDLE;
    else {
        httpd_resp_set_status(req, "400 Bad Request");
        return httpd_resp_sendstr(req, "{\"ok\":false,\"err\":\"bad state\"}");
    }
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_sendstr(req, "{\"ok\":true}");
}

// ======= NUEVO: /calib GET/POST (leer/guardar offsets) =======
static esp_err_t calib_handler(httpd_req_t *req)
{
    if (req->method == HTTP_POST) {
        char body[256];
        int r = httpd_req_recv(req, body, sizeof(body)-1);
        if (r <= 0) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "no body");
        body[r] = 0;
        char *p = strstr(body, "[");
        char *e = strstr(body, "]");
        if (!p || !e || e<=p) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "bad json");
        *e = 0; ++p;
        int idx=0;
        char *tok = strtok(p, ",");
        while (tok && idx < SERVO_COUNT) {
            int v = atoi(tok);
            if (v < -45) v = -45;
            if (v >  45) v =  45;
            g_offset_deg[idx++] = (int8_t)v;
            tok = strtok(NULL, ",");
        }
        if (idx != SERVO_COUNT) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "count");
        calib_nvs_save();
        httpd_resp_set_type(req, "application/json");
        return httpd_resp_sendstr(req, "{\"ok\":true}");
    } else {
        char out[256];
        int n=0;
        n += snprintf(out+n, sizeof(out)-n, "{\"offsets\":[");
        for (int i=0;i<SERVO_COUNT;i++) {
            n += snprintf(out+n, sizeof(out)-n, "%d%s", (int)g_offset_deg[i], (i==SERVO_COUNT-1)?"]}":",");
        }
        httpd_resp_set_type(req, "application/json");
        return httpd_resp_send(req, out, HTTPD_RESP_USE_STRLEN);
    }
}

// ======= Registro HTTP =======
static httpd_handle_t start_httpd(void) {
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = 80;
    cfg.uri_match_fn = httpd_uri_match_wildcard;
    httpd_handle_t hd = NULL;
    if (httpd_start(&hd, &cfg) == ESP_OK) {
        static const httpd_uri_t uri_angles = { .uri="/angles", .method=HTTP_GET, .handler=angles_get_handler };
        static const httpd_uri_t uri_angle  = { .uri="/angle",  .method=HTTP_GET, .handler=angle_get_handler  };
        static const httpd_uri_t uri_cfg    = { .uri="/cfg",    .method=HTTP_GET, .handler=cfg_get_handler    };
        static const httpd_uri_t uri_set    = { .uri="/set",    .method=HTTP_GET, .handler=set_get_handler    };
        static const httpd_uri_t uri_drive  = { .uri="/drive",  .method=HTTP_GET, .handler=drive_get_handler  };
        static const httpd_uri_t uri_mode   = { .uri="/mode",   .method=HTTP_GET, .handler=mode_get_handler   };
        static const httpd_uri_t uri_calibG = { .uri="/calib",  .method=HTTP_GET, .handler=calib_handler      };
        static const httpd_uri_t uri_calibP = { .uri="/calib",  .method=HTTP_POST,.handler=calib_handler      };
        httpd_register_uri_handler(hd, &uri_angles);
        httpd_register_uri_handler(hd, &uri_angle);
        httpd_register_uri_handler(hd, &uri_cfg);
        httpd_register_uri_handler(hd, &uri_set);
        httpd_register_uri_handler(hd, &uri_drive);
        httpd_register_uri_handler(hd, &uri_mode);
        httpd_register_uri_handler(hd, &uri_calibG);
        httpd_register_uri_handler(hd, &uri_calibP);
        ESP_LOGI(TAG, "HTTP listo: /angle, /angles, /cfg, /set, /drive, /mode, /calib");
    }
    return hd;
}

// ======= Timer: genera y PUBLICA (banco) =======
static void timer_cb(void* arg) {
    const float dt_s = ((float)period_ms) / 1000.0f;
    if (freeze_motion) return;

    // Avance LUT solo si DRIVE_* y modo DRV
    if (g_mode == MODE_DRIVE && drive_mode != DRIVE_STOP) {
        float step_f = ((float)LUT_N) * ((float)period_ms / (float)gait_period_ms);
        static float acc = 0.0f;
        acc += step_f;
        int step = (int)acc;
        if (step > 0) { acc -= step; lut_idx = (lut_idx + step) % LUT_N; }
    }

    // Targets por modo
    int16_t t_id0[4], t_id4[4], t_sp[6];

    if (g_mode == MODE_CALIB) {
        for (int j=0;j<4;++j){ t_id0[j] = 90; t_id4[j] = 90; }
        for (int k=0;k<6;++k){ t_sp[k]  = 90; }
    } else if (g_mode == MODE_PREVIEW) {
         // Vista "estática" para validar offsets: 90° + offset, SIN LUT ni avance
         for (int j=0;j<4;++j){ t_id0[j] = clamp_deg(90 + g_offset_deg[j]); }
         for (int j=0;j<4;++j){ t_id4[j] = clamp_deg(90 + g_offset_deg[j + 7]); }
         for (int k=0;k<6;++k){
             if (k < 3)  t_sp[k] = clamp_deg(90 + g_offset_deg[k + 4]);
             else        t_sp[k] = clamp_deg(90 + g_offset_deg[k + 8]);
         }
    } else if (g_mode == MODE_DRIVE) {
        for (int j=0;j<4;++j){ t_id0[j]=lut_legs_front[j][lut_idx]; t_id4[j]=lut_legs_rear[j][lut_idx]; }
        for (int k=0;k<6;++k){ t_sp[k]=lut_spine[k][lut_idx]; }
        // Aplica OFFSETS (RUN solamente)
        t_id0[0] = clamp_deg(t_id0[0] + g_offset_deg[0]);
        t_id0[1] = clamp_deg(t_id0[1] + g_offset_deg[1]);
        t_id0[2] = clamp_deg(t_id0[2] + g_offset_deg[2]);
        t_id0[3] = clamp_deg(t_id0[3] + g_offset_deg[3]);

        t_sp[0]  = clamp_deg(t_sp[0]  + g_offset_deg[4]);
        t_sp[1]  = clamp_deg(t_sp[1]  + g_offset_deg[5]);
        t_sp[2]  = clamp_deg(t_sp[2]  + g_offset_deg[6]);

        t_id4[0] = clamp_deg(t_id4[0] + g_offset_deg[7]);
        t_id4[1] = clamp_deg(t_id4[1] + g_offset_deg[8]);
        t_id4[2] = clamp_deg(t_id4[2] + g_offset_deg[9]);
        t_id4[3] = clamp_deg(t_id4[3] + g_offset_deg[10]);

        t_sp[3]  = clamp_deg(t_sp[3]  + g_offset_deg[11]);
        t_sp[4]  = clamp_deg(t_sp[4]  + g_offset_deg[12]);
        t_sp[5]  = clamp_deg(t_sp[5]  + g_offset_deg[13]);
    } else { // MODE_IDLE
        for (int j=0;j<4;++j){ t_id0[j] = 90 + g_offset_deg[j]; t_id4[j] = 90 + g_offset_deg[j + 7]; }
        for (int k=0;k<6;++k){
            if (k < 3){
                t_sp[k]  = 90 + g_offset_deg[k + 4];
            }else{
                t_sp[k]  = 90 + g_offset_deg[k + 8];
            }  
        }
    }

    // Suavizado (respeta max_dps)
    for (int j=0;j<4;++j){ cur_id0[j]  = approach_deg(cur_id0[j],  t_id0[j], dt_s, max_dps); }
    for (int j=0;j<4;++j){ cur_id4[j]  = approach_deg(cur_id4[j],  t_id4[j], dt_s, max_dps); }
    for (int k=0;k<6;++k){ cur_spine[k]= approach_deg(cur_spine[k], t_sp[k],  dt_s, max_dps); }

    // Publica al banco (lo que leen /angles y /angle)
    bank[0].a[0] = cur_id0[0]; bank[0].a[1] = cur_id0[1];
    bank[0].a[2] = cur_id0[2]; bank[0].a[3] = cur_id0[3];

    bank[1].a[0] = cur_spine[0];
    bank[2].a[0] = cur_spine[1];
    bank[3].a[0] = cur_spine[2];

    bank[4].a[0] = cur_id4[0]; bank[4].a[1] = cur_id4[1];
    bank[4].a[2] = cur_id4[2]; bank[4].a[3] = cur_id4[3];

    bank[5].a[0] = cur_spine[3];
    bank[6].a[0] = cur_spine[4];
    bank[7].a[0] = cur_spine[5];
}

// ======= app_main =======
void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    wifi_init_softap();

    // Offsets desde NVS o por defecto
    if (calib_nvs_load() != ESP_OK) { calib_defaults(); calib_nvs_save(); }

    // HTTP
    (void)start_httpd();

    // Trayectoria y timer
    generarTrayectoria();

    const esp_timer_create_args_t targs = {
        .callback = &timer_cb,
        .arg = NULL,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "gait"
    };
    ESP_ERROR_CHECK(esp_timer_create(&targs, &g_timer));
    ESP_ERROR_CHECK(esp_timer_start_periodic(g_timer, (uint64_t)period_ms * 1000ULL));

    // Idle loop
    while (true) { vTaskDelay(pdMS_TO_TICKS(1000)); }
}
