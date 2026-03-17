import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string;
        initDataUnsafe: any;
        ready: () => void;
        expand: () => void;
        close: () => void;
        sendData: (value: string) => void;
        MainButton: {
          text: string;
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
          showProgress: (leaveActive?: boolean) => void;
          hideProgress: () => void;
        };
      };
    };
  }
}

const tg = window.Telegram?.WebApp;
const API = (import.meta as any).env.VITE_API_BASE_URL || `${window.location.origin}/api`;

type BBox = { x1: number; y1: number; x2: number; y2: number };
type Closeup = { image_id: string; slot_code?: string; raw_url: string; created_at?: string };
type Damage = {
  damage_id: string;
  damage_type: string;
  confidence: number;
  bbox_norm: BBox;
  review_status: string;
  review_id: string;
  review_note?: string;
  closeups?: Closeup[];
};
type ManualDamage = {
  manual_damage_id: string;
  damage_type: string;
  bbox_norm: BBox;
  severity_hint: string;
  note?: string | null;
  closeups?: Closeup[];
};
type DraftManualDamage = {
  draft_id: string;
  image_id: string;
  damage_type: (typeof DAMAGE_TYPES)[number];
  bbox_norm: BBox;
  severity_hint: (typeof SEVERITY)[number];
  note: string;
};
type LocalPreview = {
  url: string;
  status: "uploading" | "rejected" | "error";
  source: "hero" | "slot";
};
type Img = {
  image_id: string;
  slot_code: string;
  status: string;
  raw_url: string;
  overlay_url?: string;
  predicted_damages: Damage[];
  manual_damages: ManualDamage[];
  image_closeups?: Closeup[];
};
type InspectionData = {
  inspection_id: string;
  status: string;
  required_slots: string[];
  accepted_slots: string[];
  vehicle_id?: string | null;
  vehicle_plate?: string | null;
  vehicle_title?: string | null;
  images: Img[];
};
type FinalizeResult = {
  inspection_id: string;
  status: string;
  canonical_damage_count: number;
  comparison_id?: string | null;
  comparison_status?: string;
};

type ApiErrorDetail = {
  code?: string;
  status?: string;
  message?: string;
};

const SLOT_ORDER = ["front", "left_side", "right_side", "rear"];
const SLOT_LABELS: Record<string, string> = {
  front: "Перед",
  left_side: "Левый бок",
  right_side: "Правый бок",
  rear: "Зад",
};
const SLOT_TIPS: Record<string, string> = {
  front: "Покажите весь передний бампер, капот и фары целиком.",
  left_side: "Снимите весь левый бок: крылья, двери и пороги.",
  right_side: "Снимите весь правый бок: крылья, двери и пороги.",
  rear: "Покажите задний бампер, крышку багажника и фонари.",
};
const DAMAGE_LABELS: Record<string, string> = {
  scratch: "Царапина",
  dent: "Вмятина",
  crack: "Трещина",
  broken_part: "Сломанная деталь",
};
const DAMAGE_COLORS: Record<string, string> = {
  scratch: "#2DCB70",
  dent: "#13B5FF",
  crack: "#FF9F0A",
  broken_part: "#FF5C59",
};
const REVIEW_LABELS: Record<string, string> = {
  pending: "Ожидает",
  confirmed: "Подтверждено",
  rejected: "Отклонено",
  uncertain: "Неуверенно",
};

const AUTO_DECISION_LABELS: Record<string, string> = {
  confirmed: "Автопринято",
  uncertain: "Нужна проверка админа",
  rejected: "Отфильтровано",
  pending: "Ожидает",
};
const SEVERITY = ["small", "medium", "severe"] as const;
const DAMAGE_TYPES = ["scratch", "dent", "crack", "broken_part"] as const;

const css = `
  :root {
    color-scheme: light;
    --mint-1: #C4F5C6;
    --mint-2: #EAF6EE;
    --mint-3: #F7FBF8;
    --green-1: #87E28F;
    --green-2: #3ED76D;
    --green-3: #2CC55D;
    --bg: #EEF3EF;
    --card: #FFFFFF;
    --text: #152019;
    --muted: #708078;
    --border: rgba(21, 32, 25, 0.07);
    --shadow: 0 18px 42px rgba(34, 62, 40, 0.08);
    --sheet-shadow: 0 -20px 46px rgba(28, 48, 34, 0.08);
    --success: #2CC55D;
    --warning: #FF9F0A;
    --danger: #FF5C59;
    --blue: #4F7CFF;
    --space-1: 8px;
    --space-2: 12px;
    --space-3: 16px;
    --space-4: 20px;
    --space-5: 24px;
  }
  * { box-sizing: border-box; }
  html, body, #root {
    margin: 0;
    min-height: 100%;
    background: var(--bg);
    font-family: "SF Pro Display", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: var(--text);
  }
  body { padding: 0; }
  button, input, textarea, select { font: inherit; }
  button {
    border: 0;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    transform: none !important;
    box-shadow: none !important;
  }
  .app-shell {
    min-height: 100vh;
    padding-bottom: calc(20px + env(safe-area-inset-bottom));
    background:
      radial-gradient(circle at top left, rgba(115, 223, 129, 0.42), transparent 34%),
      linear-gradient(180deg, var(--mint-1) 0, var(--mint-2) 220px, var(--bg) 220px, var(--bg) 100%);
    max-width: 520px;
    margin: 0 auto;
    overflow-x: hidden;
  }
  .hero {
    padding: var(--space-5) var(--space-4) var(--space-3);
  }
  .hero-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.76);
    border: 1px solid rgba(255, 255, 255, 0.56);
    color: #1E3225;
    font-size: 12px;
    font-weight: 700;
    box-shadow: 0 10px 22px rgba(29, 52, 35, 0.07);
  }
  .hero-badge::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
  }
  .hero-title {
    margin: 0;
    font-size: 34px;
    line-height: 1.02;
    letter-spacing: -0.06em;
    max-width: 12ch;
  }
  .hero-subtitle {
    margin: 10px 0 0;
    color: var(--muted);
    font-size: 17px;
    line-height: 1.4;
  }
  .hero-feature {
    position: relative;
    overflow: hidden;
    border-radius: 28px;
    background: rgba(255, 255, 255, 0.88);
    box-shadow: 0 18px 38px rgba(31, 52, 35, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.58);
    padding: 12px;
  }
  .hero-feature-media {
    position: relative;
    aspect-ratio: 1.45 / 1;
    border-radius: 22px;
    overflow: hidden;
    background: linear-gradient(180deg, #F6FBF8, #E7F1EA);
    display: grid;
    place-items: center;
  }
  .hero-feature-media img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .hero-feature-media::after {
    content: "";
    position: absolute;
    inset: auto 18px 14px 18px;
    height: 64px;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(255,255,255,0), rgba(255,255,255,0.92));
    pointer-events: none;
  }
  .hero-feature-empty {
    padding: 24px;
    text-align: center;
    color: var(--muted);
  }
  .hero-feature-empty strong {
    display: block;
    color: var(--text);
    margin-bottom: 8px;
    font-size: 16px;
  }
  .hero-feature-badge {
    position: absolute;
    left: 16px;
    top: 16px;
    border-radius: 999px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.86);
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 20px rgba(31, 52, 35, 0.08);
    font-size: 12px;
    font-weight: 800;
  }
  .hero-feature-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 2px 0;
  }
  .hero-feature-foot strong {
    display: block;
    font-size: 16px;
    letter-spacing: -0.04em;
    margin-bottom: 4px;
  }
  .hero-feature-foot span {
    color: var(--muted);
    font-size: 12px;
    line-height: 1.4;
  }
  .hero-arrow {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: linear-gradient(135deg, #2CC55D, #59E76C);
    color: #fff;
    display: inline-grid;
    place-items: center;
    font-size: 18px;
    box-shadow: 0 12px 24px rgba(44, 197, 93, 0.22);
  }
  .sheet {
    margin-top: 12px;
    background: linear-gradient(180deg, rgba(247, 250, 248, 0.98) 0%, #F6FAF7 18%, #EEF3EF 100%);
    border-radius: 34px 34px 0 0;
    padding: 14px 16px calc(22px + env(safe-area-inset-bottom));
    box-shadow: var(--sheet-shadow);
    min-height: 0;
  }
  .handle {
    width: 54px;
    height: 6px;
    border-radius: 999px;
    background: rgba(24, 38, 27, 0.12);
    margin: 0 auto 14px;
  }
  .row {
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
  }
  .section-title {
    margin: 16px 0 12px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 10px 16px;
  }
  .section-title h3,
  .section-title h2 {
    margin: 0;
    font-size: 20px;
    letter-spacing: -0.04em;
  }
  .section-title span {
    color: var(--muted);
    font-size: 13px;
    font-weight: 600;
  }
  .notice {
    background: #fff;
    border-radius: 24px;
    border: 1px solid var(--border);
    padding: 14px 16px;
    margin-bottom: 14px;
    box-shadow: var(--shadow);
  }
  .notice strong {
    display: block;
    margin-bottom: 6px;
  }
  .notice p {
    margin: 0;
    line-height: 1.45;
    color: var(--muted);
  }
  .notice.warning { border-color: rgba(255, 159, 10, 0.22); background: #FFF9EF; }
  .notice.error { border-color: rgba(255, 92, 89, 0.24); background: #FFF1F0; }
  .notice.success { border-color: rgba(45, 203, 112, 0.24); background: #F3FFF8; }
  .progress-card,
  .capture-card,
  .viewer-card,
  .gallery-card,
  .summary-card,
  .damage-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 28px;
    box-shadow: var(--shadow);
  }
  .progress-card {
    padding: var(--space-4);
    margin-bottom: var(--space-3);
  }
  .progress-note {
    margin-top: 6px;
    color: var(--muted);
    line-height: 1.4;
  }
  .capture-hero {
    padding: var(--space-4);
    margin-bottom: var(--space-3);
  }
  .capture-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }
  .capture-head h2 {
    margin: 0;
    font-size: 30px;
    line-height: 1.08;
    letter-spacing: -0.05em;
  }
  .capture-preview {
    margin-top: 0;
    background: linear-gradient(180deg, #F8FBF9, #ECF4EE);
    border-radius: 26px;
    aspect-ratio: 1 / 1;
    overflow: hidden;
    position: relative;
    border: 1px dashed rgba(21, 32, 25, 0.12);
    display: grid;
    place-items: center;
  }
  .capture-preview.is-pending {
    border-color: rgba(255, 159, 10, 0.28);
  }
  .capture-preview.is-rejected,
  .slot-thumb.is-rejected {
    border-color: rgba(255, 92, 89, 0.28);
    background: linear-gradient(180deg, #FFF8F7, #FBECEA);
  }
  .capture-preview.is-error,
  .slot-thumb.is-error {
    border-color: rgba(255, 92, 89, 0.24);
  }
  .capture-preview img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: center;
    padding: 14px;
  }
  .capture-empty {
    width: 100%;
    height: 100%;
    padding: 0 24px;
    text-align: center;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .capture-empty-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    width: 100%;
    margin-top: 22px;
  }
  .capture-empty strong {
    display: block;
    color: var(--text);
    font-size: 18px;
    margin: 0;
  }
  .capture-empty .muted {
    max-width: 20ch;
    margin: 0;
    line-height: 1.32;
    font-size: 15px;
  }
  .capture-icon {
    width: 74px;
    height: 74px;
    border-radius: 24px;
    display: inline-grid;
    place-items: center;
    background: rgba(45, 203, 112, 0.12);
    color: #18A94D;
    font-size: 28px;
    margin-bottom: 0;
  }
  .upload-btn,
  .primary-btn,
  .secondary-btn,
  .ghost-btn,
  .decision-btn {
    border-radius: 18px;
    padding: 14px 16px;
    font-weight: 700;
    transition: transform 0.18s ease, opacity 0.18s ease, box-shadow 0.18s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    text-align: center;
  }
  .upload-btn:hover,
  .primary-btn:hover,
  .secondary-btn:hover,
  .ghost-btn:hover,
  .decision-btn:hover {
    transform: translateY(-1px);
  }
  .primary-btn {
    background: linear-gradient(135deg, #2DCB70, #57E36E);
    color: #fff;
    box-shadow: 0 12px 24px rgba(45, 203, 112, 0.28);
  }
  .secondary-btn {
    background: #1B2620;
    color: #fff;
  }
  .ghost-btn {
    background: rgba(27, 38, 32, 0.06);
    color: var(--text);
  }
  .upload-btn {
    background: rgba(44, 197, 93, 0.12);
    color: #16984A;
  }
  .capture-foot {
    margin-top: var(--space-3);
    display: grid;
    gap: var(--space-2);
  }
  .capture-foot .primary-btn {
    width: 100%;
  }
  .capture-state {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 700;
    color: var(--muted);
  }
  .capture-state::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(21, 32, 25, 0.18);
  }
  .capture-state.pending::before {
    background: var(--warning);
  }
  .capture-state.rejected::before,
  .capture-state.error::before {
    background: var(--danger);
  }
  .slot-meta {
    display: grid;
    gap: 12px;
  }
  .slot-title-row {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 10px;
    justify-content: space-between;
    width: 100%;
  }
  .slot-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .slot-card {
    padding: 14px;
    position: relative;
  }
  .slot-card.active {
    border-color: rgba(45, 203, 112, 0.38);
    box-shadow: 0 18px 34px rgba(45, 203, 112, 0.16);
  }
  .slot-card.rejected {
    border-color: rgba(255, 92, 89, 0.3);
  }
  .slot-thumb {
    aspect-ratio: 1 / 1;
    height: auto;
    border-radius: 18px;
    overflow: hidden;
    margin-top: 10px;
    background: linear-gradient(180deg, #F8FAFB, #E9EEF2);
    display: grid;
    place-items: center;
    color: var(--muted);
    font-size: 13px;
    border: 1px solid transparent;
    text-align: center;
    padding: 18px;
  }
  .slot-thumb img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: center;
    padding: 10px;
  }
  .slot-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 999px;
    padding: 8px 12px;
    background: rgba(21, 32, 43, 0.06);
    color: var(--muted);
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
    line-height: 1;
    width: fit-content;
  }
  .slot-status.done { background: rgba(45, 203, 112, 0.12); color: #16984A; }
  .slot-status.rejected { background: rgba(255, 92, 89, 0.12); color: #D54E4B; }
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .summary-card {
    padding: 16px;
    background: rgba(255,255,255,0.92);
  }
  .summary-card strong {
    display: block;
    font-size: 26px;
    line-height: 1;
    margin-bottom: 8px;
  }
  .summary-card span {
    font-size: 12px;
    color: var(--muted);
  }
  .review-stack {
    display: grid;
    gap: 14px;
  }
  .review-view-card {
    padding: 16px;
  }
  .gallery {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .gallery-card {
    overflow: hidden;
  }
  .gallery-card button {
    width: 100%;
    padding: 0;
    background: transparent;
    text-align: left;
  }
  .gallery-media {
    aspect-ratio: 1.1 / 1;
    position: relative;
    overflow: hidden;
  }
  .gallery-media img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .gallery-chip,
  .gallery-count {
    position: absolute;
    top: 12px;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 800;
    backdrop-filter: blur(10px);
  }
  .gallery-chip {
    left: 12px;
    background: rgba(255,255,255,0.88);
  }
  .gallery-count {
    right: 12px;
    background: rgba(21,32,43,0.74);
    color: #fff;
  }
  .gallery-body {
    padding: 14px;
  }
  .gallery-body strong {
    display: block;
    margin-bottom: 4px;
  }
  .gallery-body span {
    font-size: 12px;
    color: var(--muted);
  }
  .viewer-card {
    padding: 16px;
    margin-bottom: 16px;
  }
  .viewer-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    margin-bottom: 12px;
  }
  .viewer {
    position: relative;
    border-radius: 28px;
    overflow: hidden;
    background: #DEE9E1;
    aspect-ratio: 4 / 3;
    user-select: none;
  }
  .viewer img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .viewer .overlay {
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.94;
  }
  .bbox {
    position: absolute;
    border: 2px solid;
    border-radius: 16px;
    backdrop-filter: blur(4px);
  }
  .bbox-label {
    position: absolute;
    top: 8px;
    left: 8px;
    border-radius: 999px;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 800;
    color: #fff;
  }
  .bbox.draft {
    border-style: dashed;
    border-width: 3px;
  }
  .bbox.draft.selected {
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.88), 0 0 0 6px rgba(21, 32, 43, 0.26);
  }
  .bbox-delete {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 28px;
    height: 28px;
    border-radius: 999px;
    display: grid;
    place-items: center;
    background: rgba(21, 32, 43, 0.88);
    color: #fff;
    font-size: 16px;
    font-weight: 800;
    line-height: 1;
    box-shadow: 0 6px 16px rgba(15, 23, 42, 0.18);
  }
  .manual-panel {
    margin-bottom: 12px;
    border-radius: 22px;
    background: #F7FBF8;
    border: 1px solid var(--border);
    padding: 14px;
  }
  .manual-panel textarea {
    width: 100%;
    min-height: 72px;
    margin-top: 10px;
    border: 1px solid rgba(19, 32, 46, 0.12);
    border-radius: 14px;
    padding: 10px 12px;
    resize: vertical;
    background: #fff;
    color: var(--text);
  }
  .manual-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }
  .draft-editor-overlay {
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: 12px;
    z-index: 4;
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid rgba(19, 32, 46, 0.1);
    box-shadow: 0 16px 34px rgba(15, 23, 42, 0.22);
    backdrop-filter: blur(12px);
    padding: 12px;
  }
  .draft-editor-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 8px;
  }
  .draft-editor-title {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .draft-editor-title strong {
    font-size: 14px;
  }
  .draft-editor-title span {
    font-size: 12px;
    color: var(--muted);
  }
  .draft-editor-overlay textarea {
    width: 100%;
    min-height: 58px;
    margin-top: 8px;
    border: 1px solid rgba(19, 32, 46, 0.12);
    border-radius: 14px;
    padding: 10px 12px;
    resize: vertical;
    background: #fff;
    color: var(--text);
  }
  .draft-stack {
    display: grid;
    gap: 10px;
    margin-top: 12px;
  }
  .draft-card {
    border-radius: 22px;
    border: 1px dashed rgba(21, 32, 43, 0.16);
    background: #F8FBFD;
    padding: 12px 14px;
  }
  .draft-card strong {
    display: block;
    margin-bottom: 4px;
  }
  .draft-card p {
    margin: 8px 0 0;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.4;
  }
  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }
  .chip-btn {
    border-radius: 999px;
    padding: 8px 12px;
    background: rgba(21, 32, 43, 0.06);
    color: var(--text);
    font-size: 12px;
    font-weight: 700;
  }
  .chip-btn.active {
    background: #15202B;
    color: #fff;
  }
  .damage-stack {
    display: grid;
    gap: 12px;
  }
  .damage-card {
    padding: 14px;
  }
  .damage-head {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: flex-start;
  }
  .damage-title {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .damage-icon {
    width: 42px;
    height: 42px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    color: #fff;
    font-size: 12px;
    font-weight: 900;
  }
  .damage-title strong {
    display: block;
  }
  .damage-title span,
  .muted {
    color: var(--muted);
    font-size: 12px;
  }
  .review-pill {
    border-radius: 999px;
    padding: 6px 10px;
    color: #fff;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
  }
  .decision-row,
  .closeup-row,
  .top-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .decision-btn.confirm { background: rgba(45, 203, 112, 0.12); color: #16984A; }
  .decision-btn.reject { background: rgba(255, 92, 89, 0.12); color: #D54E4B; }
  .decision-btn.uncertain { background: rgba(255, 159, 10, 0.14); color: #C97A00; }
  .closeups {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(84px, 1fr));
    gap: 8px;
    margin-top: 10px;
  }
  .closeups a {
    display: block;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid var(--border);
    background: #E9EEF2;
  }
  .closeups img {
    width: 100%;
    aspect-ratio: 1 / 1;
    object-fit: cover;
  }
  .loading {
    text-align: center;
    color: var(--muted);
    padding: 40px 0;
  }
  @media (max-width: 420px) {
    .slot-meta,
    .summary-grid,
    .slot-grid,
    .gallery {
      grid-template-columns: 1fr;
    }
    .section-title,
    .hero-title {
      max-width: none;
    }
    .hero-title {
      font-size: 28px;
    }
    .section-title,
    .capture-head {
      grid-template-columns: 1fr;
    }
  }
`;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatStatus(value: string) {
  return value.replace(/_/g, " ");
}

function centeredBox(x: number, y: number): BBox {
  const width = 0.18;
  const height = 0.18;
  return {
    x1: clamp(x - width / 2, 0.02, 0.8),
    y1: clamp(y - height / 2, 0.02, 0.8),
    x2: clamp(x + width / 2, 0.2, 0.98),
    y2: clamp(y + height / 2, 0.2, 0.98),
  };
}

function humanizeViewLabel(label?: string) {
  if (!label) return "неподходящий ракурс";
  const normalized = label.trim().toLowerCase().replace(/^['"]|['"]$/g, "");
  const labels: Record<string, string> = {
    front: "Перед",
    left_side: "Левый бок",
    right_side: "Правый бок",
    rear: "Зад",
    front_valid: "передний ракурс",
    rear_valid: "задний ракурс",
    side_valid: "боковой ракурс",
    angled_invalid: "неподходящий угол съёмки",
    other_invalid: "неподходящий ракурс",
    front_left_3q: "передний левый угол",
    front_right_3q: "передний правый угол",
    rear_left_3q: "задний левый угол",
    rear_right_3q: "задний правый угол",
  };
  return labels[normalized] || normalized.replace(/_/g, " ");
}

function humanizeRejectionReason(reason?: string, expectedSlot?: string) {
  if (!reason) {
    return "Фото отклонено. Попробуйте снять кадр ещё раз.";
  }

  const wrongViewMatch = reason.match(/^wrong_viewpoint:\s*expected\s+([^,]+),\s*got\s+(.+)$/);
  if (wrongViewMatch) {
    const expected = SLOT_LABELS[wrongViewMatch[1]] || SLOT_LABELS[expectedSlot || ""] || wrongViewMatch[1];
    const gotRaw = (wrongViewMatch[2] || "").trim().replace(/^['"]|['"]$/g, "").toLowerCase();
    const got = humanizeViewLabel(gotRaw);
    if (gotRaw === "angled_invalid") {
      return `Фото не подходит: машина снята под углом. Нужен кадр «${expected}». Встаньте ровнее напротив нужной стороны и снимите кузов целиком.`;
    }
    if (gotRaw === "other_invalid") {
      return `Фото не подходит: машина видна не целиком или кадр слишком обрезан. Нужен кадр «${expected}». Снимите весь кузов с нужной стороны без обрезанных краёв.`;
    }
    if (gotRaw === "front_valid" || gotRaw === "rear_valid" || gotRaw === "side_valid") {
      return `Фото не подходит по углу съёмки. Нужен кадр «${expected}». Перейдите к нужному ракурсу и снимите кузов целиком.`;
    }
    return `Неверный ракурс. Нужен кадр «${expected}», а сейчас больше похож на «${got}». Подойдите к нужной стороне машины и снимите кузов целиком.`;
  }

  const messages: Record<string, string> = {
    too_dark: "Слишком темно. Добавьте света или снимите под другим углом, чтобы кузов был хорошо виден.",
    overexposed: "Кадр пересвечен. Уберите сильные блики и попробуйте снять чуть темнее.",
    too_blurry: "Фото смазано. Удерживайте телефон ровнее и дождитесь резкого кадра.",
    car_too_small: "Машина слишком далеко. Подойдите ближе, чтобы кузов занимал большую часть кадра.",
    car_cut_off: "Машина обрезана. Снимите весь нужный ракурс целиком, без обрезанных краёв.",
    wrong_distance: "Неподходящая дистанция. Держите машину целиком в кадре, но без слишком большого пустого фона.",
    wrong_view: "Нужен другой ракурс. Перестройтесь так, чтобы был виден именно требуемый бок или часть машины.",
    duplicate_upload: "Это фото уже загружалось. Сделайте новый кадр этого же ракурса.",
    no_car_detected: "Машина распознана неуверенно. Снимите авто целиком и уберите лишний фон из кадра.",
    quality_gate_reject: "Фото не прошло автоматическую проверку качества. Попробуйте снять ровнее, светлее и ближе.",
    angled_invalid: "Фото не подходит: машина снята под углом. Встаньте ровнее напротив нужной стороны машины.",
    other_invalid: "Фото не подходит: машина видна не целиком или кадр слишком обрезан. Переснимите машину целиком с нужной стороны.",
  };

  const normalizedReason = reason.trim().toLowerCase().replace(/^['"]|['"]$/g, "");
  return (
    messages[normalizedReason] ||
    messages[reason] ||
    `Фото отклонено: ${normalizedReason.replace(/_/g, " ")}. Попробуйте снять кадр ещё раз.`
  );
}

async function readApiError(response: Response, fallback: string): Promise<string> {
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

function App() {
  const params = new URLSearchParams(window.location.search);
  const [inspectionId, setInspectionId] = useState(params.get("inspection_id") || "");
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
  const viewerRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const localPreviewsRef = useRef<Record<string, LocalPreview | undefined>>({});

  useEffect(() => {
    tg?.ready?.();
    tg?.expand?.();
  }, []);

  useEffect(() => {
    if (inspectionId) {
      void loadInspection(inspectionId);
    }
  }, [inspectionId]);

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
  const hasInferenceOutput = orderedImages.some(
    (image) => !!image.overlay_url || image.predicted_damages.length > 0 || image.manual_damages.length > 0,
  );
  const inferenceReady =
    !!data &&
    captureComplete &&
    (hasInferenceOutput || ["ready_for_review", "under_review", "finalized"].includes(data.status));
  const waitingForInference = !!data && captureComplete && !inferenceReady;
  const pendingCount = orderedImages.reduce(
    (sum, image) =>
      sum +
      image.predicted_damages.filter((damage) => ["pending", "uncertain"].includes(damage.review_status)).length,
    0,
  );
  const totalFindings = orderedImages.reduce(
    (sum, image) => sum + image.predicted_damages.length + image.manual_damages.length,
    0,
  );

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
      const response = await fetch(`${API}/miniapp/inspections/${id}`);
      if (!response.ok) {
        let detail: ApiErrorDetail | null = null;
        try {
          const json = await response.json();
          detail = json?.detail ?? null;
        } catch {
          detail = null;
        }
        if (response.status === 409 && detail?.code === "inspection_closed") {
          setData(null);
          setFinalizeResult((current) =>
            current ?? {
              inspection_id: id,
              status: detail?.status || "finalized",
              canonical_damage_count: 0,
            },
          );
          setError("Этот осмотр уже завершён и больше не доступен для редактирования.");
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      const json = await response.json();
      setData(json.data);
    } catch (err: any) {
      setError(err.message || "Не удалось загрузить инспекцию.");
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
      const uploadForm = new FormData();
      uploadForm.append("file", file);
      uploadForm.append("image_type", "required_view");
      uploadForm.append("slot_code", slot);
      uploadForm.append("capture_order", String(SLOT_ORDER.indexOf(slot) + 1));
      const uploadResponse = await fetch(`${API}/inspections/${data.inspection_id}/images`, {
        method: "POST",
        body: uploadForm,
      });
      if (!uploadResponse.ok) throw new Error(await readApiError(uploadResponse, "Не удалось загрузить фото"));
      const uploadJson = await uploadResponse.json();
      const imageId = uploadJson.data.image_id;

      const checkResponse = await fetch(`${API}/inspections/${data.inspection_id}/run-initial-checks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_id: imageId, expected_slot: slot }),
      });
      if (!checkResponse.ok) throw new Error(await readApiError(checkResponse, "Не удалось проверить фото"));
      const checkJson = await checkResponse.json();
      if (!checkJson.data.accepted) {
        const reason = checkJson.data.rejection_reason || checkJson.data.quality_label || "Фото отклонено";
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
    } catch (err: any) {
      setError(err.message || "Не удалось загрузить фото.");
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
    setBusy(true);
    setPhotosReviewConfirmed(false);
    setError("");
    try {
      const response = await fetch(`${API}/inspections/${currentInspectionId}/run-damage-inference?force_sync=true`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(await readApiError(response, "Не удалось запустить анализ"));
      await loadInspection(currentInspectionId);
    } catch (err: any) {
      setError(err.message || "Не удалось запустить анализ.");
    } finally {
      setBusy(false);
    }
  }

  async function updateDecision(damageId: string, action: "confirm" | "reject" | "uncertain") {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API}/miniapp/damages/${damageId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (data) await loadInspection(data.inspection_id);
    } catch (err: any) {
      setError(err.message || "Не удалось сохранить решение.");
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
        const response = await fetch(`${API}/miniapp/damages/manual`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inspection_session_id: data.inspection_id,
            base_image_id: image.image_id,
            damage_type: draft.damage_type,
            bbox_norm: draft.bbox_norm,
            severity_hint: draft.severity_hint,
            note: draft.note || undefined,
          }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
      }
      setManualDrafts((current) => current.filter((draft) => draft.image_id !== image.image_id));
      setSelectedDraftId(null);
      setManualModeByImage((current) => ({ ...current, [image.image_id]: false }));
      await loadInspection(data.inspection_id);
    } catch (err: any) {
      setError(err.message || "Не удалось сохранить добавленные вручную повреждения.");
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
      const form = new FormData();
      form.append("file", file);
      if (damageRefType && damageRefId) {
        form.append("damage_ref_type", damageRefType);
        form.append("damage_ref_id", damageRefId);
      }
      const response = await fetch(`${API}/miniapp/images/${imageId}/attach-closeup`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) throw new Error(await readApiError(response, "Не удалось загрузить дополнительное фото"));
      if (data) await loadInspection(data.inspection_id);
    } catch (err: any) {
      setError(err.message || "Не удалось загрузить крупный план.");
    } finally {
      if (isImageLevel) {
        setUploadingImageCloseupFor(null);
      } else {
        setUploadingCloseupFor(null);
      }
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
      const response = await fetch(`${API}/inspections/${data.inspection_id}/finalize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photos_review_confirmed: true }),
      });
      if (!response.ok) throw new Error(await readApiError(response, "Не удалось завершить осмотр"));
      const json = await response.json();
      setFinalizeResult(json.data);
      setData((current) => (current ? { ...current, status: json.data.status } : current));
      tg?.sendData?.(
        JSON.stringify({
          action: "inspection_finalized",
          inspection_id: json.data.inspection_id,
          comparison_status: json.data.comparison_status,
          canonical_damage_count: json.data.canonical_damage_count,
        }),
      );
      if (tg?.close) {
        window.setTimeout(() => tg.close(), 350);
      }
    } catch (err: any) {
      setError(err.message || "Не удалось завершить осмотр.");
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
              <span>{Math.round(damage.confidence * 100)}% уверенность</span>
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

  return (
    <div className="app-shell">
      <style>{css}</style>
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
                    ? "Можно перейти к проверке найденных повреждений."
                    : `Осталось снять: ${remainingSlots.map((slot) => SLOT_LABELS[slot]).join(", ")}`}
                </div>
              </div>
              <div className={`slot-status ${captureComplete ? "done" : ""}`}>
                {captureComplete ? "Готово" : "Обязательные фото"}
              </div>
              </div>
          </div>
        ) : null}
        {error ? (
          <div className="notice error">
            <strong>Что-то пошло не так</strong>
            <p>{error}</p>
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

        {loading && !data ? <div className="loading">Загружаем осмотр…</div> : null}

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
            <div className="summary-grid">
              <div className="summary-card">
                <strong>{orderedImages.length}</strong>
                <span>Проверено ракурсов</span>
              </div>
              <div className="summary-card">
                <strong>{totalFindings}</strong>
                <span>Найдено системой</span>
              </div>
              <div className="summary-card">
                <strong>{pendingCount}</strong>
                <span>Низкая/средняя уверенность</span>
              </div>
            </div>

            {waitingForInference ? (
              <>
                <div className="section-title">
                  <h3>Подтвердите набор фото</h3>
                  <span>До анализа можно переснять ракурс и добавить доп. фото</span>
                </div>
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
                          <label className="ghost-btn">
                            {uploadingImageCloseupFor === image.image_id ? "Загружаем..." : "Добавить доп. фото"}
                            <input
                              hidden
                              type="file"
                              accept="image/*"
                              capture="environment"
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) {
                                  void attachCloseup(image.image_id, file);
                                }
                                event.currentTarget.value = "";
                              }}
                            />
                          </label>
                        </div>
                        <div className="viewer">
                          <img src={image.raw_url} alt={SLOT_LABELS[image.slot_code] || image.slot_code} draggable={false} />
                        </div>
                        <div className="section-title">
                          <h3>Дополнительные фото</h3>
                          <span>{image.image_closeups?.length || 0} шт.</span>
                        </div>
                        {image.image_closeups?.length ? (
                          renderCloseups(image.image_closeups)
                        ) : (
                          <div className="muted">Пока нет дополнительных фото для этого ракурса.</div>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="notice" style={{ marginTop: 16 }}>
                  <strong>Запуск анализа повреждений</strong>
                  <p>Подтвердите, что вы проверили все 4 обязательных ракурса и загрузили нужные доп. фото.</p>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                    <button
                      className={photosReviewConfirmed ? "secondary-btn" : "ghost-btn"}
                      onClick={() => setPhotosReviewConfirmed((value) => !value)}
                    >
                      {photosReviewConfirmed ? "Проверка подтверждена" : "Я проверил(а) фото перед анализом"}
                    </button>
                    <button
                      className="primary-btn"
                      disabled={!photosReviewConfirmed || busy}
                      onClick={() => void runInference(data.inspection_id)}
                    >
                      Запустить анализ повреждений
                    </button>
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
                        </div>
                        {image.predicted_damages.length ? (
                          <div className="damage-stack" style={{ marginTop: 12 }}>
                            {image.predicted_damages.map((damage) => renderPredictedDamage(image, damage))}
                          </div>
                        ) : (
                          <div className="muted" style={{ marginTop: 12 }}>На этом ракурсе повреждения не найдены.</div>
                        )}
                        <div className="section-title">
                          <h3>Дополнительные фото</h3>
                          <span>{image.image_closeups?.length || 0} шт.</span>
                        </div>
                        {image.image_closeups?.length ? (
                          renderCloseups(image.image_closeups)
                        ) : (
                          <div className="muted">Пока нет дополнительных фото для этого ракурса.</div>
                        )}
                      </div>
                    );
                  })}
                </div>

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
