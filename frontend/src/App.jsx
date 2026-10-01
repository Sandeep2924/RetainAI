import { useState, useEffect } from "react";
import { getToken, setToken, clearToken, fetchMe, fetchAppSettings } from "./api";
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
import { Menu } from "lucide-react";

export default function App() {
  const [authState, setAuthState] = useState("checking"); // "checking" | "authed" | "unauthed"
  const [user, setUser] = useState(null); // { email, role }
  const [view, setView] = useState("dashboard");
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [emailComposeCustomerId, setEmailComposeCustomerId] = useState(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    // Check if URL has token from redirect (e.g. /?token=...&verified=true)
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      setToken(urlToken);
      window.history.replaceState({}, document.title, window.location.pathname);
    }

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
    <div className="flex h-screen w-full bg-slate-950 text-slate-100 overflow-hidden font-sans">
      <Sidebar
        view={view}
        setView={(v) => {
          setView(v);
          setSelectedCustomerId(null);
          setEmailComposeCustomerId(null);
          setIsMobileMenuOpen(false);
        }}
        email={user?.email}
        role={user?.role}
        onLogout={handleLogout}
        isOpen={isMobileMenuOpen}
        onClose={() => setIsMobileMenuOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Mobile Top Navigation Bar */}
        <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-slate-900/90 backdrop-blur border-b border-slate-800 sticky top-0 z-30 shrink-0">
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="p-1.5 -ml-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
              aria-label="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 ring-2 ring-cyan-500/20 animate-pulse" />
              <span className="font-bold text-sm tracking-tight text-white">RetainAI</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-cyan-300 font-medium capitalize px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30">
              {view}
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto scrollbar-thin p-3.5 sm:p-6 lg:p-8 min-w-0 w-full">
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
    </div>
  );
}
