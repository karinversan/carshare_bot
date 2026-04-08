import React from "react";

import { SLOT_LABELS, SLOT_ORDER, SLOT_TIPS, type Img, type LocalPreview } from "../domain";

type RequiredCaptureSectionProps = {
  acceptedSlots: string[];
  imagesBySlot: Partial<Record<string, Img>>;
  localPreviews: Record<string, LocalPreview | undefined>;
  nextImage?: Img;
  nextPreview?: LocalPreview;
  nextSlot: string;
  onUploadRequired: (slot: string, file: File, source: "hero" | "slot") => void;
  slotFeedback: Record<string, string>;
  uploadingSlot: string | null;
};

export function RequiredCaptureSection({
  acceptedSlots,
  imagesBySlot,
  localPreviews,
  nextImage,
  nextPreview,
  nextSlot,
  onUploadRequired,
  slotFeedback,
  uploadingSlot,
}: RequiredCaptureSectionProps) {
  return (
    <>
      <div className="capture-card capture-hero">
        <div className="capture-head">
          <div>
            <h2>{SLOT_LABELS[nextSlot]}</h2>
            <div className="muted" style={{ marginTop: 8 }}>Обязательный ракурс для завершения осмотра</div>
          </div>
        </div>
        <div
          className={`capture-preview ${nextPreview?.status === "uploading" ? "is-pending" : ""} ${nextPreview?.status === "rejected" ? "is-rejected" : ""} ${nextPreview?.status === "error" ? "is-error" : ""}`}
        >
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
                  onUploadRequired(nextSlot, file, "hero");
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
          const done = acceptedSlots.includes(slot);
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
                        onUploadRequired(slot, file, "slot");
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
  );
}
