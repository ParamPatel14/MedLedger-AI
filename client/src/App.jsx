import { useEffect, useState } from 'react'
import Extract from './pages/Extract'
import Denials from './pages/Denials'
import Rules from './pages/Rules'
import AgentWorkflowPanel from './components/AgentWorkflowPanel'
import ClaimExplanationPanel from './components/ClaimExplanationPanel'
import './App.css'

function App() {
  const [path, setPath] = useState(window.location.pathname || '/')
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname || '/')
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const navigate = (to) => {
    if (to === path) return
    window.history.pushState({}, '', to)
    setPath(to)
  }

  const isClaim = path === '/claim' || path === '/extract'
  const isFlow = path === '/flow'
  const isVerify = path === '/verify'
  const isImpact = path === '/impact' || path === '/denials'
  const isRules = path === '/rules'
  const isHome = !(isClaim || isFlow || isVerify || isImpact || isRules)

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
            <a
              className={`navLink ${isClaim ? 'active' : ''}`}
              href="/claim"
              onClick={(e) => {
                e.preventDefault()
                navigate('/claim')
              }}
            >
              Claim Processing
            </a>
            <a
              className={`navLink ${isFlow ? 'active' : ''}`}
              href="/flow"
              onClick={(e) => {
                e.preventDefault()
                navigate('/flow')
              }}
            >
              Agent Flow
            </a>
            <a
              className={`navLink ${isVerify ? 'active' : ''}`}
              href="/verify"
              onClick={(e) => {
                e.preventDefault()
                navigate('/verify')
              }}
            >
              Verification
            </a>
            <a
              className={`navLink ${isImpact ? 'active' : ''}`}
              href="/impact"
              onClick={(e) => {
                e.preventDefault()
                navigate('/impact')
              }}
            >
              Impact
            </a>
            <a
              className={`navLink ${isRules ? 'active' : ''}`}
              href="/rules"
              onClick={(e) => {
                e.preventDefault()
                navigate('/rules')
              }}
            >
              Rules
            </a>
            <a
              className="navLink"
              href="/"
              onClick={(e) => {
                e.preventDefault()
                navigate('/')
              }}
            >
              Home
            </a>
          </nav>
        </div>
      </header>

      <main>
        {isHome && (
          <div className="container">
            <section className="heroSection" id="get-started">
              <div className="heroCopy">
                <h1 className="heroTitle">Advanced clinical text understanding</h1>
                <p className="heroSubtitle">
                  Automatically extract diagnoses, procedures, and medications from clinical notes using scispaCy, rapidfuzz, and Gemini fallbacks.
                </p>
                <div className="heroActions">
                  <a
                    className="btn btnPrimary"
                    href="/claim"
                    onClick={(e) => {
                      e.preventDefault()
                      navigate('/claim')
                    }}
                  >
                    Start Demo
                  </a>
                  <a className="btn btnGhost" href="#features">
                    Explore Features
                  </a>
                </div>
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
          </div>
        )}
        {isClaim && <Extract />}
        {isFlow && (
          <div className="container">
            <section className="section">
              <div className="sectionHeader">
                <h2 className="sectionTitle">Agent Flow Visualization</h2>
                <p className="sectionSubtitle">Clinical → Coding → Rule → Final (with confidence).</p>
              </div>
              <AgentWorkflowPanel view="flow" />
            </section>
          </div>
        )}
        {isVerify && (
          <div className="container">
            <section className="section">
              <div className="sectionHeader">
                <h2 className="sectionTitle">Verification + Guardrails</h2>
                <p className="sectionSubtitle">SVM results, policy decisions, and alerts.</p>
              </div>
              <AgentWorkflowPanel view="verification" />
              <ClaimExplanationPanel />
            </section>
          </div>
        )}
        {isImpact && <Denials />}
        {isRules && <Rules />}
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
