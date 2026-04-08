import React from "react";

import { cl, type DamageAsset } from "../domain";
import { damageLabel, severityLabel } from "../utils";

type EvidenceCardProps = {
  damage?: DamageAsset | null;
  title: string;
};

export function EvidenceCard({ damage, title }: EvidenceCardProps) {
  return (
    <div
      style={{
        background: "#F8FBFC",
        border: `1px solid ${cl.border}`,
        borderRadius: 28,
        minHeight: 240,
        padding: 14,
      }}
    >
      <div style={{ color: cl.muted, fontSize: 12, fontWeight: 800, marginBottom: 10 }}>{title}</div>
      {damage?.image?.raw_url ? (
        <>
          <img
            src={damage.image.raw_url}
            alt={title}
            style={{ aspectRatio: "4 / 3", borderRadius: 22, marginBottom: 10, objectFit: "cover", width: "100%" }}
          />
          <strong style={{ display: "block", marginBottom: 4 }}>{damageLabel(damage.damage_type)}</strong>
          <div style={{ color: cl.muted, fontSize: 12 }}>
            Размер: {severityLabel(damage.severity_hint)}
          </div>
          {damage.note ? (
            <div style={{ color: cl.text, fontSize: 12, lineHeight: 1.4, marginTop: 8 }}>
              Комментарий: {damage.note}
            </div>
          ) : null}
          {damage.closeups?.length ? (
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(72px, 1fr))", marginTop: 12 }}>
              {damage.closeups.map((closeup) => (
                <a
                  key={closeup.image_id}
                  href={closeup.raw_url}
                  rel="noreferrer"
                  style={{ border: `1px solid ${cl.border}`, borderRadius: 18, display: "block", overflow: "hidden" }}
                  target="_blank"
                >
                  <img src={closeup.raw_url} alt="Крупный план" style={{ aspectRatio: "1 / 1", objectFit: "cover", width: "100%" }} />
                </a>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <div style={{ color: cl.muted, fontSize: 13 }}>Нет связанного изображения.</div>
      )}
    </div>
  );
}
