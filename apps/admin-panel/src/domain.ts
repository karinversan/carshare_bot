// -------------------------------------------------------------------------- //
//                                    TYPES                                   //
// -------------------------------------------------------------------------- //

export type CaseSummary = {
  assignee_name?: string | null;
  comparison_id: string;
  id: string;
  opened_at: string;
  priority: string;
  status: string;
  summary: string;
  title: string;
  vehicle_id: string;
};

export type ImageAsset = {
  image_id: string;
  raw_url: string;
  slot_code: string;
};

export type CloseupAsset = {
  image_id: string;
  raw_url: string;
  slot_code?: string;
};

export type DamageAsset = {
  closeups?: CloseupAsset[];
  damage_id: string;
  damage_type: string;
  image?: ImageAsset | null;
  note?: string | null;
  severity_hint?: string | null;
};

export type MatchDetail = {
  id: string;
  match_score: number;
  post_damage?: DamageAsset | null;
  pre_damage?: DamageAsset | null;
  status: string;
  view_slot: string;
};

export type CaseDetail = {
  assignee_name?: string | null;
  comparison: {
    matched_count?: number;
    new_confirmed_count?: number;
    possible_new_count?: number;
  };
  id: string;
  matches: MatchDetail[];
  status: string;
  summary: string;
  title: string;
  vehicle_id: string;
};

// -------------------------------------------------------------------------- //
//                                  CONSTANTS                                 //
// -------------------------------------------------------------------------- //

export const cl = {
  bg: "#EFF4F2",
  blue: "#2563EB",
  border: "rgba(16, 32, 46, 0.08)",
  card: "#FFFFFF",
  green: "#21C45A",
  lime: "#B8FF2C",
  muted: "#6D7781",
  orange: "#F59E0B",
  red: "#EF4444",
  shadow: "0 20px 42px rgba(16, 32, 46, 0.12)",
  text: "#10202E",
};

export const CASE_STATUS_LABELS: Record<string, string> = {
  dismissed: "Отклонён",
  in_review: "На проверке",
  open: "Открыт",
  resolved_confirmed: "Подтверждено",
  resolved_no_issue: "Без новых повреждений",
};

export const DAMAGE_LABELS: Record<string, string> = {
  broken_part: "Сломанная деталь",
  crack: "Трещина",
  dent: "Вмятина",
  scratch: "Царапина",
};

export const MATCH_STATUS_LABELS: Record<string, string> = {
  matched_existing: "Совпадает с осмотром до поездки",
  new_confirmed: "Новое подтверждённое",
  not_visible_enough: "Недостаточно видно",
  possible_match: "Похожее совпадение",
  possible_new: "Вероятно новое",
  requires_admin_review: "Нужна проверка",
};

export const SEVERITY_LABELS: Record<string, string> = {
  medium: "Среднее",
  severe: "Сильное",
  small: "Малое",
};

export const SLOT_LABELS: Record<string, string> = {
  front: "Перед",
  left_side: "Левый бок",
  rear: "Зад",
  right_side: "Правый бок",
};
