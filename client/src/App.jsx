import { useMemo, useState } from 'react'
import './App.css'

function App() {
  const [apiState, setApiState] = useState('idle')
  const [apiMessage, setApiMessage] = useState('')

  const apiBadge = useMemo(() => {
    if (apiState === 'loading') return { label: 'Checking…', tone: 'neutral' }
    if (apiState === 'ok') return { label: 'Online', tone: 'success' }
    if (apiState === 'error') return { label: 'Offline', tone: 'danger' }
    return { label: 'Not checked', tone: 'neutral' }
  }, [apiState])

  const callApi = async () => {
    setApiState('loading')
    setApiMessage('')
    try {
      const res = await fetch('/api/hello/MedLedger')
      const data = await res.json()
      setApiMessage(data?.message ?? '')
      setApiState('ok')
    } catch {
      setApiMessage('Error contacting backend')
      setApiState('error')
    }
  }

  return (
    <div className="appShell">
      <header className="topBar">
        <div className="container topBarInner">
          <div className="brand">
            <div className="brandMark" aria-hidden="true"></div>
            <div className="brandText">
              <div className="brandName">MedLedger AI</div>
              <div className="brandTag">Medication traceability, simplified</div>
            </div>
          </div>

          <nav className="nav">
            <a className="navLink" href="#features">
              Features
            </a>
            <a className="navLink" href="#status">
              Status
            </a>
            <a className="navLink ctaLink" href="#get-started">
              Get started
            </a>
          </nav>
        </div>
      </header>

      <main className="container">
        <section className="heroSection" id="get-started">
          <div className="heroCopy">
            <h1 className="heroTitle">A secure ledger for medication movement</h1>
            <p className="heroSubtitle">
              Track meds from intake to dispense with an audit-friendly history
              that’s fast to query and easy for staff to use.
            </p>

            <div className="heroActions">
              <button className="btn btnPrimary" onClick={callApi}>
                Check backend connection
              </button>
              <a className="btn btnGhost" href="#features">
                See key features
              </a>
            </div>

            <div className="heroMeta">
              <span className={`badge badge-${apiBadge.tone}`}>
                API: {apiBadge.label}
              </span>
              <span className="metaText">Dev proxy: /api → 127.0.0.1:8000</span>
            </div>

            <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-200 ring-1 ring-emerald-400/25">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
              Tailwind is working
            </div>

            {apiMessage && <div className="callout">{apiMessage}</div>}
          </div>

          <div className="heroPanel" aria-hidden="true">
            <div className="panelCard">
              <div className="panelTitleRow">
                <div className="panelTitle">Ledger snapshot</div>
                <div className="panelPill">Encrypted</div>
              </div>
              <div className="panelGrid">
                <div className="panelStat">
                  <div className="panelStatLabel">New events</div>
                  <div className="panelStatValue">24</div>
                </div>
                <div className="panelStat">
                  <div className="panelStatLabel">Dispenses</div>
                  <div className="panelStatValue">7</div>
                </div>
                <div className="panelStat">
                  <div className="panelStatLabel">Checks</div>
                  <div className="panelStatValue">98%</div>
                </div>
                <div className="panelStat">
                  <div className="panelStatLabel">Alerts</div>
                  <div className="panelStatValue">0</div>
                </div>
              </div>
              <div className="panelFoot">
                <div className="spark">
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <div className="panelFootText">Real-time updates (dev)</div>
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="features">
          <div className="sectionHeader">
            <h2 className="sectionTitle">Designed for clinical workflows</h2>
            <p className="sectionSubtitle">
              Build on a simple API today, expand to full tracking tomorrow.
            </p>
          </div>

          <div className="grid3">
            <div className="card">
              <div className="cardTitle">Inventory movement</div>
              <div className="cardBody">
                Record receipts, transfers, adjustments, and dispenses as clean
                events.
              </div>
            </div>
            <div className="card">
              <div className="cardTitle">Audit-ready history</div>
              <div className="cardBody">
                Keep a human-readable trail for compliance and investigations.
              </div>
            </div>
            <div className="card">
              <div className="cardTitle">Fast search</div>
              <div className="cardBody">
                Find by patient, medication, lot, or location in seconds.
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="status">
          <div className="sectionHeader">
            <h2 className="sectionTitle">Environment status</h2>
            <p className="sectionSubtitle">
              Quick checks while you build out endpoints.
            </p>
          </div>

          <div className="grid2">
            <div className="card">
              <div className="cardTitle">Backend</div>
              <div className="cardBody">
                Running on <span className="mono">http://127.0.0.1:8000</span>
              </div>
              <div className="cardActions">
                <button className="btn btnSecondary" onClick={callApi}>
                  Ping API
                </button>
              </div>
            </div>
            <div className="card">
              <div className="cardTitle">Frontend</div>
              <div className="cardBody">
                Running on <span className="mono">http://localhost:5173</span>
              </div>
              <div className="cardActions">
                <a className="btn btnSecondary" href="#get-started">
                  Back to top
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container footerInner">
          <div className="footerLeft">© {new Date().getFullYear()} MedLedger AI</div>
          <div className="footerRight">
            <span className="muted">Theme: Clinical Dark</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
