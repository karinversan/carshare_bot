// -------------------------------------------------------------------------- //
//                                   IMPORTS                                  //
// -------------------------------------------------------------------------- //

import { CASE_STATUS_LABELS, DAMAGE_LABELS, MATCH_STATUS_LABELS, SEVERITY_LABELS, SLOT_LABELS, cl } from "./domain";

// -------------------------------------------------------------------------- //
//                                   HELPERS                                  //
// -------------------------------------------------------------------------- //

export function statusColor(status: string) {
  if (status === "open") return cl.orange;
  if (status === "in_review") return cl.blue;
  if (status === "resolved_confirmed") return cl.green;
  if (status === "resolved_no_issue") return "#64748B";
  if (status === "dismissed") return cl.red;
  return "#94A3B8";
}

export function matchColor(status: string) {
  if (status === "matched_existing") return cl.green;
  if (status === "possible_new") return cl.orange;
  if (status === "new_confirmed") return cl.red;
  return "#64748B";
}

export function caseStatusLabel(value: string) {
  return CASE_STATUS_LABELS[value] || value.replace(/_/g, " ");
}

export function matchStatusLabel(value: string) {
  return MATCH_STATUS_LABELS[value] || value.replace(/_/g, " ");
}

export function slotLabel(value?: string | null) {
  if (!value) return "Неизвестный ракурс";
  return SLOT_LABELS[value] || value.replace(/_/g, " ");
}

export function damageLabel(value?: string | null) {
  if (!value) return "Повреждение";
  return DAMAGE_LABELS[value] || value.replace(/_/g, " ");
}

export function severityLabel(value?: string | null) {
  if (!value) return "Не указан";
  return SEVERITY_LABELS[value] || value;
}

export function formatDate(value?: string | null) {
  if (!value) return "Без даты";
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      month: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export async function readAdminError(response: Response, fallback: string): Promise<string> {
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
