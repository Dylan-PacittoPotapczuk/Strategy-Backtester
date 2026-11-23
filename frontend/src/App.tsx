import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { ConfigurePage } from './pages/ConfigurePage'
import { ResultsPage } from './pages/ResultsPage'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="topbar">
          <div className="brand">
            <span className="brand-mark" aria-hidden />
            <div>
              <div className="brand-name">Strategy Backtester</div>
              <div className="brand-sub">Risk guardrails · Phase A</div>
            </div>
          </div>
          <nav>
            <NavLink to="/" end>
              Configure
            </NavLink>
            <span className="nav-muted">Compare (Phase B)</span>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<ConfigurePage />} />
            <Route path="/results/:runId" element={<ResultsPage />} />
          </Routes>
        </main>
        <footer className="foot">
          Long-only equities/ETFs · next-open fills · free Yahoo EOD data · USD
        </footer>
      </div>
    </BrowserRouter>
  )
}
