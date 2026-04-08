// -------------------------------------------------------------------------- //
//                                    TYPES                                   //
// -------------------------------------------------------------------------- //

export type ApiErrorDetail = {
  code?: string;
  message?: string;
  status?: string;
};

export type BBox = {
  x1: number;
  x2: number;
  y1: number;
  y2: number;
};

export type PolygonPoint = [number, number];

export type Closeup = {
  comment?: string;
  created_at?: string;
  image_id: string;
  raw_url: string;
  slot_code?: string;
};

export type Damage = {
  bbox_norm: BBox;
  closeups?: Closeup[];
  confidence: number;
  damage_id: string;
  damage_type: string;
  polygon_json?: PolygonPoint[] | null;
  review_id: string;
  review_note?: string;
  review_status: string;
};

export type ExtraPhotoPreview = {
  status: "uploading" | "error";
  url: string;
};

export type FinalizeResult = {
  canonical_damage_count: number;
  comparison_id?: string | null;
  comparison_status?: string;
  inspection_id: string;
  status: string;
};

export type Img = {
  image_closeups?: Closeup[];
  image_id: string;
  manual_damages: ManualDamage[];
  overlay_url?: string;
  predicted_damages: Damage[];
  raw_url: string;
  slot_code: string;
  status: string;
};

export type InspectionData = {
  accepted_slots: string[];
  extra_photos?: Closeup[];
  images: Img[];
  inspection_id: string;
  required_slots: string[];
  status: string;
  vehicle_id?: string | null;
  vehicle_plate?: string | null;
  vehicle_title?: string | null;
};

export type LocalPreview = {
  source: "hero" | "slot";
  status: "uploading" | "rejected" | "error";
  url: string;
};

export type ManualDamage = {
  bbox_norm: BBox;
  closeups?: Closeup[];
  damage_type: string;
  manual_damage_id: string;
  note?: string | null;
  polygon_json?: PolygonPoint[] | null;
  severity_hint: string;
};

// -------------------------------------------------------------------------- //
//                                  CONSTANTS                                 //
// -------------------------------------------------------------------------- //

export const AUTO_DECISION_LABELS: Record<string, string> = {
  confirmed: "Автопринято",
  pending: "Ожидает",
  rejected: "Отфильтровано",
  uncertain: "Нужна проверка админа",
};

export const DAMAGE_COLORS: Record<string, string> = {
  broken_part: "#FF5C59",
  crack: "#FF9F0A",
  dent: "#13B5FF",
  scratch: "#2DCB70",
};

export const DAMAGE_LABELS: Record<string, string> = {
  broken_part: "Сломанная деталь",
  crack: "Трещина",
  dent: "Вмятина",
  scratch: "Царапина",
};

export const REVIEW_LABELS: Record<string, string> = {
  confirmed: "Подтверждено",
  pending: "Ожидает",
  rejected: "Отклонено",
  uncertain: "Неуверенно",
};

export const SLOT_LABELS: Record<string, string> = {
  front: "Перед",
  left_side: "Левый бок",
  rear: "Зад",
  right_side: "Правый бок",
};

export const SLOT_ORDER = ["front", "left_side", "right_side", "rear"] as const;

export const SLOT_TIPS: Record<string, string> = {
  front: "Покажите весь передний бампер, капот и фары целиком.",
  left_side: "Снимите весь левый бок: крылья, двери и пороги.",
  rear: "Покажите задний бампер, крышку багажника и фонари.",
  right_side: "Снимите весь правый бок: крылья, двери и пороги.",
};
