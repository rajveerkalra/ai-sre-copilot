const TOKEN_KEY = "sre_access_token";
const USER_KEY = "sre_auth_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string, username: string, roles: string[]) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify({ username, roles }));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getSessionUser(): { username: string; roles: string[] } | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as { username: string; roles: string[] };
  } catch {
    return null;
  }
}

export async function login(username: string, password: string) {
  const res = await fetch("/proxy/auth/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Login failed (${res.status})`);
  }
  const body = (await res.json()) as {
    access_token: string;
    username: string;
    roles: string[];
  };
  setSession(body.access_token, body.username, body.roles);
  return body;
}
