import {
  LayoutDashboard,
  Users,
  TrendingUp,
  Mail,
  FileSpreadsheet,
  Settings,
  ShieldCheck,
  LogOut,
  X,
} from "lucide-react";

export default function Sidebar({
  view,
  setView,
  email,
  role,
  onLogout,
  isOpen = false,
  onClose = () => {},
}) {
  const items = [
    { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { key: "customers", label: "All Customers", icon: Users },
    { key: "predictions", label: "Predictions", icon: TrendingUp },
    { key: "emails", label: "Email Drafts", icon: Mail },
    { key: "reports", label: "Reports", icon: FileSpreadsheet },
    { key: "settings", label: "Settings", icon: Settings },
    ...(role === "admin" ? [{ key: "team", label: "Team", icon: ShieldCheck }] : []),
  ];

  const handleSelect = (key) => {
    setView(key);
    onClose();
  };

  const navContent = (
    <div className="flex flex-col h-full">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-3 mb-6">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="w-2.5 h-2.5 rounded-full bg-cyan-400 ring-4 ring-cyan-500/20 animate-pulse shrink-0"
          />
          <div>
            <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-1.5">
              RetainAI
            </h1>
            <p className="text-[11px] text-slate-400 uppercase tracking-wider font-medium">
              Risk Console
            </p>
          </div>
        </div>

        {/* Close Button on Mobile Drawer */}
        <button
          onClick={onClose}
          className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          aria-label="Close menu"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Nav List */}
      <nav className="flex-1 space-y-1">
        {items.map((item) => {
          const active = view === item.key;
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => handleSelect(item.key)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                active
                  ? "bg-cyan-500/15 text-cyan-300 font-semibold border border-cyan-500/30 shadow-sm shadow-cyan-950"
                  : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
              }`}
            >
              <Icon className={`w-4 h-4 shrink-0 ${active ? "text-cyan-400" : "text-slate-400"}`} />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* User & Sign Out Footer */}
      <div className="mt-auto pt-4 border-t border-slate-800/80 px-2 space-y-3">
        <div className="space-y-0.5">
          <p className="text-xs text-slate-300 font-medium truncate" title={email}>
            {email}
          </p>
          {role && (
            <p className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  role === "admin" ? "bg-emerald-400" : "bg-slate-500"
                }`}
              />
              <span className="capitalize">{role === "admin" ? "Administrator" : "Member"}</span>
            </p>
          )}
        </div>

        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-rose-300 hover:bg-rose-500/10 border border-slate-800 hover:border-rose-500/30 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden lg:flex w-60 shrink-0 bg-slate-900/95 backdrop-blur border-r border-slate-800/80 flex-col p-4 h-screen sticky top-0 z-20">
        {navContent}
      </aside>

      {/* Mobile Drawer Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Mobile Drawer Slider */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] bg-slate-900 border-r border-slate-800 p-4 flex flex-col h-full shadow-2xl transition-transform duration-300 ease-out lg:hidden ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {navContent}
      </aside>
    </>
  );
}
