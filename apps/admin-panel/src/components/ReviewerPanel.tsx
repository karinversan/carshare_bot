import React from "react";

import { cl, type CaseDetail } from "../domain";

type ReviewerPanelProps = {
  assigneeName: string;
  caseDetail: CaseDetail;
  isPhone: boolean;
  isTablet: boolean;
  note: string;
  onAssign: () => void;
  onAssigneeNameChange: (value: string) => void;
  onNoteChange: (value: string) => void;
};

export function ReviewerPanel({
  assigneeName,
  caseDetail,
  isPhone,
  isTablet,
  note,
  onAssign,
  onAssigneeNameChange,
  onNoteChange,
}: ReviewerPanelProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: isTablet ? "minmax(0, 1fr)" : "minmax(0, 1fr) 260px",
        gap: 16,
        marginBottom: 18,
        alignItems: "start",
      }}
    >
      <div
        style={{
          background: "#F7FBFC",
          border: `1px solid ${cl.border}`,
          borderRadius: 28,
          padding: 16,
          minWidth: 0,
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 800, color: cl.muted, marginBottom: 10 }}>Назначение кейса</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", minWidth: 0 }}>
          <input
            value={assigneeName}
            onChange={(event) => onAssigneeNameChange(event.target.value)}
            placeholder="Имя проверяющего"
            style={{
              flex: 1,
              minWidth: isPhone ? "100%" : 180,
              borderRadius: 20,
              border: `1px solid ${cl.border}`,
              padding: "12px 14px",
              boxSizing: "border-box",
            }}
          />
          <button
            onClick={onAssign}
            style={{
              background: "#15202B",
              color: "#fff",
              borderRadius: 20,
              padding: "12px 14px",
              fontWeight: 800,
              width: isPhone ? "100%" : "auto",
            }}
          >
            Назначить на себя
          </button>
        </div>
        <div style={{ marginTop: 10, fontSize: 13, color: cl.muted }}>
          Текущий исполнитель: <strong style={{ color: cl.text }}>{caseDetail.assignee_name || "не назначен"}</strong>
        </div>
      </div>
      <div
        style={{
          background: "#F7FBFC",
          border: `1px solid ${cl.border}`,
          borderRadius: 28,
          padding: 16,
          minWidth: 0,
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 800, color: cl.muted, marginBottom: 10 }}>Комментарий по решению</div>
        <textarea
          value={note}
          onChange={(event) => onNoteChange(event.target.value)}
          placeholder="Что показала проверка? Например: подтверждаем новую царапину на правом борту."
          style={{
            width: "100%",
            minHeight: 92,
            resize: "vertical",
            borderRadius: 20,
            border: `1px solid ${cl.border}`,
            padding: 12,
            boxSizing: "border-box",
          }}
        />
      </div>
    </div>
  );
}
