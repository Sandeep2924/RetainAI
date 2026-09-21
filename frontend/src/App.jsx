import { useState, useEffect } from "react";
import { getToken, clearToken, fetchMe, fetchAppSettings } from "./api";
import { setRiskThresholds } from "./risk";
import Sidebar from "./components/Sidebar";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import AllCustomers from "./pages/AllCustomers";
import CustomerDetail from "./pages/CustomerDetail";
import Team from "./pages/Team";
import EmailDrafts from "./pages/EmailDrafts";
import Reports from "./pages/Reports";
import Predictions from "./pages/Predictions";
import Settings from "./pages/Settings";

export default function App() {
  const [authState, setAuthState] = useState("checking"); // "checking" | "authed" | "unauthed"
  const [user, setUser] = useState(null); // { email, role }
  const [view, setView] = useState("dashboard");
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [emailComposeCustomerId, setEmailComposeCustomerId] = useState(null);

  useEffect(() => {
    if (!getToken()) {
      setAuthState("unauthed");
      return;
    }
    fetchMe()
      .then((me) => {
        setUser(me);
        setAuthState("authed");
        fetchAppSettings()
          .then((s) => setRiskThresholds(s.high_risk_threshold))
          .catch(() => {}); // badges just keep the 0.7 default if this fails
      })
      .catch(() => {
        clearToken();
        setAuthState("unauthed");
      });
  }, []);

  function handleAuthed(me) {
    setUser(me);
    setAuthState("authed");
  }

  function handleLogout() {
    clearToken();
    setUser(null);
    setAuthState("unauthed");
    setView("dashboard");
    setSelectedCustomerId(null);
  }

  function openCustomer(id) {
    setSelectedCustomerId(id);
  }

  function openEmailDraftFor(customerId) {
    setEmailComposeCustomerId(customerId);
    setSelectedCustomerId(null);
    setView("emails");
  }

  if (authState === "checking") {
    return null;
  }

  if (authState === "unauthed") {
    return <Login onAuthed={handleAuthed} />;
  }

  const isAdmin = user?.role === "admin";

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <Sidebar
        view={view}
        setView={(v) => {
          setView(v);
          setSelectedCustomerId(null);
          setEmailComposeCustomerId(null);
        }}
        email={user?.email}
        role={user?.role}
        onLogout={handleLogout}
      />
      <main
        className="scrollbar-thin"
        style={{ flex: 1, padding: "28px 32px", overflowY: "auto" }}
      >
        {selectedCustomerId ? (
          <CustomerDetail
            customerId={selectedCustomerId}
            onBack={() => setSelectedCustomerId(null)}
            isAdmin={isAdmin}
            onGenerateEmail={openEmailDraftFor}
          />
        ) : view === "dashboard" ? (
          <Dashboard
            onSelectCustomer={openCustomer}
            onViewAll={() => setView("customers")}
            isAdmin={isAdmin}
          />
        ) : view === "team" && isAdmin ? (
          <Team onBack={() => setView("dashboard")} currentUserEmail={user?.email} />
        ) : view === "emails" ? (
          <EmailDrafts
            onBack={() => {
              setView("dashboard");
              setEmailComposeCustomerId(null);
            }}
            initialCustomerId={emailComposeCustomerId}
          />
        ) : view === "reports" ? (
          <Reports onBack={() => setView("dashboard")} />
        ) : view === "predictions" ? (
          <Predictions onBack={() => setView("dashboard")} />
        ) : view === "settings" ? (
          <Settings onBack={() => setView("dashboard")} isAdmin={isAdmin} />
        ) : (
          <AllCustomers
            onSelectCustomer={openCustomer}
            onBack={() => setView("dashboard")}
          />
        )}
      </main>
    </div>
  );
}
