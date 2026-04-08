// -------------------------------------------------------------------------- //
//                                   IMPORTS                                  //
// -------------------------------------------------------------------------- //

import { useState } from "react";

import { ADMIN_EMAIL_KEY, ADMIN_TOKEN_KEY, API } from "./config";
import { readAdminError } from "./utils";

// -------------------------------------------------------------------------- //
//                                    TYPES                                   //
// -------------------------------------------------------------------------- //

type LoginResponse = {
  access_token: string;
};

// -------------------------------------------------------------------------- //
//                                   EXPORTS                                  //
// -------------------------------------------------------------------------- //

export function useAdminSession() {
  const [authToken, setAuthToken] = useState(() => window.localStorage.getItem(ADMIN_TOKEN_KEY) || "");
  const [loginEmail, setLoginEmail] = useState(() => window.localStorage.getItem(ADMIN_EMAIL_KEY) || "admin@example.com");
  const [loginPassword, setLoginPassword] = useState("admin123");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");

  async function apiFetch(input: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers || undefined);
    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }

    const response = await fetch(input, { ...init, headers });
    if (response.status === 401 || response.status === 403) {
      setAuthToken("");
      window.localStorage.removeItem(ADMIN_TOKEN_KEY);
    }
    return response;
  }

  async function login() {
    setAuthLoading(true);
    setAuthError("");
    try {
      const response = await fetch(`${API}/auth/admin/login`, {
        body: JSON.stringify({
          email: loginEmail.trim(),
          password: loginPassword,
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(await readAdminError(response, "Не удалось войти в админку"));
      }

      const json = await response.json() as LoginResponse;
      window.localStorage.setItem(ADMIN_TOKEN_KEY, json.access_token);
      window.localStorage.setItem(ADMIN_EMAIL_KEY, loginEmail.trim());
      setAuthToken(json.access_token);
      setAuthError("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось войти в админку.";
      setAuthError(message);
    } finally {
      setAuthLoading(false);
    }
  }

  function logout() {
    setAuthToken("");
    window.localStorage.removeItem(ADMIN_TOKEN_KEY);
  }

  return {
    apiFetch,
    authError,
    authLoading,
    authToken,
    login,
    loginEmail,
    loginPassword,
    logout,
    setAuthError,
    setLoginEmail,
    setLoginPassword,
  };
}
