import React from "react";

import { DAMAGE_COLORS, type Img } from "../domain";
import { hexToRgba, polygonToSvgPoints } from "../utils";

type GeometryOverlayProps = {
  image: Img;
};

export function GeometryOverlay({ image }: GeometryOverlayProps) {
  const polygons = [
    ...image.predicted_damages.map((damage) => ({
      key: `pred-${damage.damage_id}`,
      points: polygonToSvgPoints(damage.polygon_json, damage.bbox_norm),
      stroke: DAMAGE_COLORS[damage.damage_type] || "#15202B",
      fill: hexToRgba(
        DAMAGE_COLORS[damage.damage_type] || "#15202B",
        damage.polygon_json && damage.polygon_json.length > 4 ? 0.22 : 0.12,
      ),
      dash: damage.polygon_json && damage.polygon_json.length > 4 ? undefined : "6 4",
    })),
    ...image.manual_damages.map((damage) => ({
      key: `manual-${damage.manual_damage_id}`,
      points: polygonToSvgPoints(damage.polygon_json, damage.bbox_norm),
      stroke: "#15202B",
      fill: "rgba(21, 32, 43, 0.08)",
      dash: "10 6",
    })),
  ].filter((shape) => !!shape.points);

  if (!polygons.length) return null;

  return (
    <svg className="vector-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      {polygons.map((shape) => (
        <polygon
          key={shape.key}
          points={shape.points}
          fill={shape.fill}
          stroke={shape.stroke}
          strokeWidth={1.25}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          strokeDasharray={shape.dash}
        />
      ))}
    </svg>
  );
}
