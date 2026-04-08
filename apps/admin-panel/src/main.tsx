import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";

import { EvidenceCard } from "./components/EvidenceCard";
import { LoginScreen } from "./components/LoginScreen";
import { ADMIN_EMAIL_KEY, ADMIN_TOKEN_KEY, API } from "./config";
import { cl, type CaseDetail, type CaseSummary } from "./domain";
import {
  caseStatusLabel,
  formatDate,
  matchColor,
  matchStatusLabel,
  readAdminError,
  slotLabel,
  statusColor,
} from "./utils";

function App() {
  const [authToken, setAuthToken] = useState(() => window.localStorage.getItem(ADMIN_TOKEN_KEY) || "");
  const [loginEmail, setLoginEmail] = useState(() => window.localStorage.getItem(ADMIN_EMAIL_KEY) || "admin@example.com");
  const [loginPassword, setLoginPassword] = useState("admin123");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCase, setSelectedCase] = useState<CaseDetail | null>(null);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [assigneeName, setAssigneeName] = useState("Karin");
  const [viewportWidth, setViewportWidth] = useState(() => window.innerWidth);

  const isPhone = viewportWidth < 760;
  const isTablet = viewportWidth < 1180;

  useEffect(() => {
    if (authToken) {
      void loadCases();
    }
  }, [filter, authToken]);

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  async function apiFetch(input: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers || undefined);
    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }
    const response = await fetch(input, { ...init, headers });
    if (response.status === 401 || response.status === 403) {
      setAuthToken("");
      window.localStorage.removeItem(ADMIN_TOKEN_KEY);
    }
    return response;
  }

  async function login() {
    setAuthLoading(true);
    setAuthError("");
    try {
      const response = await fetch(`${API}/auth/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: loginEmail.trim(),
          password: loginPassword,
        }),
      });
      if (!response.ok) {
        throw new Error(await readAdminError(response, "Не удалось войти в админку"));
      }
      const json = await response.json();
      window.localStorage.setItem(ADMIN_TOKEN_KEY, json.access_token);
      window.localStorage.setItem(ADMIN_EMAIL_KEY, loginEmail.trim());
      setAuthToken(json.access_token);
      setAuthError("");
      setError("");
    } catch (err: any) {
      setAuthError(err.message || "Не удалось войти в админку.");
    } finally {
      setAuthLoading(false);
    }
  }

  function logout() {
    setAuthToken("");
    setCases([]);
    setSelectedCase(null);
    setError("");
    window.localStorage.removeItem(ADMIN_TOKEN_KEY);
  }

  async function loadCases() {
    setLoading(true);
    setError("");
    try {
      const url = filter ? `${API}/admin-cases?status=${filter}` : `${API}/admin-cases`;
      const response = await apiFetch(url);
      if (!response.ok) throw new Error(await readAdminError(response, "Не удалось загрузить очередь кейсов"));
      const json = await response.json();
      setCases(json.data);
    } catch (err: any) {
      setError(err.message || "Не удалось загрузить очередь кейсов.");
    } finally {
      setLoading(false);
    }
  }

  async function loadCase(caseId: string) {
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch(`${API}/admin-cases/${caseId}`);
      if (!response.ok) throw new Error(await readAdminError(response, "Не удалось загрузить детали кейса"));
      const json = await response.json();
      setSelectedCase(json.data);
      if (json.data.assignee_name) {
        setAssigneeName(json.data.assignee_name);
      }
    } catch (err: any) {
      setError(err.message || "Не удалось загрузить детали кейса.");
    } finally {
      setLoading(false);
    }
  }

  async function assignCase() {
    if (!selectedCase) return;
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch(`${API}/admin-cases/${selectedCase.id}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ first_name: assigneeName }),
      });
      if (!response.ok) throw new Error(await readAdminError(response, "Не удалось назначить кейс"));
      await loadCase(selectedCase.id);
      await loadCases();
    } catch (err: any) {
      setError(err.message || "Не удалось назначить кейс.");
    } finally {
      setLoading(false);
    }
  }

  async function updateStatus(status: string) {
    if (!selectedCase) return;
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch(`${API}/admin-cases/${selectedCase.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          resolved_note: note || `Статус обновлён: ${caseStatusLabel(status)}`,
        }),
      });
      if (!response.ok) throw new Error(await readAdminError(response, "Не удалось обновить статус кейса"));
      setNote("");
      await loadCase(selectedCase.id);
      await loadCases();
    } catch (err: any) {
      setError(err.message || "Не удалось обновить статус кейса.");
    } finally {
      setLoading(false);
    }
  }

  if (!authToken) {
    return (
      <LoginScreen
        authError={authError}
        authLoading={authLoading}
        loginEmail={loginEmail}
        loginPassword={loginPassword}
        onEmailChange={setLoginEmail}
        onPasswordChange={setLoginPassword}
        onSubmit={() => void login()}
      />
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: `linear-gradient(180deg, ${cl.lime} 0%, #D8FF7A 10%, ${cl.bg} 10%)`,
        color: cl.text,
        fontFamily: '"SF Pro Display", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        overflowX: "hidden",
        width: "100%",
      }}
    >
      <header
        style={{
          padding: isPhone ? "18px 14px 14px" : "24px 24px 18px",
          maxWidth: 1560,
          margin: "0 auto",
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: isPhone ? "column" : "row",
            justifyContent: "space-between",
            alignItems: isPhone ? "stretch" : "center",
            gap: 12,
            minWidth: 0,
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                background: "rgba(255,255,255,0.82)",
                borderRadius: 999,
                padding: "10px 14px",
                boxShadow: cl.shadow,
                marginBottom: 12,
              }}
            >
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: cl.green }} />
              <span style={{ fontSize: 13, fontWeight: 800 }}>Очередь кейсов активна</span>
            </div>
            <h1 style={{ margin: 0, fontSize: isPhone ? 28 : 34, letterSpacing: "-0.06em", lineHeight: 1.02 }}>
              Проверка новых повреждений
            </h1>
            <p style={{ margin: "10px 0 0", color: cl.muted, maxWidth: 620, fontSize: isPhone ? 15 : 16, lineHeight: 1.45 }}>
              Рабочая панель для спорных кейсов после завершения поездки. Назначьте кейс на себя, сравните осмотр до и
              после поездки, проверьте крупные планы и примите итоговое решение.
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, flexDirection: isPhone ? "column" : "row" }}>
            <button
              onClick={() => void loadCases()}
              style={{
                background: "#15202B",
                color: "#fff",
                borderRadius: 24,
                padding: "14px 18px",
                fontSize: 13,
                fontWeight: 800,
                alignSelf: isPhone ? "stretch" : "auto",
                width: isPhone ? "100%" : "auto",
                flexShrink: 0,
              }}
            >
              Обновить очередь
            </button>
            <button
              onClick={logout}
              style={{
                background: "#FFFFFF",
                color: cl.text,
                borderRadius: 24,
                padding: "14px 18px",
                fontSize: 13,
                fontWeight: 800,
                border: `1px solid ${cl.border}`,
                alignSelf: isPhone ? "stretch" : "auto",
                width: isPhone ? "100%" : "auto",
                flexShrink: 0,
              }}
            >
              Выйти
            </button>
          </div>
        </div>
      </header>

      <main
        style={{
          maxWidth: 1560,
          margin: "0 auto",
          padding: isPhone ? "0 14px 20px" : "0 24px 30px",
          width: "100%",
          boxSizing: "border-box",
          overflowX: "hidden",
        }}
      >
        {error ? (
          <div
            style={{
              marginBottom: 18,
              background: "#FFF1F0",
              border: `1px solid rgba(239, 68, 68, 0.22)`,
              borderRadius: 28,
              padding: 14,
              color: cl.red,
            }}
          >
            {error}
          </div>
        ) : null}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: isTablet ? "minmax(0, 1fr)" : "320px minmax(0, 1fr)",
            gap: 18,
            alignItems: "start",
            minWidth: 0,
          }}
        >
          <aside
            style={{
              background: cl.card,
              border: `1px solid ${cl.border}`,
              borderRadius: 34,
              boxShadow: cl.shadow,
              overflow: "hidden",
              minHeight: isTablet ? "auto" : "calc(100vh - 190px)",
              minWidth: 0,
            }}
          >
            <div style={{ padding: 18, borderBottom: `1px solid ${cl.border}` }}>
              <div style={{ fontSize: 12, color: cl.muted, fontWeight: 800, marginBottom: 10 }}>Фильтр по статусу</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {["", "open", "in_review", "resolved_confirmed", "resolved_no_issue", "dismissed"].map((value) => (
                  <button
                    key={value || "all"}
                    onClick={() => setFilter(value)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 999,
                      background: filter === value ? "#15202B" : "#F2F6F8",
                      color: filter === value ? "#fff" : cl.text,
                      fontSize: 12,
                      fontWeight: 800,
                      maxWidth: "100%",
                      overflowWrap: "anywhere",
                    }}
                  >
                    {value ? caseStatusLabel(value) : "Все"}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ maxHeight: isTablet ? "none" : "calc(100vh - 280px)", overflowY: isTablet ? "visible" : "auto" }}>
              {cases.length === 0 && !loading ? (
                <div style={{ padding: 28, color: cl.muted }}>Очередь пуста.</div>
              ) : null}
              {cases.map((item) => (
                <button
                  key={item.id}
                  onClick={() => void loadCase(item.id)}
                  style={{
                    width: "100%",
                    background: selectedCase?.id === item.id ? "#F4FFF7" : "transparent",
                    padding: 16,
                    borderBottom: `1px solid ${cl.border}`,
                    textAlign: "left",
                    minWidth: 0,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start", marginBottom: 8 }}>
                    <strong style={{ lineHeight: 1.35, minWidth: 0, overflowWrap: "anywhere" }}>{item.title}</strong>
                    <span
                      style={{
                        background: statusColor(item.status),
                        color: "#fff",
                        borderRadius: 999,
                        padding: "6px 9px",
                        fontSize: 10,
                        fontWeight: 900,
                        textTransform: "uppercase",
                        whiteSpace: isPhone ? "normal" : "nowrap",
                        overflowWrap: "anywhere",
                        textAlign: "center",
                        flexShrink: 0,
                      }}
                    >
                      {caseStatusLabel(item.status)}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: cl.muted, lineHeight: 1.45, overflowWrap: "anywhere" }}>{item.summary}</div>
                  <div style={{ marginTop: 10, fontSize: 11, color: cl.muted }}>
                    Авто {item.vehicle_id} • {item.assignee_name ? `Назначен: ${item.assignee_name}` : "Без исполнителя"} • {formatDate(item.opened_at)}
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section
            style={{
              background: cl.card,
              border: `1px solid ${cl.border}`,
              borderRadius: 34,
              boxShadow: cl.shadow,
              padding: isPhone ? 16 : 22,
              minHeight: isTablet ? "auto" : "calc(100vh - 190px)",
              minWidth: 0,
              overflowX: "hidden",
            }}
          >
            {!selectedCase ? (
              <div style={{ padding: 26, color: cl.muted }}>
                Выберите кейс слева. После этого можно назначить его на себя, сравнить кадры до и после поездки, посмотреть крупные планы и обновить статус.
              </div>
            ) : (
              <>
                <div
                  style={{
                    display: "flex",
                    flexDirection: isPhone ? "column" : "row",
                    justifyContent: "space-between",
                    gap: 16,
                    alignItems: isPhone ? "stretch" : "flex-start",
                    marginBottom: 18,
                    minWidth: 0,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <h2 style={{ margin: 0, fontSize: isPhone ? 24 : 30, letterSpacing: "-0.05em", overflowWrap: "anywhere" }}>
                      {selectedCase.title}
                    </h2>
                    <p style={{ margin: "8px 0 0", color: cl.muted }}>
                      Авто {selectedCase.vehicle_id} • {selectedCase.summary}
                    </p>
                  </div>
                  <span
                    style={{
                      background: statusColor(selectedCase.status),
                      color: "#fff",
                      borderRadius: 999,
                      padding: "8px 12px",
                      fontSize: 12,
                      fontWeight: 900,
                      textTransform: "uppercase",
                      alignSelf: isPhone ? "flex-start" : "auto",
                      maxWidth: "100%",
                      overflowWrap: "anywhere",
                    }}
                  >
                    {caseStatusLabel(selectedCase.status)}
                  </span>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: isPhone ? "minmax(0, 1fr)" : "repeat(3, minmax(0, 1fr))",
                    gap: 12,
                    marginBottom: 18,
                  }}
                >
                  <div style={{ background: "#F2FFF7", borderRadius: 28, padding: 16, border: `1px solid ${cl.border}` }}>
                    <div style={{ fontSize: 30, fontWeight: 900, color: cl.green }}>{selectedCase.comparison?.matched_count ?? 0}</div>
                    <div style={{ fontSize: 12, color: cl.muted }}>Совпало с осмотром до поездки</div>
                  </div>
                  <div style={{ background: "#FFF8ED", borderRadius: 28, padding: 16, border: `1px solid ${cl.border}` }}>
                    <div style={{ fontSize: 30, fontWeight: 900, color: cl.orange }}>{selectedCase.comparison?.possible_new_count ?? 0}</div>
                    <div style={{ fontSize: 12, color: cl.muted }}>Вероятно новые</div>
                  </div>
                  <div style={{ background: "#FFF2F1", borderRadius: 28, padding: 16, border: `1px solid ${cl.border}` }}>
                    <div style={{ fontSize: 30, fontWeight: 900, color: cl.red }}>{selectedCase.comparison?.new_confirmed_count ?? 0}</div>
                    <div style={{ fontSize: 12, color: cl.muted }}>Подтверждённо новые</div>
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: isTablet ? "minmax(0, 1fr)" : "minmax(0, 1fr) 260px",
                    gap: 16,
                    marginBottom: 18,
                    alignItems: "start",
                  }}
                >
                  <div
                    style={{
                      background: "#F7FBFC",
                      border: `1px solid ${cl.border}`,
                      borderRadius: 28,
                      padding: 16,
                      minWidth: 0,
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 800, color: cl.muted, marginBottom: 10 }}>Назначение кейса</div>
                    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", minWidth: 0 }}>
                      <input
                        value={assigneeName}
                        onChange={(event) => setAssigneeName(event.target.value)}
                        placeholder="Имя проверяющего"
                        style={{
                          flex: 1,
                          minWidth: isPhone ? "100%" : 180,
                          borderRadius: 20,
                          border: `1px solid ${cl.border}`,
                          padding: "12px 14px",
                          boxSizing: "border-box",
                        }}
                      />
                      <button
                        onClick={() => void assignCase()}
                        style={{
                          background: "#15202B",
                          color: "#fff",
                          borderRadius: 20,
                          padding: "12px 14px",
                          fontWeight: 800,
                          width: isPhone ? "100%" : "auto",
                        }}
                      >
                        Назначить на себя
                      </button>
                    </div>
                    <div style={{ marginTop: 10, fontSize: 13, color: cl.muted }}>
                      Текущий исполнитель: <strong style={{ color: cl.text }}>{selectedCase.assignee_name || "не назначен"}</strong>
                    </div>
                  </div>
                  <div
                    style={{
                      background: "#F7FBFC",
                      border: `1px solid ${cl.border}`,
                      borderRadius: 28,
                      padding: 16,
                      minWidth: 0,
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 800, color: cl.muted, marginBottom: 10 }}>Комментарий по решению</div>
                    <textarea
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Что показала проверка? Например: подтверждаем новую царапину на правом борту."
                      style={{
                        width: "100%",
                        minHeight: 92,
                        resize: "vertical",
                        borderRadius: 20,
                        border: `1px solid ${cl.border}`,
                        padding: 12,
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gap: 14, marginBottom: 18 }}>
                  {selectedCase.matches.map((match) => (
                    <article
                      key={match.id}
                      style={{
                        border: `1px solid ${cl.border}`,
                        borderRadius: 30,
                        padding: 16,
                        background: "#FCFDFE",
                        minWidth: 0,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          flexDirection: isPhone ? "column" : "row",
                          justifyContent: "space-between",
                          gap: 12,
                          alignItems: isPhone ? "stretch" : "center",
                          marginBottom: 14,
                          minWidth: 0,
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <strong style={{ display: "block", marginBottom: 4 }}>{slotLabel(match.view_slot)}</strong>
                          <span style={{ color: cl.muted, fontSize: 12 }}>
                            Оценка совпадения: {(match.match_score * 100).toFixed(1)}%
                          </span>
                        </div>
                        <span
                          style={{
                            background: matchColor(match.status),
                            color: "#fff",
                            borderRadius: 999,
                            padding: "7px 10px",
                            fontSize: 11,
                            fontWeight: 900,
                            textTransform: "uppercase",
                            alignSelf: isPhone ? "flex-start" : "auto",
                            maxWidth: "100%",
                            overflowWrap: "anywhere",
                          }}
                        >
                          {matchStatusLabel(match.status)}
                        </span>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: isPhone ? "minmax(0, 1fr)" : "1fr 1fr", gap: 12, minWidth: 0 }}>
                        <EvidenceCard title="Осмотр до поездки" damage={match.pre_damage} />
                        <EvidenceCard title="Осмотр после поездки" damage={match.post_damage} />
                      </div>
                    </article>
                  ))}
                </div>

                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <button
                    onClick={() => void updateStatus("in_review")}
                    style={{ background: cl.blue, color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
                  >
                    Взять в работу
                  </button>
                  <button
                    onClick={() => void updateStatus("resolved_confirmed")}
                    style={{ background: cl.green, color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
                  >
                    Подтвердить новое повреждение
                  </button>
                  <button
                    onClick={() => void updateStatus("resolved_no_issue")}
                    style={{ background: "#64748B", color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
                  >
                    Новых повреждений нет
                  </button>
                  <button
                    onClick={() => void updateStatus("dismissed")}
                    style={{ background: cl.red, color: "#fff", borderRadius: 20, padding: "12px 16px", fontWeight: 800, width: isPhone ? "100%" : "auto" }}
                  >
                    Отклонить кейс
                  </button>
                </div>
              </>
            )}
            {loading ? <div style={{ marginTop: 16, color: cl.muted }}>Загрузка…</div> : null}
          </section>
        </div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
