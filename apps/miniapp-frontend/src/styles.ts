// -------------------------------------------------------------------------- //
//                                   STYLES                                   //
// -------------------------------------------------------------------------- //

export const miniappStyles = `
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
  .extra-comment-input {
    width: 100%;
    min-height: 74px;
    border-radius: 16px;
    border: 1px solid var(--border);
    background: rgba(255, 255, 255, 0.9);
    color: var(--text);
    padding: 10px 12px;
    line-height: 1.35;
    resize: vertical;
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
    opacity: 0.52;
  }
  .viewer .vector-overlay {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
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
