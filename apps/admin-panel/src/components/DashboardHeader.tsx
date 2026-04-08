import React from "react";

import { cl } from "../domain";

type DashboardHeaderProps = {
  isPhone: boolean;
  onLogout: () => void;
  onRefresh: () => void;
};

export function DashboardHeader({ isPhone, onLogout, onRefresh }: DashboardHeaderProps) {
  return (
    <header
      style={{
        padding: isPhone ? "18px 14px 14px" : "24px 24px 18px",
        maxWidth: 1560,
        margin: "0 auto",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: isPhone ? "column" : "row",
          justifyContent: "space-between",
          alignItems: isPhone ? "stretch" : "center",
          gap: 12,
          minWidth: 0,
        }}
      >
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              background: "rgba(255,255,255,0.82)",
              borderRadius: 999,
              padding: "10px 14px",
              boxShadow: cl.shadow,
              marginBottom: 12,
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: cl.green }} />
            <span style={{ fontSize: 13, fontWeight: 800 }}>Очередь кейсов активна</span>
          </div>
          <h1 style={{ margin: 0, fontSize: isPhone ? 28 : 34, letterSpacing: "-0.06em", lineHeight: 1.02 }}>
            Проверка новых повреждений
          </h1>
          <p style={{ margin: "10px 0 0", color: cl.muted, maxWidth: 620, fontSize: isPhone ? 15 : 16, lineHeight: 1.45 }}>
            Рабочая панель для спорных кейсов после завершения поездки. Назначьте кейс на себя, сравните осмотр до и
            после поездки, проверьте крупные планы и примите итоговое решение.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, flexDirection: isPhone ? "column" : "row" }}>
          <button
            onClick={onRefresh}
            style={{
              background: "#15202B",
              color: "#fff",
              borderRadius: 24,
              padding: "14px 18px",
              fontSize: 13,
              fontWeight: 800,
              alignSelf: isPhone ? "stretch" : "auto",
              width: isPhone ? "100%" : "auto",
              flexShrink: 0,
            }}
          >
            Обновить очередь
          </button>
          <button
            onClick={onLogout}
            style={{
              background: "#FFFFFF",
              color: cl.text,
              borderRadius: 24,
              padding: "14px 18px",
              fontSize: 13,
              fontWeight: 800,
              border: `1px solid ${cl.border}`,
              alignSelf: isPhone ? "stretch" : "auto",
              width: isPhone ? "100%" : "auto",
              flexShrink: 0,
            }}
          >
            Выйти
          </button>
        </div>
      </div>
    </header>
  );
}
