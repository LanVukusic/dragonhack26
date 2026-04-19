#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include <FastLED.h>

#define WIFI_SSID "nLa"
#define WIFI_PASS "tugicamalo"
#define WS_URL "ws://10.230.183.204:8000/"

#define LED_PIN 5
#define NUM_LEDS 27
#define MY_ESP_ID 1

using namespace websockets;

CRGB leds[NUM_LEDS];
WebsocketsClient client;

int currentEffect = 8;
uint8_t currentR = 250, currentG = 0, currentB = 200;
uint8_t chaseIndex = 0;
uint8_t rainbowHue = 0;
uint8_t cometHead = 0;
uint8_t waveOffset = 0;
uint8_t tripleChaseIndex = 0;

void onMessageCallback(WebsocketsMessage message) {
    if (message.isText()) {
        StaticJsonDocument<1024> doc; 
        DeserializationError error = deserializeJson(doc, message.c_str());

        if (!error && doc.is<JsonArray>()) {
            JsonArray array = doc.as<JsonArray>();
            for (JsonObject obj : array) {
                if (obj["id"] == MY_ESP_ID) {
                    currentEffect = obj["effect"];
                    currentR = obj["r"];
                    currentG = obj["g"];
                    currentB = obj["b"];
                }
            }
        }
    }
}

void setup() {
    Serial.begin(115200);
    random16_add_entropy(analogRead(0));
    FastLED.addLeds<WS2812B, LED_PIN, RGB>(leds, NUM_LEDS);

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }

    // Setup Websocket Callbacks
    client.onMessage(onMessageCallback);
    
    // Connect to Server
    bool connected = client.connect(WS_URL);
    if(connected) {
        Serial.println("Connected to WS Server!");
    }
}

void loop() {
    // if(client.available()) {
    //     client.poll();
    // }
    
    // Basic effect router
    if (currentEffect == 0) {
        fill_solid(leds, NUM_LEDS, CRGB::Black);
    } else if (currentEffect == 1) {
        fill_solid(leds, NUM_LEDS, CRGB(currentR, currentG, currentB));
    } else if (currentEffect == 2) {
        uint8_t brightness = beat8(60);
        CRGB breathColor = CRGB(currentR, currentG, currentB).scale8(brightness);
        fill_solid(leds, NUM_LEDS, breathColor);
    } else if (currentEffect == 3) {
        fill_solid(leds, NUM_LEDS, CRGB::Black);
        leds[chaseIndex] = CRGB(currentR, currentG, currentB);
        chaseIndex++;
        chaseIndex %= NUM_LEDS;
    } else if (currentEffect == 4) {
        for (int i = 0; i < NUM_LEDS; i++) {
            leds[i] = CHSV((rainbowHue + (i * 256 / NUM_LEDS)) % 256, 255, 255);
        }
        rainbowHue++;
    } else if (currentEffect == 5) {
        fill_solid(leds, NUM_LEDS, CRGB::Black);
        for (int i = 0; i < 5; i++) {
            int pos = (cometHead + i) % NUM_LEDS;
            uint8_t alpha = 255 - (i * 50);
            leds[pos] = CRGB(currentR, currentG, currentB).scale8(alpha);
        }
        cometHead = (cometHead + 1) % NUM_LEDS;
    } else if (currentEffect == 6) {
        for (int i = 0; i < NUM_LEDS; i++) {
            uint8_t wave = sin8((i * 30 + waveOffset) % 256);
            leds[i] = CRGB(currentR, currentG, currentB).scale8(wave);
        }
        waveOffset += 10;
    } else if (currentEffect == 7) {
        fill_solid(leds, NUM_LEDS, CRGB::Black);
        for (int i = 0; i < 3; i++) {
            int pos = (tripleChaseIndex + i * (NUM_LEDS / 3)) % NUM_LEDS;
            leds[pos] = CRGB(currentR, currentG, currentB);
        }
        tripleChaseIndex = (tripleChaseIndex + 1) % (NUM_LEDS / 3);
    } else if (currentEffect == 8) {
        for (int i = 0; i < NUM_LEDS; i++) {
            if (random8() < 20) {
                leds[i] = CRGB(currentR, currentG, currentB);
            } else {
                leds[i].fadeToBlackBy(200);
            }
        }
    } else if (currentEffect == 9) {
        for (int i = 0; i < NUM_LEDS; i++) {
            uint8_t pulse = beat8(30);
            uint8_t dist = abs(i - (NUM_LEDS / 2));
            uint8_t brightness = 255 - (dist * 40);
            leds[i] = CRGB(currentR, currentG, currentB).scale8(brightness * pulse / 255);
        }
    }

    FastLED.show();
    delay(20);
}