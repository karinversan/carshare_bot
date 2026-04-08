import React from "react";

import { cl } from "../domain";

type CaseActionBarProps = {
  isPhone: boolean;
  onUpdateStatus: (status: string) => void;
};

export function CaseActionBar({ isPhone, onUpdateStatus }: CaseActionBarProps) {
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
      <button
        onClick={() => onUpdateStatus("in_review")}
        style={{ background: cl.blue, color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
      >
        Взять в работу
      </button>
      <button
        onClick={() => onUpdateStatus("resolved_confirmed")}
        style={{ background: cl.green, color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
      >
        Подтвердить новое повреждение
      </button>
      <button
        onClick={() => onUpdateStatus("resolved_no_issue")}
        style={{ background: "#64748B", color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
      >
        Новых повреждений нет
      </button>
      <button
        onClick={() => onUpdateStatus("dismissed")}
        style={{ background: cl.red, color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
      >
        Отклонить кейс
      </button>
    </div>
  );
}
