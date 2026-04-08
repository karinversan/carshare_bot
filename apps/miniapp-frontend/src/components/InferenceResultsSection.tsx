import React from "react";

import { SLOT_LABELS, type Closeup, type Img } from "../domain";
import { ExtraPhotoGrid } from "./ExtraPhotoGrid";
import { GeometryOverlay } from "./GeometryOverlay";
import { PredictedDamageCard } from "./PredictedDamageCard";

type InferenceResultsSectionProps = {
  busy: boolean;
  extraPhotos: Closeup[];
  onFinalizeInspection: () => void;
  onTogglePhotosReviewConfirmed: () => void;
  onUploadRequired: (slot: string, file: File) => void;
  orderedImages: Img[];
  photosReviewConfirmed: boolean;
  uploadingSlot: string | null;
};

export function InferenceResultsSection({
  busy,
  extraPhotos,
  onFinalizeInspection,
  onTogglePhotosReviewConfirmed,
  onUploadRequired,
  orderedImages,
  photosReviewConfirmed,
  uploadingSlot,
}: InferenceResultsSectionProps) {
  return (
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
                        onUploadRequired(image.slot_code, file);
                      }
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
              </div>
              <div className="viewer">
                <img src={image.raw_url} alt={SLOT_LABELS[image.slot_code] || image.slot_code} draggable={false} />
                {image.overlay_url ? <img className="overlay" src={image.overlay_url} alt="Damage overlay" /> : null}
                <GeometryOverlay image={image} />
              </div>
              {image.predicted_damages.length ? (
                <div className="damage-stack" style={{ marginTop: 12 }}>
                  {image.predicted_damages.map((damage) => (
                    <PredictedDamageCard key={damage.damage_id} damage={damage} />
                  ))}
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
        <ExtraPhotoGrid closeups={extraPhotos} />
      ) : (
        <div className="muted">Дополнительные фото не добавлялись.</div>
      )}

      <div className="notice" style={{ marginTop: 16 }}>
        <strong>Финальная проверка перед сдачей</strong>
        <p>Проверьте все 4 ракурса и доп. фото. После подтверждения можно завершить осмотр.</p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
          <button
            className={photosReviewConfirmed ? "secondary-btn" : "ghost-btn"}
            onClick={onTogglePhotosReviewConfirmed}
          >
            {photosReviewConfirmed ? "Проверка подтверждена" : "Я проверил(а) все фото"}
          </button>
          <button
            className="primary-btn"
            disabled={!photosReviewConfirmed || busy}
            onClick={onFinalizeInspection}
          >
            Завершить осмотр
          </button>
        </div>
      </div>
    </>
  );
}
