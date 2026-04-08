import React from "react";

import { cl, type CaseDetail } from "../domain";
import { caseStatusLabel, statusColor } from "../utils";

type CaseOverviewProps = {
  caseDetail: CaseDetail;
  isPhone: boolean;
};

export function CaseOverview({ caseDetail, isPhone }: CaseOverviewProps) {
  return (
    <>
      <div
        style={{
          display: "flex",
          flexDirection: isPhone ? "column" : "row",
          justifyContent: "space-between",
          gap: 16,
          alignItems: isPhone ? "stretch" : "flex-start",
          marginBottom: 18,
          minWidth: 0,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <h2 style={{ margin: 0, fontSize: isPhone ? 24 : 30, letterSpacing: "-0.05em", overflowWrap: "anywhere" }}>
            {caseDetail.title}
          </h2>
          <p style={{ margin: "8px 0 0", color: cl.muted }}>
            Авто {caseDetail.vehicle_id} • {caseDetail.summary}
          </p>
        </div>
        <span
          style={{
            background: statusColor(caseDetail.status),
            color: "#fff",
            borderRadius: 999,
            padding: "8px 12px",
            fontSize: 12,
            fontWeight: 900,
            textTransform: "uppercase",
            alignSelf: isPhone ? "flex-start" : "auto",
            maxWidth: "100%",
            overflowWrap: "anywhere",
          }}
        >
          {caseStatusLabel(caseDetail.status)}
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: isPhone ? "minmax(0, 1fr)" : "repeat(3, minmax(0, 1fr))",
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div style={{ background: "#F2FFF7", borderRadius: 28, padding: 16, border: `1px solid ${cl.border}` }}>
          <div style={{ fontSize: 30, fontWeight: 900, color: cl.green }}>{caseDetail.comparison?.matched_count ?? 0}</div>
          <div style={{ fontSize: 12, color: cl.muted }}>Совпало с осмотром до поездки</div>
        </div>
        <div style={{ background: "#FFF8ED", borderRadius: 28, padding: 16, border: `1px solid ${cl.border}` }}>
          <div style={{ fontSize: 30, fontWeight: 900, color: cl.orange }}>{caseDetail.comparison?.possible_new_count ?? 0}</div>
          <div style={{ fontSize: 12, color: cl.muted }}>Вероятно новые</div>
        </div>
        <div style={{ background: "#FFF2F1", borderRadius: 28, padding: 16, border: `1px solid ${cl.border}` }}>
          <div style={{ fontSize: 30, fontWeight: 900, color: cl.red }}>{caseDetail.comparison?.new_confirmed_count ?? 0}</div>
          <div style={{ fontSize: 12, color: cl.muted }}>Подтверждённо новые</div>
        </div>
      </div>
    </>
  );
}
