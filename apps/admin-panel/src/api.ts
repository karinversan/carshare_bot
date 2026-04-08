// -------------------------------------------------------------------------- //
//                                   IMPORTS                                  //
// -------------------------------------------------------------------------- //

import { API } from "./config";
import { type CaseDetail, type CaseSummary } from "./domain";
import { readAdminError } from "./utils";

// -------------------------------------------------------------------------- //
//                                    TYPES                                   //
// -------------------------------------------------------------------------- //

export type AdminApiFetch = (input: string, init?: RequestInit) => Promise<Response>;

type JsonEnvelope<T> = {
  data: T;
};

// -------------------------------------------------------------------------- //
//                                   HELPERS                                  //
// -------------------------------------------------------------------------- //

async function readJson<T>(response: Response): Promise<T> {
  return response.json() as Promise<T>;
}

// -------------------------------------------------------------------------- //
//                                   EXPORTS                                  //
// -------------------------------------------------------------------------- //

export async function fetchAdminCases(apiFetch: AdminApiFetch, filter: string): Promise<CaseSummary[]> {
  const url = filter ? `${API}/admin-cases?status=${filter}` : `${API}/admin-cases`;
  const response = await apiFetch(url);

  if (!response.ok) {
    throw new Error(await readAdminError(response, "Не удалось загрузить очередь кейсов"));
  }

  const json = await readJson<JsonEnvelope<CaseSummary[]>>(response);
  return json.data;
}

export async function fetchAdminCase(apiFetch: AdminApiFetch, caseId: string): Promise<CaseDetail> {
  const response = await apiFetch(`${API}/admin-cases/${caseId}`);

  if (!response.ok) {
    throw new Error(await readAdminError(response, "Не удалось загрузить детали кейса"));
  }

  const json = await readJson<JsonEnvelope<CaseDetail>>(response);
  return json.data;
}

export async function assignAdminCase(
  apiFetch: AdminApiFetch,
  assigneeName: string,
  caseId: string,
): Promise<void> {
  const response = await apiFetch(`${API}/admin-cases/${caseId}/assign`, {
    body: JSON.stringify({ first_name: assigneeName }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readAdminError(response, "Не удалось назначить кейс"));
  }
}

export async function updateAdminCaseStatus(
  apiFetch: AdminApiFetch,
  caseId: string,
  resolvedNote: string,
  status: string,
): Promise<void> {
  const response = await apiFetch(`${API}/admin-cases/${caseId}/status`, {
    body: JSON.stringify({
      resolved_note: resolvedNote,
      status,
    }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readAdminError(response, "Не удалось обновить статус кейса"));
  }
}
