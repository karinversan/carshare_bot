import React from "react";

import { cl, type CaseSummary } from "../domain";
import { caseStatusLabel, formatDate, statusColor } from "../utils";

type CaseQueueSidebarProps = {
  cases: CaseSummary[];
  filter: string;
  isPhone: boolean;
  isTablet: boolean;
  loading: boolean;
  onFilterChange: (value: string) => void;
  onSelectCase: (caseId: string) => void;
  selectedCaseId?: string;
};

const FILTERS = ["", "open", "in_review", "resolved_confirmed", "resolved_no_issue", "dismissed"];

export function CaseQueueSidebar({
  cases,
  filter,
  isPhone,
  isTablet,
  loading,
  onFilterChange,
  onSelectCase,
  selectedCaseId,
}: CaseQueueSidebarProps) {
  return (
    <aside
      style={{
        background: cl.card,
        border: `1px solid ${cl.border}`,
        borderRadius: 34,
        boxShadow: cl.shadow,
        overflow: "hidden",
        minHeight: isTablet ? "auto" : "calc(100vh - 190px)",
        minWidth: 0,
      }}
    >
      <div style={{ padding: 18, borderBottom: `1px solid ${cl.border}` }}>
        <div style={{ fontSize: 12, color: cl.muted, fontWeight: 800, marginBottom: 10 }}>Фильтр по статусу</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {FILTERS.map((value) => (
            <button
              key={value || "all"}
              onClick={() => onFilterChange(value)}
              style={{
                padding: "8px 12px",
                borderRadius: 999,
                background: filter === value ? "#15202B" : "#F2F6F8",
                color: filter === value ? "#fff" : cl.text,
                fontSize: 12,
                fontWeight: 800,
                maxWidth: "100%",
                overflowWrap: "anywhere",
              }}
            >
              {value ? caseStatusLabel(value) : "Все"}
            </button>
          ))}
        </div>
      </div>
      <div style={{ maxHeight: isTablet ? "none" : "calc(100vh - 280px)", overflowY: isTablet ? "visible" : "auto" }}>
        {cases.length === 0 && !loading ? (
          <div style={{ padding: 28, color: cl.muted }}>Очередь пуста.</div>
        ) : null}
        {cases.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelectCase(item.id)}
            style={{
              width: "100%",
              background: selectedCaseId === item.id ? "#F4FFF7" : "transparent",
              padding: 16,
              borderBottom: `1px solid ${cl.border}`,
              textAlign: "left",
              minWidth: 0,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start", marginBottom: 8 }}>
              <strong style={{ lineHeight: 1.35, minWidth: 0, overflowWrap: "anywhere" }}>{item.title}</strong>
              <span
                style={{
                  background: statusColor(item.status),
                  color: "#fff",
                  borderRadius: 999,
                  padding: "6px 9px",
                  fontSize: 10,
                  fontWeight: 900,
                  textTransform: "uppercase",
                  whiteSpace: isPhone ? "normal" : "nowrap",
                  overflowWrap: "anywhere",
                  textAlign: "center",
                  flexShrink: 0,
                }}
              >
                {caseStatusLabel(item.status)}
              </span>
            </div>
            <div style={{ fontSize: 13, color: cl.muted, lineHeight: 1.45, overflowWrap: "anywhere" }}>{item.summary}</div>
            <div style={{ marginTop: 10, fontSize: 11, color: cl.muted }}>
              Авто {item.vehicle_id} • {item.assignee_name ? `Назначен: ${item.assignee_name}` : "Без исполнителя"} • {formatDate(item.opened_at)}
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}
