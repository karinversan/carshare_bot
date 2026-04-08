import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";

import { assignAdminCase, fetchAdminCase, fetchAdminCases, updateAdminCaseStatus } from "./api";
import { CaseActionBar } from "./components/CaseActionBar";
import { CaseMatchesList } from "./components/CaseMatchesList";
import { CaseOverview } from "./components/CaseOverview";
import { CaseQueueSidebar } from "./components/CaseQueueSidebar";
import { DashboardHeader } from "./components/DashboardHeader";
import { LoginScreen } from "./components/LoginScreen";
import { ReviewerPanel } from "./components/ReviewerPanel";
import { cl, type CaseDetail, type CaseSummary } from "./domain";
import { useAdminSession } from "./useAdminSession";
import { caseStatusLabel } from "./utils";

function App() {
  const {
    apiFetch,
    authError,
    authLoading,
    authToken,
    login,
    loginEmail,
    loginPassword,
    logout,
    setLoginEmail,
    setLoginPassword,
  } = useAdminSession();
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
    if (!authToken) {
      setCases([]);
      setSelectedCase(null);
      setError("");
    }
  }, [authToken]);

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function handleLogout() {
    logout();
    setCases([]);
    setSelectedCase(null);
    setError("");
  }

  async function loadCases() {
    setLoading(true);
    setError("");
    try {
      const items = await fetchAdminCases(apiFetch, filter);
      setCases(items);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось загрузить очередь кейсов.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function loadCase(caseId: string) {
    setLoading(true);
    setError("");
    try {
      const details = await fetchAdminCase(apiFetch, caseId);
      setSelectedCase(details);
      if (details.assignee_name) {
        setAssigneeName(details.assignee_name);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось загрузить детали кейса.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function assignCase() {
    if (!selectedCase) return;
    setLoading(true);
    setError("");
    try {
      await assignAdminCase(apiFetch, assigneeName, selectedCase.id);
      await loadCase(selectedCase.id);
      await loadCases();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось назначить кейс.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function updateStatus(status: string) {
    if (!selectedCase) return;
    setLoading(true);
    setError("");
    try {
      await updateAdminCaseStatus(
        apiFetch,
        selectedCase.id,
        note || `Статус обновлён: ${caseStatusLabel(status)}`,
        status,
      );
      setNote("");
      await loadCase(selectedCase.id);
      await loadCases();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Не удалось обновить статус кейса.";
      setError(message);
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
        onSubmit={() => {
          setError("");
          void login();
        }}
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
      <DashboardHeader isPhone={isPhone} onLogout={handleLogout} onRefresh={() => void loadCases()} />

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
          <CaseQueueSidebar
            cases={cases}
            filter={filter}
            isPhone={isPhone}
            isTablet={isTablet}
            loading={loading}
            onFilterChange={setFilter}
            onSelectCase={(caseId) => void loadCase(caseId)}
            selectedCaseId={selectedCase?.id}
          />

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
                <CaseOverview caseDetail={selectedCase} isPhone={isPhone} />
                <ReviewerPanel
                  assigneeName={assigneeName}
                  caseDetail={selectedCase}
                  isPhone={isPhone}
                  isTablet={isTablet}
                  note={note}
                  onAssign={() => void assignCase()}
                  onAssigneeNameChange={setAssigneeName}
                  onNoteChange={setNote}
                />
                <CaseMatchesList isPhone={isPhone} matches={selectedCase.matches} />
                <CaseActionBar isPhone={isPhone} onUpdateStatus={(status) => void updateStatus(status)} />
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
