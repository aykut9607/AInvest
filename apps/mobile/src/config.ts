// on the Android emulator "localhost" works through `adb reverse` (npm run ports), which forwards
// each service port to the PC; 10.0.2.2 timed out from inside Expo Go and .NET only listens on 127.0.0.1
// for a real phone on the same Wi-Fi, replace HOST with the PC's LAN IP
const HOST = "localhost";

// one place to change when the Edge Gateway (port 5000) arrives - then all three become the gateway URL
export const API = {
  identity: `http://${HOST}:8081`,
  finance: `http://${HOST}:5293`,
  ai: `http://${HOST}:8001`,
};

export const REQUEST_TIMEOUT_MS = 10000;
