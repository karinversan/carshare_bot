import React from "react";

import { SLOT_LABELS } from "../domain";

type CaptureProgressCardProps = {
  acceptedCount: number;
  captureComplete: boolean;
  inferenceRunning: boolean;
  optionalPhotoStage: boolean;
  photoSetConfirmed: boolean;
  remainingSlots: string[];
};

export function CaptureProgressCard({
  acceptedCount,
  captureComplete,
  inferenceRunning,
  optionalPhotoStage,
  photoSetConfirmed,
  remainingSlots,
}: CaptureProgressCardProps) {
  const progressNote = captureComplete
    ? optionalPhotoStage
      ? "Можно добавить доп. фото и подтвердить набор перед анализом."
      : photoSetConfirmed
        ? "Набор фото подтверждён. Доп. фото заблокированы, можно запускать анализ."
        : inferenceRunning
          ? "Анализ уже запущен. Подождите, пока загрузятся результаты."
          : "Можно перейти к проверке найденных повреждений."
    : `Осталось снять: ${remainingSlots.map((slot) => SLOT_LABELS[slot]).join(", ")}`;

  return (
    <div className="progress-card">
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div>
          <strong style={{ fontSize: 18 }}>
            {captureComplete ? "Все обязательные кадры готовы" : `Прогресс: ${acceptedCount} из 4`}
          </strong>
          <div className="progress-note">{progressNote}</div>
        </div>
        <div className={`slot-status ${captureComplete ? "done" : ""}`}>
          {captureComplete ? (photoSetConfirmed ? "Подтверждено" : "Готово") : "Обязательные фото"}
        </div>
      </div>
    </div>
  );
}
