// on the Android emulator "localhost" works through `adb reverse` (npm run ports), which forwards
// the gateway port to the PC; 10.0.2.2 timed out from inside Expo Go and .NET only listens on 127.0.0.1
// for a real phone on the same Wi-Fi, replace HOST with the PC's LAN IP
const HOST = "localhost";

// the app talks to the Edge Gateway only; the gateway checks the token and forwards each path to its service
// (/auth -> Identity, /api/Profiles -> Finance Profile, /ai -> AI). The services' own ports are not used here.
export const GATEWAY_URL = `http://${HOST}:5000`;

export const REQUEST_TIMEOUT_MS = 10000;
