#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include "esp_http_client.h"
#include "cJSON.h"

#include "driver/ledc.h"
#include "led_strip.h"

/* ========================= CONFIGURACIÓN ========================= */
#define AP_SSID             "SallyAP"
#define AP_PASS             "Sally1234"
#define DEVICE_ID           0                 // 0..7 (cambia en cada equipo)
#define DEFAULT_PERIOD_MS   2               // período por defecto si el server no lo envía
#define AP_IP               "192.168.4.1"     // IP SoftAP del servidor

#define USE_STATUS_LED      1                 // 1: usa el WS2812 del C3 en GPIO 8 como indicador
#define LED_STRIP_GPIO      8
#define LED_COUNT           1

/* Cómo mandar el ángulo al/los servo(s)
   0 = todos los servos
   1 = índice = DEVICE_ID % NUM_SERVOS   (POR DEFECTO)
   2 = índice fijo SERVO_FIXED_IDX
*/
#define SERVO_TARGET_MODE   1
#define SERVO_FIXED_IDX     0

/* ========================= TAGS (logs) ========================= */
static const char *TAG_WIFI  = "client_sta";
#define TAG_SERVO            "SERVOS"

/* ========================= NEURONS FILTERS (logs) ========================= */
#define NEU_N 4 
static const float tau = 3.0f;
static float z[NEU_N][2] = {{90.f,90.f}, {90.f,90.f}, {90.f,90.f}, {90.f,90.f}};

/* ========================= WIFI (STA) ========================= */
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_GOT_IP_BIT    BIT1
static EventGroupHandle_t s_wifi_event_group;

static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                               int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT | WIFI_GOT_IP_BIT);
        vTaskDelay(pdMS_TO_TICKS(500));
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_CONNECTED) {
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(s_wifi_event_group, WIFI_GOT_IP_BIT);
    }
}

static void wifi_init_sta(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = { 0 };
    strncpy((char*)wifi_config.sta.ssid, AP_SSID, sizeof(wifi_config.sta.ssid));
    strncpy((char*)wifi_config.sta.password, AP_PASS, sizeof(wifi_config.sta.password));
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler, NULL, NULL));
    esp_wifi_set_ps(WIFI_PS_NONE);
    ESP_LOGI(TAG_WIFI, "Conectando a %s ...", AP_SSID);
}

/* ========================= LED RGB (opcional) ========================= */
#if USE_STATUS_LED
static led_strip_handle_t led_strip;

static void init_led_strip(void) {
    led_strip_config_t strip_cfg = {
        .strip_gpio_num = LED_STRIP_GPIO,
        .max_leds = LED_COUNT,
    };
    led_strip_rmt_config_t rmt_cfg = {
        .resolution_hz = 10 * 1000 * 1000,
        .flags.with_dma = false,
    };
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_cfg, &rmt_cfg, &led_strip));
    ESP_ERROR_CHECK(led_strip_clear(led_strip));
}

static void angle_to_rgb(int ang, uint8_t *R, uint8_t *G, uint8_t *B) {
    if (ang < 0) ang = 0;
    if (ang > 180) ang = 180;
    float t = ang / 180.0f; // 0..1
    float r = (t <= 0.5f) ? 0.0f : (t - 0.5f) * 2.0f;
    float g = (t <= 0.5f) ? (t * 2.0f) : (1.0f - r);
    float b = (t <= 0.5f) ? (1.0f - t*2.0f) : 0.0f;
    int brightness = 150;
    *R = (uint8_t)(r * brightness);
    *G = (uint8_t)(g * brightness);
    *B = (uint8_t)(b * brightness);
}

static void set_led_angle(int ang) {
    uint8_t R,G,B;
    angle_to_rgb(ang, &R,&G,&B);
    led_strip_set_pixel(led_strip, 0, R,G,B);
    led_strip_refresh(led_strip);
}
#endif

/* ========================= SERVOS (LEDC) ========================= */
/* GPIOs para tus servos (ajusta a gusto) */
static const int servo_pins[] = { 0, 1, 5, 6 };
#define NUM_SERVOS (sizeof(servo_pins)/sizeof(servo_pins[0]))

/* Un canal por servo */
static const ledc_channel_t servo_channels[NUM_SERVOS] = {
    LEDC_CHANNEL_0, LEDC_CHANNEL_1, LEDC_CHANNEL_2, LEDC_CHANNEL_3
};

/* PWM 50 Hz @ 14 bits (ESP32-C3) */
#define SERVO_MODE          LEDC_LOW_SPEED_MODE
#define SERVO_TIMER         LEDC_TIMER_0
#define SERVO_FREQ_HZ       (50)
#define SERVO_RES_BITS      (14)
#define SERVO_RESOLUTION    (ledc_timer_bit_t)LEDC_TIMER_14_BIT

/* Rango típico de pulso en microsegundos (ajústalo a tu servo) */
#define SERVO_MIN_US        (500)
#define SERVO_MAX_US        (2500)
#define SERVO_MIN_DEG       (0)
#define SERVO_MAX_DEG       (180)

static inline uint32_t duty_max(void) {
    return (1U << SERVO_RES_BITS) - 1U; // 16383 para 14 bits
}
static inline uint32_t period_us(void) {
    return 1000000UL / SERVO_FREQ_HZ;    // 20000 µs
}
static inline uint32_t clamp_u32(uint32_t v, uint32_t lo, uint32_t hi) {
    return (v < lo) ? lo : (v > hi ? hi : v);
}
static uint32_t us_to_duty(uint32_t pulse_us) {
    uint64_t num = (uint64_t)pulse_us * duty_max();
    return (uint32_t)(num / period_us());
}
static uint32_t deg_to_us(uint32_t deg) {
    deg = clamp_u32(deg, SERVO_MIN_DEG, SERVO_MAX_DEG);
    uint32_t span_us = SERVO_MAX_US - SERVO_MIN_US;
    uint64_t num = (uint64_t)(deg - SERVO_MIN_DEG) * span_us;
    return SERVO_MIN_US + (uint32_t)(num / (SERVO_MAX_DEG - SERVO_MIN_DEG));
}

static void servos_init(void) {
    ledc_timer_config_t tcfg = {
        .speed_mode       = SERVO_MODE,
        .duty_resolution  = SERVO_RESOLUTION,
        .timer_num        = SERVO_TIMER,
        .freq_hz          = SERVO_FREQ_HZ,
        .clk_cfg          = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&tcfg));

    for (size_t i = 0; i < NUM_SERVOS; ++i) {
        ledc_channel_config_t ccfg = {
            .gpio_num   = servo_pins[i],
            .speed_mode = SERVO_MODE,
            .channel    = servo_channels[i],
            .intr_type  = LEDC_INTR_DISABLE,
            .timer_sel  = SERVO_TIMER,
            .duty       = 0,
            .hpoint     = 0
        };
        ESP_ERROR_CHECK(ledc_channel_config(&ccfg));

        uint32_t duty = us_to_duty(deg_to_us(90)); // centrar
        ESP_ERROR_CHECK(ledc_set_duty(SERVO_MODE, servo_channels[i], duty));
        ESP_ERROR_CHECK(ledc_update_duty(SERVO_MODE, servo_channels[i]));
        ESP_LOGI(TAG_SERVO, "Servo %d -> GPIO %d, canal %d OK", (int)i, servo_pins[i], servo_channels[i]);
    }
}

static void servo_write_us_idx(size_t idx, uint32_t pulse_us) {
    if (idx >= NUM_SERVOS) return;
    pulse_us = clamp_u32(pulse_us, SERVO_MIN_US, SERVO_MAX_US);
    uint32_t duty = us_to_duty(pulse_us);
    ledc_set_duty(SERVO_MODE, servo_channels[idx], duty);
    ledc_update_duty(SERVO_MODE, servo_channels[idx]);
}
static void servo_write_deg_idx(size_t idx, uint32_t deg) {
    servo_write_us_idx(idx, deg_to_us(deg));
    ESP_LOGI(TAG_SERVO, "Servo %d (GPIO %d) → %u°", (int)idx, servo_pins[idx], (unsigned)deg);
}

/* ========================= FETCH (HTTP → servo) ========================= */
static void fetch_task(void *arg) {
    char url[64];
    snprintf(url, sizeof(url), "http://%s/angle?id=%d", AP_IP, DEVICE_ID);
    ESP_LOGI(TAG_WIFI, "URL=%s", url);

    esp_http_client_config_t cfg = {
        .url = url,
        .timeout_ms = 2000,
        .buffer_size = 512,
        .keep_alive_enable = true,
    };
    esp_http_client_handle_t client = esp_http_client_init(&cfg);

    int curr_period = DEFAULT_PERIOD_MS;

    while (1) {
        esp_err_t err = esp_http_client_open(client, 0);
        if (err != ESP_OK) {
            ESP_LOGW(TAG_WIFI, "open fallo: %s", esp_err_to_name(err));
            vTaskDelay(pdMS_TO_TICKS(300));
            continue;
        }

        int64_t cl = esp_http_client_fetch_headers(client);
        ESP_LOGI(TAG_WIFI, "status=%d, content-length=%lld",
                 esp_http_client_get_status_code(client), cl);

        char buf[512];
        int total = 0;
        for (;;) {
            int r = esp_http_client_read(client, buf + total, sizeof(buf) - 1 - total);
            if (r > 0) {
                total += r;
                if (total >= (int)sizeof(buf) - 1) break;
            } else {
                break;
            }
        }
        buf[total] = 0;
        esp_http_client_close(client);

        if (total <= 0) {
            vTaskDelay(pdMS_TO_TICKS(300));
            continue;
        }

        ESP_LOGI(TAG_WIFI, "HTTP body len=%d", total);
        ESP_LOGI(TAG_WIFI, "HTTP body: %.*s", total, buf);

                cJSON *root = cJSON_Parse(buf);
        if (!root) {
            ESP_LOGW(TAG_WIFI, "JSON inválido");
            vTaskDelay(pdMS_TO_TICKS(200));
            continue;
        }

        // Lee periodo recomendado (si viene)
        cJSON *pms = cJSON_GetObjectItem(root, "period_ms");
        if (cJSON_IsNumber(pms) && pms->valueint >= 20 && pms->valueint <= 5000) {
            // curr_period = pms->valueint;
        }

        // --- PATH 1: paquete de patas (count=4) -> 4 servos ---
        bool drove_servos = false;
        cJSON *count = cJSON_GetObjectItem(root, "count");
        if (cJSON_IsNumber(count) && count->valueint == 4) {
            cJSON *angles = cJSON_GetObjectItem(root, "angles");
            if (cJSON_IsArray(angles) && cJSON_GetArraySize(angles) >= 4) {
                int a0 = cJSON_GetArrayItem(angles, 0)->valuedouble;
                int a1 = cJSON_GetArrayItem(angles, 1)->valuedouble;
                int a2 = cJSON_GetArrayItem(angles, 2)->valuedouble;
                int a3 = cJSON_GetArrayItem(angles, 3)->valuedouble;

                // Clamp 0..180 por seguridad
                if (a0 < 0) { a0 = 0; }
                if (a0 > 180) { a0 = 180; }

                if (a1 < 0) { a1 = 0; }
                if (a1 > 180) { a1 = 180; }

                if (a2 < 0) { a2 = 0; }
                if (a2 > 180) { a2 = 180; }

                if (a3 < 0) { a3 = 0; }
                if (a3 > 180) { a3 = 180; }


                // Mapea 1:1 a tus 4 servos (GPIO 0,1,5,6)
                z[0][1]=z[0][0]+(curr_period/tau)*(-z[0][0]+(a0));
                z[1][1]=z[1][0]+(curr_period/tau)*(-z[1][0]+(a1));
                z[2][1]=z[2][0]+(curr_period/tau)*(-z[2][0]+(a2));
                z[3][1]=z[3][0]+(curr_period/tau)*(-z[3][0]+(a3));

                // servo_write_deg_idx(0, (uint32_t)(z[0][1]));
                // servo_write_deg_idx(1, (uint32_t)(z[1][1]));
                // servo_write_deg_idx(2, (uint32_t)(z[2][1]));
                // servo_write_deg_idx(3, (uint32_t)(z[3][1]));

                servo_write_deg_idx(0, (uint32_t)(a0));
                servo_write_deg_idx(1, (uint32_t)(a1));
                servo_write_deg_idx(2, (uint32_t)(a2));
                servo_write_deg_idx(3, (uint32_t)(a3));

                ESP_LOGI(TAG_SERVO, "Patas[0] = [%d, %d, %d, %d] → servos 0..3", a0,a1,a2,a3);

                // (opcional) LED de estado: promedio para color
                #if USE_STATUS_LED
                set_led_angle((a0 + a1 + a2 + a3) / 4);
                #endif

                drove_servos = true;
            }
        }

        // --- PATH 2: módulo de 1 servo (count=1 / angle) ---
        if (!drove_servos) {
            int angle_val = -1;
            cJSON *angle = cJSON_GetObjectItem(root, "angle");
            if (cJSON_IsNumber(angle)) {
                angle_val = angle->valueint;
            } else if (cJSON_IsString(angle) && angle->valuestring) {
                angle_val = atoi(angle->valuestring);
            }
            if (angle_val >= 0) {
                // Por defecto, usa el índice basado en DEVICE_ID
                size_t idx = 0;
                servo_write_deg_idx(idx, (uint32_t)angle_val);
                ESP_LOGI(TAG_SERVO, "OSC[%d] = %d° → servo %d", DEVICE_ID, angle_val, (int)idx);

                #if USE_STATUS_LED
                set_led_angle(angle_val);
                #endif
            } else {
                ESP_LOGW(TAG_WIFI, "No pude extraer 'angle' ni 'angles[4]'");
            }
        }

        cJSON_Delete(root);

        vTaskDelay(pdMS_TO_TICKS(curr_period));
    }
}

/* ========================= app_main ========================= */
void app_main(void) {
    /* Inicializa NVS (Wi-Fi lo requiere) */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }

    s_wifi_event_group = xEventGroupCreate();
    wifi_init_sta();

    /* LED indicador (opcional) */
    #if USE_STATUS_LED
    init_led_strip();
    #endif

    /* Servos */
    servos_init();

    /* Espera vínculo + IP y arranca fetch */
    xEventGroupWaitBits(s_wifi_event_group,
                        WIFI_CONNECTED_BIT | WIFI_GOT_IP_BIT,
                        pdFALSE, pdTRUE, portMAX_DELAY);
    ESP_LOGI(TAG_WIFI, "Todo Ready");
    xTaskCreate(fetch_task, "fetch_task", 4096*3, NULL, 5, NULL);
}