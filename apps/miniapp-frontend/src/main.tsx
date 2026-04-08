import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";

import {
  attachInspectionExtraPhoto,
  confirmInspectionPhotoSet,
  fetchInspectionData,
  finalizeInspectionSession,
  InspectionClosedError,
  runDamageInference,
  runInitialInspectionChecks,
  uploadRequiredView,
} from "./api";
import { CaptureProgressCard } from "./components/CaptureProgressCard";
import { InferencePreparationSection } from "./components/InferencePreparationSection";
import { InferenceResultsSection } from "./components/InferenceResultsSection";
import { RequiredCaptureSection } from "./components/RequiredCaptureSection";
import {
  SLOT_ORDER,
  type ExtraPhotoPreview,
  type FinalizeResult,
  type Img,
  type InspectionData,
  type LocalPreview,
} from "./domain";
import { miniappStyles } from "./styles";
import { tg } from "./telegram";
import { useTelegramAuth } from "./useTelegramAuth";
import { formatStatus, humanizeRejectionReason } from "./utils";

function App() {
  const params = new URLSearchParams(window.location.search);
  const [inspectionId] = useState(params.get("inspection_id") || "");
  const { authError, authReady, authToken, authorizedFetch } = useTelegramAuth();
  const [data, setData] = useState<InspectionData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [finalizeResult, setFinalizeResult] = useState<FinalizeResult | null>(null);
  const [photosReviewConfirmed, setPhotosReviewConfirmed] = useState(false);
  const [slotFeedback, setSlotFeedback] = useState<Record<string, string>>({});
  const [localPreviews, setLocalPreviews] = useState<Record<string, LocalPreview | undefined>>({});
  const [uploadingSlot, setUploadingSlot] = useState<string | null>(null);
  const [uploadingExtraPhoto, setUploadingExtraPhoto] = useState(false);
  const [extraPhotoComment, setExtraPhotoComment] = useState("");
  const [extraPhotoPreview, setExtraPhotoPreview] = useState<ExtraPhotoPreview | null>(null);
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

  function handleRequiredUpload(slot: string, file: File, source: "hero" | "slot") {
    void uploadRequired(slot, file, source);
  }

  function handleSlotUpload(slot: string, file: File) {
    void uploadRequired(slot, file, "slot");
  }

  function handleExtraPhotoSelection(file: File) {
    const comment = extraPhotoComment.trim();
    if (!comment) {
      setError("Добавьте комментарий к доп. фото перед загрузкой.");
      return;
    }

    void attachExtraPhoto(file, comment);
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
          <CaptureProgressCard
            acceptedCount={acceptedCount}
            captureComplete={captureComplete}
            inferenceRunning={inferenceRunning}
            optionalPhotoStage={optionalPhotoStage}
            photoSetConfirmed={photoSetConfirmed}
            remainingSlots={remainingSlots}
          />
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
          <RequiredCaptureSection
            acceptedSlots={data.accepted_slots}
            imagesBySlot={imagesBySlot}
            localPreviews={localPreviews}
            nextImage={nextImage}
            nextPreview={nextPreview}
            nextSlot={nextSlot}
            onUploadRequired={handleRequiredUpload}
            slotFeedback={slotFeedback}
            uploadingSlot={uploadingSlot}
          />
        ) : null}

        {data && captureComplete ? (
          <>
            {waitingForInference ? (
              <InferencePreparationSection
                busy={busy}
                extraPhotoComment={extraPhotoComment}
                extraPhotoPreview={extraPhotoPreview}
                extraPhotos={extraPhotos}
                extraPreviewUrl={extraPreviewUrl}
                onAttachExtraPhoto={handleExtraPhotoSelection}
                onConfirmPhotoSet={() => void confirmPhotoSet()}
                onExtraPhotoCommentChange={setExtraPhotoComment}
                onRunInference={() => void runInference(data.inspection_id)}
                onUploadRequired={handleSlotUpload}
                optionalPhotoStage={optionalPhotoStage}
                orderedImages={orderedImages}
                photoSetConfirmed={photoSetConfirmed}
                totalUploadedPhotos={totalUploadedPhotos}
                uploadingExtraPhoto={uploadingExtraPhoto}
                uploadingSlot={uploadingSlot}
              />
            ) : null}

            {inferenceReady ? (
              <InferenceResultsSection
                busy={busy}
                extraPhotos={extraPhotos}
                onFinalizeInspection={() => void finalizeInspection()}
                onTogglePhotosReviewConfirmed={() => setPhotosReviewConfirmed((value) => !value)}
                onUploadRequired={handleSlotUpload}
                orderedImages={orderedImages}
                photosReviewConfirmed={photosReviewConfirmed}
                uploadingSlot={uploadingSlot}
              />
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
