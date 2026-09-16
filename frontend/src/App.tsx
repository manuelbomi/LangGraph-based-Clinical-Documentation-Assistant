import { NavLink, Route, Routes } from "react-router-dom";

import { EncounterDetailPage } from "./pages/EncounterDetailPage";
import { PatientHistoryPage } from "./pages/PatientHistoryPage";
import { UploadPage } from "./pages/UploadPage";

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded-md px-3 py-1.5 text-sm font-medium ${
          isActive ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-base font-semibold text-slate-900">
              Clinical Documentation &amp; Discharge Summary Assistant
            </h1>
            <p className="text-xs text-slate-400">Built with LangGraph</p>
          </div>
          <nav className="flex gap-1">
            <NavItem to="/">Upload &amp; Process</NavItem>
            <NavItem to="/patients">Patient Encounter History</NavItem>
          </nav>
        </div>
      </header>

      <div className="border-b border-amber-200 bg-amber-50">
        <div className="mx-auto max-w-6xl px-4 py-2 text-xs font-medium text-amber-800">
          Administrative documentation only -- not medical advice or a diagnostic tool. All patient data in this
          demo is synthetic and fictitious. Every output requires clinician review before it is final.
        </div>
      </div>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/patients" element={<PatientHistoryPage />} />
          <Route path="/encounters/:id" element={<EncounterDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}
