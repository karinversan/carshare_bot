import React from "react";

import {
  AUTO_DECISION_LABELS,
  DAMAGE_COLORS,
  DAMAGE_LABELS,
  REVIEW_LABELS,
  type Damage,
} from "../domain";

type PredictedDamageCardProps = {
  damage: Damage;
};

export function PredictedDamageCard({ damage }: PredictedDamageCardProps) {
  const color = DAMAGE_COLORS[damage.damage_type] || "#15202B";
  const reviewColor =
    damage.review_status === "confirmed"
      ? "#2DCB70"
      : damage.review_status === "rejected"
        ? "#FF5C59"
        : damage.review_status === "uncertain"
          ? "#7E8794"
          : "#FF9F0A";

  return (
    <div className="damage-card">
      <div className="damage-head">
        <div className="damage-title">
          <div className="damage-icon" style={{ background: color }}>
            {(DAMAGE_LABELS[damage.damage_type] || damage.damage_type).slice(0, 1).toUpperCase()}
          </div>
          <div>
            <strong>{DAMAGE_LABELS[damage.damage_type] || damage.damage_type}</strong>
            <span>
              {Math.round(damage.confidence * 100)}% уверенность
              {damage.polygon_json && damage.polygon_json.length > 4 ? " · контур по маске" : " · контур области"}
            </span>
          </div>
        </div>
        <div className="review-pill" style={{ background: reviewColor }}>
          {AUTO_DECISION_LABELS[damage.review_status] || REVIEW_LABELS[damage.review_status] || damage.review_status}
        </div>
      </div>
      <div className="muted" style={{ marginTop: 10 }}>
        {damage.review_status === "confirmed"
          ? "Высокая уверенность: повреждение автоматически учтено."
          : damage.review_status === "uncertain"
            ? "Средняя уверенность: будет отправлено в админ-проверку при отсутствии совпадения с PRE."
            : "Низкая уверенность: не учитывается автоматически."}
      </div>
    </div>
  );
}
