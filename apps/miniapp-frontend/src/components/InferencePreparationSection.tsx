import React from "react";

import { SLOT_LABELS, type Closeup, type ExtraPhotoPreview, type Img } from "../domain";
import { ExtraPhotoGrid } from "./ExtraPhotoGrid";

type InferencePreparationSectionProps = {
  busy: boolean;
  extraPhotoComment: string;
  extraPhotoPreview: ExtraPhotoPreview | null;
  extraPhotos: Closeup[];
  extraPreviewUrl: string;
  onAttachExtraPhoto: (file: File) => void;
  onConfirmPhotoSet: () => void;
  onExtraPhotoCommentChange: (value: string) => void;
  onRunInference: () => void;
  onUploadRequired: (slot: string, file: File) => void;
  optionalPhotoStage: boolean;
  orderedImages: Img[];
  photoSetConfirmed: boolean;
  totalUploadedPhotos: number;
  uploadingExtraPhoto: boolean;
  uploadingSlot: string | null;
};

export function InferencePreparationSection({
  busy,
  extraPhotoComment,
  extraPhotoPreview,
  extraPhotos,
  extraPreviewUrl,
  onAttachExtraPhoto,
  onConfirmPhotoSet,
  onExtraPhotoCommentChange,
  onRunInference,
  onUploadRequired,
  optionalPhotoStage,
  orderedImages,
  photoSetConfirmed,
  totalUploadedPhotos,
  uploadingExtraPhoto,
  uploadingSlot,
}: InferencePreparationSectionProps) {
  return (
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
          onChange={(event) => onExtraPhotoCommentChange(event.target.value)}
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
                  onAttachExtraPhoto(file);
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
        <ExtraPhotoGrid closeups={extraPhotos} />
      ) : (
        <div className="muted" style={{ marginTop: 8, marginBottom: 16 }}>Пока нет дополнительных фото.</div>
      )}
      <div className="review-stack">
        {orderedImages.map((image) => (
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
                      onUploadRequired(image.slot_code, file);
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
        ))}
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
            <button className="primary-btn" disabled={busy} onClick={onConfirmPhotoSet}>
              Подтвердить набор фото
            </button>
          ) : null}
          {photoSetConfirmed ? (
            <button className="primary-btn" disabled={busy} onClick={onRunInference}>
              Запустить анализ повреждений
            </button>
          ) : null}
        </div>
      </div>
    </>
  );
}
