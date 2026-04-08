// -------------------------------------------------------------------------- //
//                                   IMPORTS                                  //
// -------------------------------------------------------------------------- //

import { SLOT_LABELS, type BBox, type PolygonPoint } from "./domain";

// -------------------------------------------------------------------------- //
//                                   HELPERS                                  //
// -------------------------------------------------------------------------- //

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function formatStatus(value: string) {
  return value.replace(/_/g, " ");
}

export function centeredBox(x: number, y: number): BBox {
  const height = 0.18;
  const width = 0.18;

  return {
    x1: clamp(x - width / 2, 0.02, 0.8),
    x2: clamp(x + width / 2, 0.2, 0.98),
    y1: clamp(y - height / 2, 0.02, 0.8),
    y2: clamp(y + height / 2, 0.2, 0.98),
  };
}

export function bboxToPolygon(bbox: BBox): PolygonPoint[] {
  return [
    [bbox.x1, bbox.y1],
    [bbox.x2, bbox.y1],
    [bbox.x2, bbox.y2],
    [bbox.x1, bbox.y2],
  ];
}

export function polygonToSvgPoints(polygon?: PolygonPoint[] | null, bbox?: BBox): string {
  const source = polygon && polygon.length >= 3 ? polygon : bbox ? bboxToPolygon(bbox) : [];

  return source
    .map(([x, y]) => `${clamp(x, 0, 1) * 100},${clamp(y, 0, 1) * 100}`)
    .join(" ");
}

export function hexToRgba(hex: string, alpha: number): string {
  const normalized = hex.replace("#", "");
  const full = normalized.length === 3
    ? normalized.split("").map((chunk) => `${chunk}${chunk}`).join("")
    : normalized;
  const int = Number.parseInt(full, 16);

  if (Number.isNaN(int)) return `rgba(21, 32, 25, ${alpha})`;

  const b = int & 255;
  const g = (int >> 8) & 255;
  const r = (int >> 16) & 255;

  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function humanizeViewLabel(label?: string) {
  if (!label) return "неподходящий ракурс";

  const normalized = label.trim().toLowerCase().replace(/^['"]|['"]$/g, "");
  const labels: Record<string, string> = {
    angled_invalid: "неподходящий угол съёмки",
    front: "Перед",
    front_left_3q: "передний левый угол",
    front_right_3q: "передний правый угол",
    front_valid: "передний ракурс",
    left_side: "Левый бок",
    other_invalid: "неподходящий ракурс",
    rear: "Зад",
    rear_left_3q: "задний левый угол",
    rear_right_3q: "задний правый угол",
    rear_valid: "задний ракурс",
    right_side: "Правый бок",
    side_valid: "боковой ракурс",
  };

  return labels[normalized] || normalized.replace(/_/g, " ");
}

export function humanizeRejectionReason(reason?: string, expectedSlot?: string) {
  if (!reason) {
    return "Фото отклонено. Попробуйте снять кадр ещё раз.";
  }

  const wrongViewMatch = reason.match(/^wrong_viewpoint:\s*expected\s+([^,]+),\s*got\s+(.+)$/);
  if (wrongViewMatch) {
    const expected = SLOT_LABELS[wrongViewMatch[1]] || SLOT_LABELS[expectedSlot || ""] || wrongViewMatch[1];
    const gotRaw = (wrongViewMatch[2] || "").trim().replace(/^['"]|['"]$/g, "").toLowerCase();
    const got = humanizeViewLabel(gotRaw);

    if (gotRaw === "angled_invalid") {
      return `Фото не подходит: машина снята под углом. Нужен кадр «${expected}». Встаньте ровнее напротив нужной стороны и снимите кузов целиком.`;
    }
    if (gotRaw === "other_invalid") {
      return `Фото не подходит: машина видна не целиком или кадр слишком обрезан. Нужен кадр «${expected}». Снимите весь кузов с нужной стороны без обрезанных краёв.`;
    }
    if (gotRaw === "front_valid" || gotRaw === "rear_valid" || gotRaw === "side_valid") {
      if (gotRaw === "side_valid" && (wrongViewMatch[1] === "left_side" || wrongViewMatch[1] === "right_side")) {
        return `Распознан боковой ракурс без уверенного определения стороны. Для кадра «${expected}» подойдите именно к нужной стороне машины и снимите кузов целиком без угла.`;
      }
      return `Фото не подходит по углу съёмки. Нужен кадр «${expected}». Перейдите к нужному ракурсу и снимите кузов целиком.`;
    }

    return `Неверный ракурс. Нужен кадр «${expected}», а сейчас больше похож на «${got}». Подойдите к нужной стороне машины и снимите кузов целиком.`;
  }

  const messages: Record<string, string> = {
    angled_invalid: "Фото не подходит: машина снята под углом. Встаньте ровнее напротив нужной стороны машины.",
    car_cut_off: "Машина обрезана. Снимите весь нужный ракурс целиком, без обрезанных краёв.",
    car_too_small: "Машина слишком далеко. Подойдите ближе, чтобы кузов занимал большую часть кадра.",
    duplicate_upload: "Это фото уже загружалось. Сделайте новый кадр этого же ракурса.",
    no_car_detected: "Машина распознана неуверенно. Снимите авто целиком и уберите лишний фон из кадра.",
    other_invalid: "Фото не подходит: машина видна не целиком или кадр слишком обрезан. Переснимите машину целиком с нужной стороны.",
    overexposed: "Кадр пересвечен. Уберите сильные блики и попробуйте снять чуть темнее.",
    quality_gate_reject: "Фото не прошло автоматическую проверку качества. Попробуйте снять ровнее, светлее и ближе.",
    too_blurry: "Фото смазано. Удерживайте телефон ровнее и дождитесь резкого кадра.",
    too_dark: "Слишком темно. Добавьте света или снимите под другим углом, чтобы кузов был хорошо виден.",
    wrong_distance: "Неподходящая дистанция. Держите машину целиком в кадре, но без слишком большого пустого фона.",
    wrong_view: "Нужен другой ракурс. Перестройтесь так, чтобы был виден именно требуемый бок или часть машины.",
  };

  const normalizedReason = reason.trim().toLowerCase().replace(/^['"]|['"]$/g, "");

  return (
    messages[normalizedReason]
    || messages[reason]
    || `Фото отклонено: ${normalizedReason.replace(/_/g, " ")}. Попробуйте снять кадр ещё раз.`
  );
}

export async function readApiError(
  response: Response,
  fallback: string,
  telegramInitData?: string,
): Promise<string> {
  if (response.status === 401) {
    if (telegramInitData) {
      return "Не удалось подтвердить сессию Telegram. Вернитесь в бот и откройте осмотр заново.";
    }
    return "Откройте этот осмотр из Telegram-бота, чтобы пройти авторизацию.";
  }

  try {
    const body = await response.json();
    const detail = body?.detail;

    if (typeof detail === "string" && detail) return detail;
    if (detail?.message) return detail.message;
    if (body?.message) return body.message;
  } catch {
    // ignore JSON parsing errors
  }

  return `${fallback} (HTTP ${response.status})`;
}
