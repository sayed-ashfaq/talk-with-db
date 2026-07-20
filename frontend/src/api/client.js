const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8010";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    throw new ApiError(`Can't reach the server — is the backend running? (${err.message})`, 0);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Request failed (${response.status})`, response.status);
  }

  return response.status === 204 ? null : response.json();
}

export function sendChatMessage(message, history) {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

export function listConnections() {
  return request("/connections");
}

export function createConnection(payload) {
  return request("/connections", { method: "POST", body: JSON.stringify(payload) });
}

export function activateConnection(id) {
  return request(`/connections/${id}/activate`, { method: "POST" });
}

export function deleteConnection(id) {
  return request(`/connections/${id}`, { method: "DELETE" });
}

export function getSchemaGraph() {
  return request("/connections/schema-graph");
}
