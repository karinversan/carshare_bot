import { API } from "./config";
import {
  SLOT_ORDER,
  type ApiErrorDetail,
  type FinalizeResult,
  type InspectionData,
} from "./domain";
import { readApiError } from "./utils";

export type MiniappApiFetch = (input: string, init?: RequestInit) => Promise<Response>;

type JsonEnvelope<T> = {
  data: T;
};

type UploadedImage = {
  image_id: string;
};

type InitialCheckResult = {
  accepted: boolean;
  quality_label?: string | null;
  rejection_reason?: string | null;
};

type TelegramAuthResponse = {
  access_token: string;
};

export class DamageNotFoundError extends Error {
  constructor() {
    super("Это повреждение уже обновлено после пересъёмки. Список синхронизирован.");
    this.name = "DamageNotFoundError";
  }
}

export class InspectionClosedError extends Error {
  inspectionId: string;
  status: string;

  constructor(inspectionId: string, status: string) {
    super("Этот осмотр уже завершён и больше не доступен для редактирования.");
    this.inspectionId = inspectionId;
    this.name = "InspectionClosedError";
    this.status = status;
  }
}

async function readJson<T>(response: Response): Promise<T> {
  return response.json() as Promise<T>;
}

export async function authenticateTelegram(initData: string): Promise<string> {
  const response = await fetch(`${API}/auth/telegram`, {
    body: JSON.stringify({ init_data: initData }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось подтвердить сессию Telegram", initData));
  }

  const json = await readJson<TelegramAuthResponse>(response);
  return json.access_token;
}

export async function fetchInspectionData(
  apiFetch: MiniappApiFetch,
  inspectionId: string,
  telegramInitData?: string,
): Promise<InspectionData> {
  const response = await apiFetch(`${API}/miniapp/inspections/${inspectionId}`);

  if (!response.ok) {
    let detail: ApiErrorDetail | null = null;
    try {
      const json = await readJson<{ detail?: ApiErrorDetail | null }>(response);
      detail = json?.detail ?? null;
    } catch {
      detail = null;
    }

    if (response.status === 409 && detail?.code === "inspection_closed") {
      throw new InspectionClosedError(inspectionId, detail.status || "finalized");
    }

    throw new Error(await readApiError(response, "Не удалось загрузить инспекцию", telegramInitData));
  }

  const json = await readJson<JsonEnvelope<InspectionData>>(response);
  return json.data;
}

export async function uploadRequiredView(
  apiFetch: MiniappApiFetch,
  inspectionId: string,
  slot: string,
  file: File,
  telegramInitData?: string,
): Promise<string> {
  const uploadForm = new FormData();
  uploadForm.append("file", file);
  uploadForm.append("image_type", "required_view");
  uploadForm.append("slot_code", slot);
  uploadForm.append("capture_order", String(SLOT_ORDER.indexOf(slot) + 1));

  const response = await apiFetch(`${API}/inspections/${inspectionId}/images`, {
    body: uploadForm,
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось загрузить фото", telegramInitData));
  }

  const json = await readJson<JsonEnvelope<UploadedImage>>(response);
  return json.data.image_id;
}

export async function runInitialInspectionChecks(
  apiFetch: MiniappApiFetch,
  expectedSlot: string,
  imageId: string,
  inspectionId: string,
  telegramInitData?: string,
): Promise<InitialCheckResult> {
  const response = await apiFetch(`${API}/inspections/${inspectionId}/run-initial-checks`, {
    body: JSON.stringify({ expected_slot: expectedSlot, image_id: imageId }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось проверить фото", telegramInitData));
  }

  const json = await readJson<JsonEnvelope<InitialCheckResult>>(response);
  return json.data;
}

export async function runDamageInference(
  apiFetch: MiniappApiFetch,
  inspectionId: string,
  telegramInitData?: string,
): Promise<void> {
  const response = await apiFetch(`${API}/inspections/${inspectionId}/run-damage-inference?force_sync=true`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось запустить анализ", telegramInitData));
  }
}

export async function confirmInspectionPhotoSet(
  apiFetch: MiniappApiFetch,
  inspectionId: string,
  telegramInitData?: string,
): Promise<void> {
  const response = await apiFetch(`${API}/inspections/${inspectionId}/confirm-photo-set`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось подтвердить набор фото", telegramInitData));
  }
}

export async function reviewPredictedDamage(
  action: "confirm" | "reject" | "uncertain",
  apiFetch: MiniappApiFetch,
  damageId: string,
  telegramInitData?: string,
): Promise<void> {
  const response = await apiFetch(`${API}/miniapp/damages/${damageId}/${action}`, {
    body: JSON.stringify({}),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (response.status === 404) {
    throw new DamageNotFoundError();
  }

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось сохранить решение", telegramInitData));
  }
}

export async function attachInspectionExtraPhoto(
  apiFetch: MiniappApiFetch,
  comment: string,
  file: File,
  inspectionId: string,
  telegramInitData?: string,
): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  form.append("comment", comment.trim());

  const response = await apiFetch(`${API}/miniapp/inspections/${inspectionId}/attach-extra-photo`, {
    body: form,
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось загрузить дополнительное фото", telegramInitData));
  }
}

export async function finalizeInspectionSession(
  apiFetch: MiniappApiFetch,
  inspectionId: string,
  telegramInitData?: string,
): Promise<FinalizeResult> {
  const response = await apiFetch(`${API}/inspections/${inspectionId}/finalize`, {
    body: JSON.stringify({ photos_review_confirmed: true }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Не удалось завершить осмотр", telegramInitData));
  }

  const json = await readJson<JsonEnvelope<FinalizeResult>>(response);
  return json.data;
}
