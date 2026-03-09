/**
 * ClawMatch API client — communicates with the bot-matcher server.
 *
 * All functions accept a `baseUrl` (e.g. "http://localhost:18800") and
 * return parsed JSON or throw on failure.
 */

async function request(baseUrl, path, options = {}) {
  const url = `${baseUrl.replace(/\/+$/, "")}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

/** GET /id — returns { peer_id, agent_id } */
export function fetchIdentity(baseUrl) {
  return request(baseUrl, "/id");
}

/** GET /health — returns { status, peer_id, agent_id, uptime, ... } */
export function fetchHealth(baseUrl) {
  return request(baseUrl, "/health");
}

/** GET /forest — returns { trees: [...], count } */
export function fetchForest(baseUrl) {
  return request(baseUrl, "/forest");
}

/** GET /handshake?peer=X — returns the full handshake JSON */
export function fetchHandshake(baseUrl, peerId) {
  return request(baseUrl, `/handshake?peer=${encodeURIComponent(peerId)}`);
}

/** GET /notifications — returns { notifications: [...], count } */
export function fetchNotifications(baseUrl) {
  return request(baseUrl, "/notifications");
}

/** POST /accept — accept a pending connection */
export function acceptConnection(baseUrl, peerId) {
  return request(baseUrl, "/accept", {
    method: "POST",
    body: JSON.stringify({ peer_id: peerId }),
  });
}

/** POST /message — send a watering message */
export function sendWaterMessage(baseUrl, peerId, topic, content) {
  return request(baseUrl, "/message", {
    method: "POST",
    body: JSON.stringify({
      sender_id: "__self__",
      content,
      type: "water",
      topic,
    }),
  });
}
