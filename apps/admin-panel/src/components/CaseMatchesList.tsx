import React from "react";

import { cl, type CaseDetail } from "../domain";
import { EvidenceCard } from "./EvidenceCard";
import { matchColor, matchStatusLabel, slotLabel } from "../utils";

type CaseMatchesListProps = {
  isPhone: boolean;
  matches: CaseDetail["matches"];
};

export function CaseMatchesList({ isPhone, matches }: CaseMatchesListProps) {
  return (
    <div style={{ display: "grid", gap: 14, marginBottom: 18 }}>
      {matches.map((match) => (
        <article
          key={match.id}
          style={{
            border: `1px solid ${cl.border}`,
            borderRadius: 30,
            padding: 16,
            background: "#FCFDFE",
            minWidth: 0,
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: isPhone ? "column" : "row",
              justifyContent: "space-between",
              gap: 12,
              alignItems: isPhone ? "stretch" : "center",
              marginBottom: 14,
              minWidth: 0,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <strong style={{ display: "block", marginBottom: 4 }}>{slotLabel(match.view_slot)}</strong>
              <span style={{ color: cl.muted, fontSize: 12 }}>
                Оценка совпадения: {(match.match_score * 100).toFixed(1)}%
              </span>
            </div>
            <span
              style={{
                background: matchColor(match.status),
                color: "#fff",
                borderRadius: 999,
                padding: "7px 10px",
                fontSize: 11,
                fontWeight: 900,
                textTransform: "uppercase",
                alignSelf: isPhone ? "flex-start" : "auto",
                maxWidth: "100%",
                overflowWrap: "anywhere",
              }}
            >
              {matchStatusLabel(match.status)}
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: isPhone ? "minmax(0, 1fr)" : "1fr 1fr", gap: 12, minWidth: 0 }}>
            <EvidenceCard title="Осмотр до поездки" damage={match.pre_damage} />
            <EvidenceCard title="Осмотр после поездки" damage={match.post_damage} />
          </div>
        </article>
      ))}
    </div>
  );
}
