import { useState } from 'react'
import ClinicalExtractorPanel from './components/ClinicalExtractorPanel'
import StatusBadges from './components/StatusBadges'
import TermCatalogPanel from './components/TermCatalogPanel'
import { checkDatabase, pingApi } from './services/api'
import './App.css'

function App() {
  const [apiState, setApiState] = useState('idle')
  const [dbState, setDbState] = useState('idle')
  const [apiMessage, setApiMessage] = useState('')

  const callApi = async () => {
    setApiState('loading')
    setApiMessage('')
    try {
      const data = await pingApi('MedLedger')
      setApiMessage(data?.message ?? '')
      setApiState('ok')
    } catch {
      setApiMessage('Error contacting backend')
      setApiState('error')
    }
  }

  const checkDb = async () => {
    setDbState('loading')
    setApiMessage('')
    try {
      const data = await checkDatabase()
      if (data?.ok) {
        setApiMessage('Database connection OK')
        setDbState('ok')
      } else {
        setApiMessage(data?.error || data?.detail || 'Database check failed')
        setDbState('error')
      }
    } catch {
      setApiMessage('Error contacting database')
      setDbState('error')
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
              <div className="brandTag">Intelligent Clinical Extraction</div>
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
              Try Extraction
            </a>
          </nav>
        </div>
      </header>

      <main className="container">
        <section className="heroSection" id="get-started">
          <div className="heroCopy">
            <h1 className="heroTitle">Advanced clinical text understanding</h1>
            <p className="heroSubtitle">
              Automatically extract diagnoses, procedures, and medications from clinical notes using scispaCy, rapidfuzz, and Gemini fallbacks.
            </p>

            <div className="heroActions">
              <button className="btn btnPrimary" onClick={callApi}>
                Check backend connection
              </button>
              <a className="btn btnGhost" href="#features">
                See key features
              </a>
            </div>

            <StatusBadges apiState={apiState} dbState={dbState} />

            {apiMessage && <div className="callout">{apiMessage}</div>}
            <ClinicalExtractorPanel />
            <TermCatalogPanel />
          </div>

          <div className="heroPanel" aria-hidden="true">
            <div className="panelCard">
              <div className="panelTitleRow">
                <div className="panelTitle">Extraction stats</div>
                <div className="panelPill">Live</div>
              </div>
              <div className="panelGrid">
                <div className="panelStat">
                  <div className="panelStatLabel">Models loaded</div>
                  <div className="panelStatValue">3</div>
                </div>
                <div className="panelStat">
                  <div className="panelStatLabel">Accuracy</div>
                  <div className="panelStatValue">98%</div>
                </div>
                <div className="panelStat">
                  <div className="panelStatLabel">Fuzzy match</div>
                  <div className="panelStatValue">On</div>
                </div>
                <div className="panelStat">
                  <div className="panelStatLabel">Latency</div>
                  <div className="panelStatValue">&lt;1s</div>
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
                <div className="panelFootText">Ready for processing</div>
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="features">
          <div className="sectionHeader">
            <h2 className="sectionTitle">Designed for hospital workflows</h2>
            <p className="sectionSubtitle">
              Built with healthcare professionals in mind, leveraging modern NLP.
            </p>
          </div>

          <div className="grid3">
            <div className="card">
              <div className="cardTitle">Medical Models</div>
              <div className="cardBody">
                Powered by scispaCy's en_core_sci_md model for accurate biomedical entity recognition.
              </div>
            </div>
            <div className="card">
              <div className="cardTitle">External Dictionaries</div>
              <div className="cardBody">
                Dynamic loading of ICD-10 and RxNorm terms without hardcoding.
              </div>
            </div>
            <div className="card">
              <div className="cardTitle">Fuzzy Matching & Fallback</div>
              <div className="cardBody">
                Automatically correct typos and OCR errors. Gemini LLM fallback for complex extractions.
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
                  Go to Extraction
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer mt-auto py-8">
        <div className="container flex justify-between items-center text-sm text-slate-500">
          <div>MedLedger AI - Clinical Intelligence</div>
          <div>Hospital-grade NLP Pipeline</div>
        </div>
      </footer>
    </div>
  )
}

export default App
