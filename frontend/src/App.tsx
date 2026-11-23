import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { ComparePage } from './pages/ComparePage'
import { ConfigurePage } from './pages/ConfigurePage'
import { ResultsPage } from './pages/ResultsPage'
import { SavedRunsPage } from './pages/SavedRunsPage'
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
              <div className="brand-sub">
                Historical test with risk limits · walk-forward · benchmarks
              </div>
            </div>
          </div>
          <nav>
            <NavLink to="/" end>
              Configure
            </NavLink>
            <NavLink to="/compare">Compare</NavLink>
            <NavLink to="/runs">Saved runs</NavLink>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<ConfigurePage />} />
            <Route path="/results/:runId" element={<ResultsPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/runs" element={<SavedRunsPage />} />
          </Routes>
        </main>
        <footer className="foot">
          Stocks &amp; ETFs only · priced at next day’s open · free end-of-day data · USD · long-only
        </footer>
      </div>
    </BrowserRouter>
  )
}
