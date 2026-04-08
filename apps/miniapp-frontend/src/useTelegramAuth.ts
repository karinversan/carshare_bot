import { useEffect, useState } from "react";

import { authenticateTelegram } from "./api";
import { tg } from "./telegram";

export function useTelegramAuth() {
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function bootstrapAuth() {
      if (!tg?.initData) {
        if (!cancelled) {
          setAuthReady(true);
        }
        return;
      }

      try {
        const accessToken = await authenticateTelegram(tg.initData);
        if (!cancelled) {
          setAuthError("");
          setAuthToken(accessToken);
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Не удалось подтвердить сессию Telegram.";
          setAuthError(message);
        }
      } finally {
        if (!cancelled) {
          setAuthReady(true);
        }
      }
    }

    void bootstrapAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  async function authorizedFetch(input: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers || undefined);

    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }

    return fetch(input, { ...init, headers });
  }

  return {
    authError,
    authReady,
    authToken,
    authorizedFetch,
  };
}
