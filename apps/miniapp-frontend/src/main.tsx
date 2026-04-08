import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";

import {
  attachInspectionCloseup,
  attachInspectionExtraPhoto,
  confirmInspectionPhotoSet,
  createManualDamage,
  DamageNotFoundError,
  fetchInspectionData,
  finalizeInspectionSession,
  InspectionClosedError,
  reviewPredictedDamage,
  runDamageInference,
  runInitialInspectionChecks,
  uploadRequiredView,
} from "./api";
import {
  AUTO_DECISION_LABELS,
  DAMAGE_COLORS,
  DAMAGE_LABELS,
  DAMAGE_TYPES,
  REVIEW_LABELS,
  SEVERITY,
  SLOT_LABELS,
  SLOT_ORDER,
  SLOT_TIPS,
  type BBox,
  type Damage,
  type DraftManualDamage,
  type ExtraPhotoPreview,
  type FinalizeResult,
  type Img,
  type InspectionData,
  type LocalPreview,
  type ManualDamage,
} from "./domain";
import { miniappStyles } from "./styles";
import { tg } from "./telegram";
import { useTelegramAuth } from "./useTelegramAuth";
import {
  centeredBox,
  clamp,
  formatStatus,
  hexToRgba,
  humanizeRejectionReason,
  polygonToSvgPoints,
} from "./utils";

function App() {
  const params = new URLSearchParams(window.location.search);
  const [inspectionId, setInspectionId] = useState(params.get("inspection_id") || "");
  const { authError, authReady, authToken, authorizedFetch } = useTelegramAuth();
  const [data, setData] = useState<InspectionData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [finalizeResult, setFinalizeResult] = useState<FinalizeResult | null>(null);
  const [photosReviewConfirmed, setPhotosReviewConfirmed] = useState(false);
  const [slotFeedback, setSlotFeedback] = useState<Record<string, string>>({});
  const [localPreviews, setLocalPreviews] = useState<Record<string, LocalPreview | undefined>>({});
  const [showOverlayByImage, setShowOverlayByImage] = useState<Record<string, boolean>>({});
  const [manualModeByImage, setManualModeByImage] = useState<Record<string, boolean>>({});
  const [manualType, setManualType] = useState<(typeof DAMAGE_TYPES)[number]>("scratch");
  const [manualSeverity, setManualSeverity] = useState<(typeof SEVERITY)[number]>("small");
  const [manualDrafts, setManualDrafts] = useState<DraftManualDamage[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [uploadingSlot, setUploadingSlot] = useState<string | null>(null);
  const [uploadingCloseupFor, setUploadingCloseupFor] = useState<string | null>(null);
  const [uploadingImageCloseupFor, setUploadingImageCloseupFor] = useState<string | null>(null);
  const [uploadingExtraPhoto, setUploadingExtraPhoto] = useState(false);
  const [extraPhotoComment, setExtraPhotoComment] = useState("");
  const [extraPhotoPreview, setExtraPhotoPreview] = useState<ExtraPhotoPreview | null>(null);
  const viewerRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const localPreviewsRef = useRef<Record<string, LocalPreview | undefined>>({});

  useEffect(() => {
    tg?.ready?.();
    tg?.expand?.();
  }, []);
  const authResolved = authReady && (tg?.initData ? !!authToken : true);

  useEffect(() => {
    if (inspectionId && authResolved) {
      void loadInspection(inspectionId);
    }
  }, [inspectionId, authResolved]);

  useEffect(() => {
    localPreviewsRef.current = localPreviews;
  }, [localPreviews]);

  useEffect(() => {
    return () => {
      Object.values(localPreviewsRef.current).forEach((preview) => {
        if (preview?.url) {
          URL.revokeObjectURL(preview.url);
        }
      });
    };
  }, []);

  useEffect(() => {
    return () => {
      if (extraPhotoPreview?.url) {
        URL.revokeObjectURL(extraPhotoPreview.url);
      }
    };
  }, [extraPhotoPreview]);

  const orderedImages = useMemo(() => {
    if (!data) return [];
    const order = new Map(SLOT_ORDER.map((slot, index) => [slot, index]));
    return [...data.images].sort((a, b) => (order.get(a.slot_code) ?? 99) - (order.get(b.slot_code) ?? 99));
  }, [data]);

  const imagesBySlot = useMemo(() => {
    return orderedImages.reduce<Record<string, Img>>((acc, image) => {
      acc[image.slot_code] = image;
      return acc;
    }, {});
  }, [orderedImages]);

  const draftsByImage = useMemo(() => {
    return manualDrafts.reduce<Record<string, DraftManualDamage[]>>((acc, draft) => {
      if (!acc[draft.image_id]) acc[draft.image_id] = [];
      acc[draft.image_id].push(draft);
      return acc;
    }, {});
  }, [manualDrafts]);
  const selectedDraft = useMemo(
    () => manualDrafts.find((draft) => draft.draft_id === selectedDraftId) || null,
    [manualDrafts, selectedDraftId],
  );

  const acceptedCount = data?.accepted_slots.length ?? 0;
  const captureComplete = !!data && acceptedCount === data.required_slots.length;
  const optionalPhotoStage = !!data && captureComplete && data.status === "capturing_optional_photos";
  const photoSetConfirmed = !!data && captureComplete && data.status === "ready_for_inference";
  const inferenceRunning = !!data && data.status === "inference_running";
  const inspectionFinalized = !!finalizeResult || data?.status === "finalized";
  const inferenceReady =
    !!data &&
    !inspectionFinalized &&
    captureComplete &&
    ["ready_for_review", "under_review", "finalized"].includes(data.status);
  const waitingForInference =
    !!data &&
    !inspectionFinalized &&
    captureComplete &&
    !inferenceReady &&
    (optionalPhotoStage || photoSetConfirmed || inferenceRunning);
  const extraPhotos = data?.extra_photos ?? [];
  const totalUploadedPhotos = acceptedCount + extraPhotos.length;

  useEffect(() => {
    if (!tg?.MainButton) return;
    tg.MainButton.hide();
  }, [tg, data, captureComplete, finalizeResult]);

  useEffect(() => {
    if (!selectedDraftId) return;
    const stillExists = manualDrafts.some((draft) => draft.draft_id === selectedDraftId);
    if (!stillExists) {
      setSelectedDraftId(null);
    }
  }, [manualDrafts, selectedDraftId]);

  async function loadInspection(id: string) {
    setLoading(true);
    setError("");
    try {
      const inspection = await fetchInspectionData(authorizedFetch, id, tg?.initData);
      setData(inspection);
    } catch (error) {
      if (error instanceof InspectionClosedError) {
        setData(null);
        setFinalizeResult((current) =>
          current ?? {
            canonical_damage_count: 0,
            inspection_id: id,
            status: error.status,
          },
        );
        setError(error.message);
        return;
      }

      const message = error instanceof Error ? error.message : "Не удалось загрузить инспекцию.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function uploadRequired(slot: string, file: File, source: "hero" | "slot" = "slot") {
    if (!data) return;
    const previewUrl = URL.createObjectURL(file);
    const previousPreview = localPreviews[slot];
    setUploadingSlot(slot);
    setError("");
    setLocalPreviews((current) => ({ ...current, [slot]: { url: previewUrl, status: "uploading", source } }));
    setSlotFeedback((current) => ({ ...current, [slot]: "Проверяем фото…" }));
    try {
      const imageId = await uploadRequiredView(authorizedFetch, data.inspection_id, slot, file, tg?.initData);
      const checkResult = await runInitialInspectionChecks(
        authorizedFetch,
        slot,
        imageId,
        data.inspection_id,
        tg?.initData,
      );

      if (!checkResult.accepted) {
        const reason = checkResult.rejection_reason || checkResult.quality_label || "Фото отклонено";
        setSlotFeedback((current) => ({ ...current, [slot]: humanizeRejectionReason(reason, slot) }));
        setLocalPreviews((current) => ({ ...current, [slot]: { url: previewUrl, status: "rejected", source } }));
        if (previousPreview?.url && previousPreview.url !== previewUrl) {
          URL.revokeObjectURL(previousPreview.url);
        }
        await loadInspection(data.inspection_id);
        return;
      }

      setSlotFeedback((current) => ({ ...current, [slot]: "Фото принято" }));
      setPhotosReviewConfirmed(false);
      await loadInspection(data.inspection_id);
      setLocalPreviews((current) => {
        const next = { ...current };
        delete next[slot];
        return next;
      });
      URL.revokeObjectURL(previewUrl);
      if (previousPreview?.url && previousPreview.url !== previewUrl) {
        URL.revokeObjectURL(previousPreview.url);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось загрузить фото.";
      setError(message);
      setSlotFeedback((current) => ({ ...current, [slot]: "Ошибка загрузки" }));
      setLocalPreviews((current) => ({ ...current, [slot]: { url: previewUrl, status: "error", source } }));
      if (previousPreview?.url && previousPreview.url !== previewUrl) {
        URL.revokeObjectURL(previousPreview.url);
      }
    } finally {
      setUploadingSlot(null);
    }
  }

  async function runInference(explicitInspectionId?: string) {
    const currentInspectionId = explicitInspectionId || data?.inspection_id;
    if (!currentInspectionId) return;
    if (data?.status !== "ready_for_inference") {
      setError("Сначала подтвердите набор фото перед запуском анализа.");
      return;
    }
    setBusy(true);
    setPhotosReviewConfirmed(false);
    setError("");
    try {
      await runDamageInference(authorizedFetch, currentInspectionId, tg?.initData);
      await loadInspection(currentInspectionId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось запустить анализ.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmPhotoSet() {
    if (!data) return;
    setBusy(true);
    setError("");
    try {
      await confirmInspectionPhotoSet(authorizedFetch, data.inspection_id, tg?.initData);
      await loadInspection(data.inspection_id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось подтвердить набор фото.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  async function updateDecision(damageId: string, action: "confirm" | "reject" | "uncertain") {
    setBusy(true);
    setError("");
    try {
      await reviewPredictedDamage(action, authorizedFetch, damageId, tg?.initData);
      if (data) await loadInspection(data.inspection_id);
    } catch (error) {
      if (error instanceof DamageNotFoundError) {
        if (data) await loadInspection(data.inspection_id);
        setError(error.message);
        return;
      }

      const message = error instanceof Error ? error.message : "Не удалось сохранить решение.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  function queueManualDamage(imageId: string, x: number, y: number) {
    const bbox = centeredBox(x, y);
    const draft: DraftManualDamage = {
      draft_id: `${imageId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      image_id: imageId,
      damage_type: manualType,
      bbox_norm: bbox,
      severity_hint: manualSeverity,
      note: "",
    };
    setManualDrafts((current) => [...current, draft]);
    setSelectedDraftId(draft.draft_id);
  }

  async function saveManualDrafts(image: Img) {
    if (!data) return;
    const imageDrafts = draftsByImage[image.image_id] || [];
    if (!imageDrafts.length) return;
    setBusy(true);
    setError("");
    try {
      for (const draft of imageDrafts) {
        await createManualDamage(
          authorizedFetch,
          {
            baseImageId: image.image_id,
            bboxNorm: draft.bbox_norm,
            damageType: draft.damage_type,
            inspectionId: data.inspection_id,
            note: draft.note || undefined,
            severityHint: draft.severity_hint,
          },
          tg?.initData,
        );
      }
      setManualDrafts((current) => current.filter((draft) => draft.image_id !== image.image_id));
      setSelectedDraftId(null);
      setManualModeByImage((current) => ({ ...current, [image.image_id]: false }));
      await loadInspection(data.inspection_id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось сохранить добавленные вручную повреждения.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  async function attachCloseup(
    imageId: string,
    file: File,
    damageRefType?: "predicted_review" | "manual",
    damageRefId?: string,
  ) {
    const isImageLevel = !damageRefType || !damageRefId;
    if (isImageLevel) {
      setUploadingImageCloseupFor(imageId);
    } else {
      setUploadingCloseupFor(damageRefId);
    }
    setError("");
    try {
      await attachInspectionCloseup(authorizedFetch, file, imageId, tg?.initData, damageRefType, damageRefId);
      if (data) await loadInspection(data.inspection_id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось загрузить крупный план.";
      setError(message);
    } finally {
      if (isImageLevel) {
        setUploadingImageCloseupFor(null);
      } else {
        setUploadingCloseupFor(null);
      }
    }
  }

  async function attachExtraPhoto(file: File, comment: string) {
    if (!data) return;
    const previewUrl = URL.createObjectURL(file);
    const previousPreview = extraPhotoPreview;
    setUploadingExtraPhoto(true);
    setExtraPhotoPreview({ url: previewUrl, status: "uploading" });
    setError("");
    try {
      await attachInspectionExtraPhoto(authorizedFetch, comment, file, data.inspection_id, tg?.initData);
      await loadInspection(data.inspection_id);
      setPhotosReviewConfirmed(false);
      setExtraPhotoComment("");
      setExtraPhotoPreview(null);
      URL.revokeObjectURL(previewUrl);
      if (previousPreview?.url && previousPreview.url !== previewUrl) {
        URL.revokeObjectURL(previousPreview.url);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось загрузить дополнительное фото.";
      setError(message);
      setExtraPhotoPreview({ url: previewUrl, status: "error" });
      if (previousPreview?.url && previousPreview.url !== previewUrl) {
        URL.revokeObjectURL(previousPreview.url);
      }
    } finally {
      setUploadingExtraPhoto(false);
    }
  }

  async function finalizeInspection() {
    if (!data) return;
    if (!photosReviewConfirmed) {
      setError("Перед завершением подтвердите, что проверили все фото.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await finalizeInspectionSession(authorizedFetch, data.inspection_id, tg?.initData);
      setFinalizeResult(result);
      setData((current) => (current ? { ...current, status: result.status } : current));
      const botPayload = JSON.stringify({
        action: "inspection_finalized",
        canonical_damage_count: result.canonical_damage_count,
        comparison_status: result.comparison_status,
        inspection_id: result.inspection_id,
      });
      tg?.sendData?.(botPayload);
      window.setTimeout(() => {
        tg?.sendData?.(botPayload);
      }, 350);
      if (tg?.close) {
        window.setTimeout(() => tg.close(), 1600);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось завершить осмотр.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  function onViewerTap(image: Img, event: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>) {
    if (!manualModeByImage[image.image_id]) return;
    const viewer = viewerRefs.current[image.image_id];
    if (!viewer) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest("[data-draft-control='true']")) return;
    const rect = viewer.getBoundingClientRect();
    const point = "touches" in event ? event.touches[0] : event;
    const x = clamp((point.clientX - rect.left) / rect.width, 0.05, 0.95);
    const y = clamp((point.clientY - rect.top) / rect.height, 0.05, 0.95);
    queueManualDamage(image.image_id, x, y);
  }

  function renderCloseups(closeups?: Closeup[]) {
    if (!closeups?.length) return null;
    return (
      <div className="closeups">
        {closeups.map((closeup) => (
          <a key={closeup.image_id} href={closeup.raw_url} target="_blank" rel="noreferrer">
            <img src={closeup.raw_url} alt="Close-up" loading="lazy" />
          </a>
        ))}
      </div>
    );
  }

  function renderExtraPhotoCards(closeups?: Closeup[]) {
    if (!closeups?.length) return null;
    return (
      <div className="slot-grid">
        {closeups.map((closeup, index) => (
          <div key={closeup.image_id} className="capture-card slot-card">
            <div className="slot-meta">
              <div className="slot-title-row">
                <strong>{`Доп. фото ${index + 1}`}</strong>
                <div className="slot-status done">Загружено</div>
              </div>
              <a className="upload-btn" href={closeup.raw_url} target="_blank" rel="noreferrer">
                Открыть
              </a>
            </div>
            <div className="slot-thumb">
              <img src={closeup.raw_url} alt={`Доп. фото ${index + 1}`} loading="lazy" />
            </div>
            {closeup.comment ? (
              <div className="muted" style={{ marginTop: 10 }}>{closeup.comment}</div>
            ) : (
              <div className="muted" style={{ marginTop: 10 }}>Комментарий не добавлен.</div>
            )}
          </div>
        ))}
      </div>
    );
  }

  function renderGeometryOverlay(image: Img) {
    const polygons = [
      ...image.predicted_damages.map((damage) => ({
        key: `pred-${damage.damage_id}`,
        points: polygonToSvgPoints(damage.polygon_json, damage.bbox_norm),
        stroke: DAMAGE_COLORS[damage.damage_type] || "#15202B",
        fill: hexToRgba(DAMAGE_COLORS[damage.damage_type] || "#15202B", damage.polygon_json && damage.polygon_json.length > 4 ? 0.22 : 0.12),
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

  function renderPredictedDamage(image: Img, damage: Damage) {
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
      <div key={damage.damage_id} className="damage-card">
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

  function renderManualDamage(image: Img, manualDamage: ManualDamage) {
    const color = DAMAGE_COLORS[manualDamage.damage_type] || "#15202B";
    return (
      <div key={manualDamage.manual_damage_id} className="damage-card">
        <div className="damage-head">
          <div className="damage-title">
            <div className="damage-icon" style={{ background: color }}>
              РУЧ
            </div>
            <div>
              <strong>{DAMAGE_LABELS[manualDamage.damage_type] || manualDamage.damage_type}</strong>
              <span>Размер: {manualDamage.severity_hint || "не указан"}</span>
            </div>
          </div>
          <div className="review-pill" style={{ background: "#15202B" }}>
            Вручную
          </div>
        </div>
        {manualDamage.note ? <div className="muted" style={{ marginTop: 10 }}>{manualDamage.note}</div> : null}
        <div className="closeup-row" style={{ marginTop: 12 }}>
          <label className="ghost-btn">
            {uploadingCloseupFor === manualDamage.manual_damage_id ? "Загружаем..." : "Добавить крупный план"}
            <input
              hidden
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  void attachCloseup(image.image_id, file, "manual", manualDamage.manual_damage_id);
                }
                event.currentTarget.value = "";
              }}
            />
          </label>
        </div>
        {renderCloseups(manualDamage.closeups)}
      </div>
    );
  }

  function removeDraft(draftId: string) {
    setManualDrafts((current) => current.filter((draft) => draft.draft_id !== draftId));
    setSelectedDraftId((current) => (current === draftId ? null : current));
  }

  function updateDraft(draftId: string, patch: Partial<DraftManualDamage>) {
    setManualDrafts((current) =>
      current.map((draft) => (draft.draft_id === draftId ? { ...draft, ...patch } : draft)),
    );
  }

  const userName =
    tg?.initDataUnsafe?.user?.first_name ||
    tg?.initDataUnsafe?.user?.username ||
    "Водитель";

  const nextSlot = data?.required_slots.find((slot) => !data.accepted_slots.includes(slot)) || SLOT_ORDER[0];
  const nextImage = nextSlot ? imagesBySlot[nextSlot] : undefined;
  const nextPreview = nextSlot ? localPreviews[nextSlot] : undefined;
  const remainingSlots = data?.required_slots.filter((slot) => !data.accepted_slots.includes(slot)) || [];
  const vehicleBadge = data?.vehicle_plate || data?.vehicle_id || "Авто";
  const latestExtraPhotoUrl = extraPhotos.length ? extraPhotos[extraPhotos.length - 1].raw_url : "";
  const extraPreviewUrl = extraPhotoPreview?.url || latestExtraPhotoUrl;
  const displayError = authError || error;

  return (
    <div className="app-shell">
      <style>{miniappStyles}</style>
      <section className="hero">
        <div className="hero-badge">{captureComplete ? "Режим проверки" : "Обязательные фото"}</div>
        <h1 className="hero-title">Добрый день, {userName}</h1>
        <p className="hero-subtitle">{data?.vehicle_title ? `${data.vehicle_title} · ${vehicleBadge}` : `Автомобиль ${vehicleBadge}`}</p>
      </section>

      <section className="sheet">
        <div className="handle" />
        {data ? (
          <div className="progress-card">
              <div className="row" style={{ alignItems: "flex-start" }}>
                <div>
                  <strong style={{ fontSize: 18 }}>
                    {captureComplete ? "Все обязательные кадры готовы" : `Прогресс: ${acceptedCount} из 4`}
                  </strong>
                <div className="progress-note">
                  {captureComplete
                    ? optionalPhotoStage
                      ? "Можно добавить доп. фото и подтвердить набор перед анализом."
                      : photoSetConfirmed
                        ? "Набор фото подтверждён. Доп. фото заблокированы, можно запускать анализ."
                        : inferenceRunning
                          ? "Анализ уже запущен. Подождите, пока загрузятся результаты."
                          : "Можно перейти к проверке найденных повреждений."
                    : `Осталось снять: ${remainingSlots.map((slot) => SLOT_LABELS[slot]).join(", ")}`}
                </div>
              </div>
              <div className={`slot-status ${captureComplete ? "done" : ""}`}>
                {captureComplete ? (photoSetConfirmed ? "Подтверждено" : "Готово") : "Обязательные фото"}
              </div>
              </div>
          </div>
        ) : null}
        {displayError ? (
          <div className="notice error">
            <strong>Что-то пошло не так</strong>
            <p>{displayError}</p>
          </div>
        ) : null}
        {finalizeResult ? (
          <div className="notice success">
            <strong>Осмотр завершён</strong>
            <p>
              Сохранено {finalizeResult.canonical_damage_count} канонических повреждений.
              {finalizeResult.comparison_status
                ? ` Статус сравнения: ${formatStatus(finalizeResult.comparison_status)}.`
                : ""}
            </p>
          </div>
        ) : null}
        {busy ? (
          <div className="notice">
            <strong>Обновляем состояние</strong>
            <p>Подождите пару секунд. Проверяем фото и синхронизируем результаты.</p>
          </div>
        ) : null}

        {!authReady ? <div className="loading">Подтверждаем сессию Telegram…</div> : null}
        {loading && !data && authReady ? <div className="loading">Загружаем осмотр…</div> : null}

        {data && !captureComplete ? (
          <>
            <div className="capture-card capture-hero">
              <div className="capture-head">
                <div>
                  <h2>{SLOT_LABELS[nextSlot]}</h2>
                  <div className="muted" style={{ marginTop: 8 }}>Обязательный ракурс для завершения осмотра</div>
                </div>
              </div>
              <div className={`capture-preview ${nextPreview?.status === "uploading" ? "is-pending" : ""} ${nextPreview?.status === "rejected" ? "is-rejected" : ""} ${nextPreview?.status === "error" ? "is-error" : ""}`}>
                {nextImage?.raw_url || nextPreview?.url ? (
                  <img src={nextImage?.raw_url || nextPreview?.url} alt={SLOT_LABELS[nextSlot]} loading="lazy" />
                ) : (
                  <div className="capture-empty">
                    <div className="capture-empty-inner">
                      <div className="capture-icon">+</div>
                      <strong>{SLOT_LABELS[nextSlot]}</strong>
                      <div className="muted">{SLOT_TIPS[nextSlot]}</div>
                    </div>
                  </div>
                )}
              </div>
              <div className="capture-foot">
                {nextPreview ? (
                  <div className={`capture-state ${nextPreview.status}`}>
                    {nextPreview.status === "uploading"
                      ? "Ждём проверку модели"
                      : nextPreview.status === "rejected"
                        ? slotFeedback[nextSlot] || "Фото отклонено"
                        : slotFeedback[nextSlot] || "Не удалось завершить загрузку"}
                  </div>
                ) : slotFeedback[nextSlot] ? (
                  <div className="capture-state">{slotFeedback[nextSlot]}</div>
                ) : null}
                <label className="primary-btn">
                  {uploadingSlot === nextSlot ? "Проверяем фото..." : nextImage || nextPreview ? "Переснять" : "Сделать фото"}
                  <input
                    hidden
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        void uploadRequired(nextSlot, file, "hero");
                      }
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
              </div>
            </div>

            <div className="section-title">
              <h3>Все обязательные кадры</h3>
              <span>Можно переснимать в любой момент</span>
            </div>
            <div className="slot-grid">
              {SLOT_ORDER.map((slot) => {
                const image = imagesBySlot[slot];
                const preview = localPreviews[slot];
                const slotPreview = preview?.source === "slot" ? preview : undefined;
                const done = data.accepted_slots.includes(slot);
                const rejected = !!slotFeedback[slot] && !done;
                return (
                  <div key={slot} className={`capture-card slot-card ${slot === nextSlot ? "active" : ""} ${rejected ? "rejected" : ""}`}>
                    <div className="slot-meta">
                      <div>
                        <div className="slot-title-row">
                          <strong>{SLOT_LABELS[slot]}</strong>
                          <div className={`slot-status ${done ? "done" : rejected ? "rejected" : ""}`}>
                            {done ? "Принято" : rejected ? "Нужно переснять" : "Осталось"}
                          </div>
                        </div>
                      </div>
                      <label className="upload-btn" style={{ whiteSpace: "nowrap" }}>
                        {uploadingSlot === slot ? "Проверяем..." : image || slotPreview ? "Переснять" : "Сделать фото"}
                        <input
                          hidden
                          type="file"
                          accept="image/*"
                          capture="environment"
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) {
                              void uploadRequired(slot, file, "slot");
                            }
                            event.currentTarget.value = "";
                          }}
                        />
                      </label>
                    </div>
                    <div className={`slot-thumb ${slotPreview?.status === "rejected" ? "is-rejected" : ""} ${slotPreview?.status === "error" ? "is-error" : ""}`}>
                      {image?.raw_url || slotPreview?.url ? (
                        <img src={image?.raw_url || slotPreview?.url} alt={SLOT_LABELS[slot]} loading="lazy" />
                      ) : (
                        SLOT_TIPS[slot]
                      )}
                    </div>
                    {slotFeedback[slot] ? <div className="muted" style={{ marginTop: 10 }}>{slotFeedback[slot]}</div> : null}
                  </div>
                );
              })}
            </div>

          </>
        ) : null}

        {data && captureComplete ? (
          <>
            {waitingForInference ? (
              <>
                <div className="summary-grid">
                  <div className="summary-card">
                    <strong>{totalUploadedPhotos}</strong>
                    <span>Загружено фото</span>
                  </div>
                </div>
                <div className="section-title">
                  <h3>Подготовка к анализу</h3>
                  <span>
                    {optionalPhotoStage
                      ? "До подтверждения можно переснять ракурс и добавить доп. фото"
                      : photoSetConfirmed
                        ? "Набор фото зафиксирован, теперь можно запускать анализ"
                        : "Дождитесь завершения анализа"}
                  </span>
                </div>
                <div className="capture-card capture-hero" style={{ marginBottom: 14 }}>
                  <div className="capture-head" style={{ marginBottom: 10 }}>
                    <div>
                      <h2 style={{ fontSize: 26 }}>Доп. фото</h2>
                      <div className="muted" style={{ marginTop: 8 }}>
                        Добавьте дополнительные фото перед запуском анализа.
                      </div>
                    </div>
                  </div>
                  <div className={`capture-preview ${extraPhotoPreview?.status === "uploading" ? "is-pending" : ""} ${extraPhotoPreview?.status === "error" ? "is-error" : ""}`}>
                    {extraPreviewUrl ? (
                      <img src={extraPreviewUrl} alt="Доп. фото" loading="lazy" />
                    ) : (
                      <div className="capture-empty">
                        <div className="capture-empty-inner">
                          <div className="capture-icon">+</div>
                          <strong>Доп. фото</strong>
                          <div className="muted">Снимите дополнительный кадр крупным планом.</div>
                        </div>
                      </div>
                    )}
                  </div>
                  <textarea
                    className="extra-comment-input"
                    value={extraPhotoComment}
                    onChange={(event) => setExtraPhotoComment(event.target.value)}
                    placeholder="Комментарий к доп. фото (обязательно). Например: «Крупный план скола на заднем бампере»."
                    disabled={!optionalPhotoStage || busy || uploadingExtraPhoto}
                  />
                  <div className="capture-foot">
                    {extraPhotoPreview ? (
                      <div className={`capture-state ${extraPhotoPreview.status === "uploading" ? "pending" : "error"}`}>
                        {extraPhotoPreview.status === "uploading" ? "Загружаем дополнительное фото..." : "Не удалось загрузить дополнительное фото"}
                      </div>
                    ) : null}
                    <label className="primary-btn" style={{ opacity: optionalPhotoStage ? 1 : 0.6 }}>
                      {uploadingExtraPhoto ? "Загружаем..." : extraPhotos.length ? "Добавить ещё доп. фото" : "Добавить доп. фото"}
                      <input
                        hidden
                        type="file"
                        accept="image/*"
                        capture="environment"
                        disabled={!optionalPhotoStage || busy}
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) {
                            const comment = extraPhotoComment.trim();
                            if (!comment) {
                              setError("Добавьте комментарий к доп. фото перед загрузкой.");
                              event.currentTarget.value = "";
                              return;
                            }
                            void attachExtraPhoto(file, comment);
                          }
                          event.currentTarget.value = "";
                        }}
                      />
                    </label>
                    <div className="slot-status done" style={{ marginLeft: "auto" }}>
                      {extraPhotos.length} доп. фото
                    </div>
                  </div>
                  <div className="muted" style={{ marginTop: 10 }}>
                    {optionalPhotoStage
                      ? "После подтверждения набора фото добавление доп. кадров будет закрыто."
                      : "Новые доп. фото уже заблокированы. Если нужно изменить набор, переснимите обязательный ракурс."}
                  </div>
                </div>
                {extraPhotos.length ? (
                  renderExtraPhotoCards(extraPhotos)
                ) : (
                  <div className="muted" style={{ marginTop: 8, marginBottom: 16 }}>Пока нет дополнительных фото.</div>
                )}
                <div className="review-stack">
                  {orderedImages.map((image) => {
                    return (
                      <div key={image.image_id} className="viewer-card">
                        <div className="viewer-head">
                          <strong>{SLOT_LABELS[image.slot_code] || image.slot_code}</strong>
                          <div className="slot-status done">Принято</div>
                        </div>
                        <div className="top-actions" style={{ marginBottom: 12 }}>
                          <label className="upload-btn">
                            {uploadingSlot === image.slot_code ? "Проверяем..." : "Переснять ракурс"}
                            <input
                              hidden
                              type="file"
                              accept="image/*"
                              capture="environment"
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) {
                                  void uploadRequired(image.slot_code, file, "slot");
                                }
                                event.currentTarget.value = "";
                              }}
                            />
                          </label>
                        </div>
                        <div className="viewer">
                          <img src={image.raw_url} alt={SLOT_LABELS[image.slot_code] || image.slot_code} draggable={false} />
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="notice" style={{ marginTop: 16 }}>
                  <strong>{optionalPhotoStage ? "Подтвердите набор фото" : "Запуск анализа повреждений"}</strong>
                  <p>
                    {optionalPhotoStage
                      ? "Подтвердите, что вы проверили все 4 обязательных ракурса и загрузили нужные доп. фото."
                      : photoSetConfirmed
                        ? "Набор фото подтверждён. Доп. фото заблокированы, можно запускать сегментацию."
                        : "Анализ уже выполняется. Подождите, пока результаты загрузятся на экран."}
                  </p>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                    {optionalPhotoStage ? (
                      <button
                        className="primary-btn"
                        disabled={busy}
                        onClick={() => void confirmPhotoSet()}
                      >
                        Подтвердить набор фото
                      </button>
                    ) : null}
                    {photoSetConfirmed ? (
                      <button
                        className="primary-btn"
                        disabled={busy}
                        onClick={() => void runInference(data.inspection_id)}
                      >
                        Запустить анализ повреждений
                      </button>
                    ) : null}
                  </div>
                </div>
              </>
            ) : null}

            {inferenceReady ? (
              <>
                <div className="section-title">
                  <h3>Проверка перед сдачей</h3>
                  <span>Можно переснять ракурс и перепроверить анализ</span>
                </div>
                <div className="review-stack">
                  {orderedImages.map((image) => {
                    const autoConfirmed = image.predicted_damages.filter((damage) => damage.review_status === "confirmed").length;
                    const autoUncertain = image.predicted_damages.filter((damage) => damage.review_status === "uncertain").length;
                    const autoRejected = image.predicted_damages.filter((damage) => damage.review_status === "rejected").length;
                    return (
                      <div key={image.image_id} className="viewer-card review-view-card">
                        <div className="viewer-head">
                          <div>
                            <strong>{SLOT_LABELS[image.slot_code] || image.slot_code}</strong>
                            <div className="muted">
                              Автопринято: {autoConfirmed} · На админ-проверку: {autoUncertain} · Отфильтровано: {autoRejected}
                            </div>
                          </div>
                          <div className="top-actions">
                            <div className="slot-status done">Готово</div>
                          </div>
                        </div>
                        <div className="top-actions" style={{ marginBottom: 12 }}>
                          <label className="upload-btn">
                            {uploadingSlot === image.slot_code ? "Проверяем..." : "Переснять ракурс"}
                            <input
                              hidden
                              type="file"
                              accept="image/*"
                              capture="environment"
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) {
                                  void uploadRequired(image.slot_code, file, "slot");
                                }
                                event.currentTarget.value = "";
                              }}
                            />
                          </label>
                        </div>
                        <div className="viewer">
                          <img src={image.raw_url} alt={SLOT_LABELS[image.slot_code] || image.slot_code} draggable={false} />
                          {image.overlay_url ? <img className="overlay" src={image.overlay_url} alt="Damage overlay" /> : null}
                          {renderGeometryOverlay(image)}
                        </div>
                        {image.predicted_damages.length ? (
                          <div className="damage-stack" style={{ marginTop: 12 }}>
                            {image.predicted_damages.map((damage) => renderPredictedDamage(image, damage))}
                          </div>
                        ) : (
                          <div className="muted" style={{ marginTop: 12 }}>На этом ракурсе повреждения не найдены.</div>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="section-title">
                  <h3>Дополнительные фото</h3>
                  <span>{extraPhotos.length} шт.</span>
                </div>
                {extraPhotos.length ? (
                  renderExtraPhotoCards(extraPhotos)
                ) : (
                  <div className="muted">Дополнительные фото не добавлялись.</div>
                )}

                <div className="notice" style={{ marginTop: 16 }}>
                  <strong>Финальная проверка перед сдачей</strong>
                  <p>Проверьте все 4 ракурса и доп. фото. После подтверждения можно завершить осмотр.</p>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                    <button
                      className={photosReviewConfirmed ? "secondary-btn" : "ghost-btn"}
                      onClick={() => setPhotosReviewConfirmed((value) => !value)}
                    >
                      {photosReviewConfirmed ? "Проверка подтверждена" : "Я проверил(а) все фото"}
                    </button>
                    <button
                      className="primary-btn"
                      disabled={!photosReviewConfirmed || busy}
                      onClick={() => void finalizeInspection()}
                    >
                      Завершить осмотр
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
