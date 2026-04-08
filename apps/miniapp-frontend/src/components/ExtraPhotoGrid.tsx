import React from "react";

import { type Closeup } from "../domain";

type ExtraPhotoGridProps = {
  closeups?: Closeup[];
};

export function ExtraPhotoGrid({ closeups }: ExtraPhotoGridProps) {
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
