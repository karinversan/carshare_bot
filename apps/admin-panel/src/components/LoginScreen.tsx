import React from "react";

import { cl } from "../domain";

type LoginScreenProps = {
  authError: string;
  authLoading: boolean;
  loginEmail: string;
  loginPassword: string;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: () => void;
};

export function LoginScreen({
  authError,
  authLoading,
  loginEmail,
  loginPassword,
  onEmailChange,
  onPasswordChange,
  onSubmit,
}: LoginScreenProps) {
  return (
    <div
      style={{
        background: `linear-gradient(180deg, ${cl.lime} 0%, #D8FF7A 18%, ${cl.bg} 18%)`,
        display: "grid",
        fontFamily: '"SF Pro Display", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        minHeight: "100vh",
        padding: 20,
        placeItems: "center",
      }}
    >
      <div
        style={{
          background: cl.card,
          border: `1px solid ${cl.border}`,
          borderRadius: 34,
          boxShadow: cl.shadow,
          maxWidth: 460,
          padding: 24,
          width: "100%",
        }}
      >
        <div style={{ alignItems: "center", display: "inline-flex", gap: 10, marginBottom: 14 }}>
          <span style={{ background: cl.orange, borderRadius: "50%", height: 10, width: 10 }} />
          <span style={{ color: cl.muted, fontSize: 13, fontWeight: 800 }}>Защищённый доступ</span>
        </div>
        <h1 style={{ fontSize: 32, letterSpacing: "-0.05em", lineHeight: 1.02, margin: 0 }}>Вход в админку</h1>
        <p style={{ color: cl.muted, lineHeight: 1.5, margin: "12px 0 20px" }}>
          Используйте админские учётные данные, чтобы просматривать спорные кейсы и менять итоговые статусы.
        </p>
        {authError ? (
          <div
            style={{
              background: "#FFF1F0",
              border: `1px solid rgba(239, 68, 68, 0.22)`,
              borderRadius: 20,
              color: cl.red,
              fontSize: 14,
              marginBottom: 14,
              padding: 12,
            }}
          >
            {authError}
          </div>
        ) : null}
        <div style={{ display: "grid", gap: 12 }}>
          <input
            autoComplete="username"
            onChange={(event) => onEmailChange(event.target.value)}
            placeholder="admin@example.com"
            style={{ border: `1px solid ${cl.border}`, borderRadius: 20, padding: "14px 16px" }}
            value={loginEmail}
          />
          <input
            autoComplete="current-password"
            onChange={(event) => onPasswordChange(event.target.value)}
            placeholder="Пароль"
            style={{ border: `1px solid ${cl.border}`, borderRadius: 20, padding: "14px 16px" }}
            type="password"
            value={loginPassword}
          />
          <button
            disabled={authLoading}
            onClick={onSubmit}
            style={{
              background: "#15202B",
              borderRadius: 22,
              color: "#fff",
              fontSize: 14,
              fontWeight: 800,
              padding: "14px 16px",
            }}
          >
            {authLoading ? "Входим..." : "Войти"}
          </button>
        </div>
      </div>
    </div>
  );
}
