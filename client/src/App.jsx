import { useEffect, useState } from 'react'
import Extract from './pages/Extract'
import Denials from './pages/Denials'
import Rules from './pages/Rules'
import AgentWorkflowPanel from './components/AgentWorkflowPanel'
import ClaimExplanationPanel from './components/ClaimExplanationPanel'
import './App.css'

function LandingFlowChart() {
  return (
    <svg
      className="flowSvg"
      viewBox="0 0 1400 860"
      role="img"
      aria-labelledby="flowTitle flowDesc"
      preserveAspectRatio="xMidYMid meet"
    >
      <title id="flowTitle">MedLedger AI claims automation flow</title>
      <desc id="flowDesc">
        Medical record to clinical agent, SVM verification, coding agent, SVM verification, rule agent, SVM verification,
        decision governor with approve or block and claim status loop with denial agent. Explainability and audit connects
        to key agents.
      </desc>
      <defs>
        <linearGradient id="nodeBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="rgba(255,255,255,0.92)" />
          <stop offset="1" stopColor="rgba(241,245,255,0.78)" />
        </linearGradient>
        <linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="rgba(37,99,235,0.85)" />
          <stop offset="0.5" stopColor="rgba(124,58,237,0.72)" />
          <stop offset="1" stopColor="rgba(6,182,212,0.75)" />
        </linearGradient>
        <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
          <path d="M 0 0 L 12 6 L 0 12 z" fill="rgba(37, 99, 235, 0.85)" />
        </marker>
        <radialGradient id="spot" cx="50%" cy="35%" r="70%">
          <stop offset="0" stopColor="rgba(255,255,255,0.9)" />
          <stop offset="1" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
        <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="10" stdDeviation="10" floodColor="rgba(2,6,23,0.18)" />
        </filter>
      </defs>

      <rect x="22" y="22" width="1356" height="816" rx="28" fill="rgba(255,255,255,0.34)" stroke="rgba(148,163,184,0.30)" />

      <g className="flowEdges">
        <path className="flowEdge" d="M 270 115 L 310 115" stroke="url(#edge)" strokeWidth="3" fill="none" markerEnd="url(#arrow)" />
        <path className="flowEdge" d="M 500 115 L 540 115" stroke="url(#edge)" strokeWidth="3" fill="none" markerEnd="url(#arrow)" />
        <path className="flowEdge" d="M 690 115 L 730 115" stroke="url(#edge)" strokeWidth="3" fill="none" markerEnd="url(#arrow)" />
        <path className="flowEdge" d="M 920 115 L 960 115" stroke="url(#edge)" strokeWidth="3" fill="none" markerEnd="url(#arrow)" />
        <path
          className="flowEdge"
          d="M 1030 138 C 1010 190 960 210 830 245 L 830 245"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />

        <path className="flowEdge" d="M 830 245 L 870 245" stroke="url(#edge)" strokeWidth="3" fill="none" markerEnd="url(#arrow)" />
        <path
          className="flowEdge"
          d="M 1020 245 C 1060 260 1065 290 1060 330 C 1055 370 950 388 820 390"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />

        <path
          className="flowEdge"
          d="M 700 406 C 660 430 610 448 510 492"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />
        <path
          className="flowEdge"
          d="M 700 406 C 760 432 820 448 925 492"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />

        <path
          className="flowEdge"
          d="M 405 524 C 470 560 540 585 640 610"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />
        <path
          className="flowEdge"
          d="M 995 524 C 930 560 850 585 760 610"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />

        <path
          className="flowEdge"
          d="M 700 660 C 700 690 650 715 510 732"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />
        <path
          className="flowEdge"
          d="M 700 660 C 705 690 760 712 860 722"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />

        <path className="flowEdge" d="M 970 754 L 970 774" stroke="url(#edge)" strokeWidth="3" fill="none" markerEnd="url(#arrow)" />
        <path
          className="flowEdge"
          d="M 970 828 C 960 800 930 770 880 750 C 820 726 780 710 740 664"
          stroke="url(#edge)"
          strokeWidth="3"
          fill="none"
          markerEnd="url(#arrow)"
        />

        <path
          className="flowEdge flowEdge--audit"
          d="M 330 255 C 380 195 460 160 430 140"
          stroke="rgba(15, 23, 42, 0.30)"
          strokeWidth="2.5"
          strokeDasharray="10 10"
          fill="none"
          markerEnd="url(#arrow)"
        />
        <path
          className="flowEdge flowEdge--audit"
          d="M 330 255 C 450 190 600 165 800 140"
          stroke="rgba(15, 23, 42, 0.30)"
          strokeWidth="2.5"
          strokeDasharray="10 10"
          fill="none"
          markerEnd="url(#arrow)"
        />
        <path
          className="flowEdge flowEdge--audit"
          d="M 330 255 C 470 240 560 250 640 245"
          stroke="rgba(15, 23, 42, 0.30)"
          strokeWidth="2.5"
          strokeDasharray="10 10"
          fill="none"
          markerEnd="url(#arrow)"
        />
        <path
          className="flowEdge flowEdge--audit"
          d="M 330 255 C 440 300 550 325 580 368"
          stroke="rgba(15, 23, 42, 0.30)"
          strokeWidth="2.5"
          strokeDasharray="10 10"
          fill="none"
          markerEnd="url(#arrow)"
        />

        <text x="580" y="455" className="flowEdgeLabel">
          Approve
        </text>
        <text x="770" y="455" className="flowEdgeLabel">
          Block / Escalate
        </text>
        <text x="560" y="700" className="flowEdgeLabel">
          Approved
        </text>
        <text x="760" y="700" className="flowEdgeLabel">
          Denied
        </text>
      </g>

      <g filter="url(#soft)" className="flowNodes">
        <g className="flowNode">
          <rect x="80" y="80" width="190" height="70" rx="22" fill="url(#nodeBg)" stroke="rgba(148,163,184,0.55)" />
          <rect x="80" y="80" width="190" height="70" rx="22" fill="url(#spot)" opacity="0.55" />
          <text x="175" y="112" textAnchor="middle" className="flowNodeTitle">
            Medical Record
          </text>
          <text x="175" y="134" textAnchor="middle" className="flowNodeSub">
            intake + OCR
          </text>
        </g>

        <g className="flowNode">
          <rect x="310" y="80" width="190" height="70" rx="22" fill="url(#nodeBg)" stroke="rgba(148,163,184,0.55)" />
          <rect x="310" y="80" width="190" height="70" rx="22" fill="url(#spot)" opacity="0.55" />
          <text x="405" y="120" textAnchor="middle" className="flowNodeTitle">
            Clinical Agent
          </text>
        </g>

        <g className="flowNode">
          <rect x="540" y="92" width="150" height="46" rx="18" fill="rgba(255,255,255,0.78)" stroke="rgba(37,99,235,0.35)" />
          <text x="615" y="121" textAnchor="middle" className="flowNodeChip">
            SVM Verification
          </text>
        </g>

        <g className="flowNode">
          <rect x="730" y="80" width="190" height="70" rx="22" fill="url(#nodeBg)" stroke="rgba(148,163,184,0.55)" />
          <rect x="730" y="80" width="190" height="70" rx="22" fill="url(#spot)" opacity="0.55" />
          <text x="825" y="120" textAnchor="middle" className="flowNodeTitle">
            Coding Agent
          </text>
        </g>

        <g className="flowNode">
          <rect x="960" y="92" width="150" height="46" rx="18" fill="rgba(255,255,255,0.78)" stroke="rgba(124,58,237,0.35)" />
          <text x="1035" y="121" textAnchor="middle" className="flowNodeChip">
            SVM Verification
          </text>
        </g>

        <g className="flowNode">
          <rect x="640" y="210" width="190" height="70" rx="22" fill="url(#nodeBg)" stroke="rgba(148,163,184,0.55)" />
          <rect x="640" y="210" width="190" height="70" rx="22" fill="url(#spot)" opacity="0.55" />
          <text x="735" y="250" textAnchor="middle" className="flowNodeTitle">
            Rule Agent
          </text>
        </g>

        <g className="flowNode">
          <rect x="870" y="222" width="150" height="46" rx="18" fill="rgba(255,255,255,0.78)" stroke="rgba(6,182,212,0.38)" />
          <text x="945" y="251" textAnchor="middle" className="flowNodeChip">
            SVM Verification
          </text>
        </g>

        <g className="flowNode">
          <rect x="580" y="330" width="240" height="76" rx="26" fill="url(#nodeBg)" stroke="rgba(148,163,184,0.55)" />
          <rect x="580" y="330" width="240" height="76" rx="26" fill="url(#spot)" opacity="0.55" />
          <text x="700" y="366" textAnchor="middle" className="flowNodeTitle">
            Decision Governor
          </text>
          <text x="700" y="388" textAnchor="middle" className="flowNodeSub">
            approve • block • escalate
          </text>
        </g>

        <g className="flowNode">
          <rect x="300" y="460" width="210" height="64" rx="22" fill="rgba(255,255,255,0.85)" stroke="rgba(37,99,235,0.35)" />
          <text x="405" y="498" textAnchor="middle" className="flowNodeTitle">
            Submit Claim
          </text>
        </g>

        <g className="flowNode">
          <rect x="860" y="460" width="240" height="64" rx="22" fill="rgba(255,255,255,0.85)" stroke="rgba(225,29,72,0.28)" />
          <text x="980" y="488" textAnchor="middle" className="flowNodeTitle">
            Review / Fix
          </text>
          <text x="980" y="510" textAnchor="middle" className="flowNodeSub">
            operator workflow
          </text>
        </g>

        <g className="flowNode">
          <polygon
            points="700,560 762,610 700,660 638,610"
            fill="rgba(255,255,255,0.85)"
            stroke="rgba(148,163,184,0.55)"
            strokeWidth="2"
          />
          <text x="700" y="612" textAnchor="middle" className="flowNodeTitle">
            Claim Status
          </text>
        </g>

        <g className="flowNode">
          <rect x="300" y="700" width="210" height="64" rx="22" fill="rgba(255,255,255,0.85)" stroke="rgba(16,163,74,0.30)" />
          <text x="405" y="738" textAnchor="middle" className="flowNodeTitle">
            Done
          </text>
        </g>

        <g className="flowNode">
          <rect x="860" y="690" width="220" height="64" rx="22" fill="rgba(255,255,255,0.85)" stroke="rgba(217,119,6,0.34)" />
          <text x="970" y="728" textAnchor="middle" className="flowNodeTitle">
            Denial Agent
          </text>
        </g>

        <g className="flowNode">
          <rect x="860" y="774" width="220" height="64" rx="22" fill="rgba(255,255,255,0.85)" stroke="rgba(124,58,237,0.32)" />
          <text x="970" y="804" textAnchor="middle" className="flowNodeTitle">
            Fix &amp; Resubmit
          </text>
          <text x="970" y="826" textAnchor="middle" className="flowNodeSub">
            loop back
          </text>
        </g>

        <g className="flowNode">
          <rect x="80" y="210" width="250" height="76" rx="26" fill="rgba(255,255,255,0.86)" stroke="rgba(148,163,184,0.55)" />
          <rect x="80" y="210" width="250" height="76" rx="26" fill="url(#spot)" opacity="0.55" />
          <text x="205" y="245" textAnchor="middle" className="flowNodeTitle">
            Explainability + Audit
          </text>
          <text x="205" y="267" textAnchor="middle" className="flowNodeSub">
            trace • evidence • confidence
          </text>
        </g>
      </g>
    </svg>
  )
}

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
                  Automatically extract diagnoses, procedures, and medications from clinical notes using scispaCy,
                  rapidfuzz, and Gemini fallbacks.
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
                  <a className="btn btnGhost" href="#flow">
                    View Flowchart
                  </a>
                </div>
                <div className="heroMeta">
                  <div className="heroPill">Audit-ready trace</div>
                  <div className="heroPill">3× verification gates</div>
                  <div className="heroPill">Denial loop closure</div>
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

            <section className="section flowSection" id="flow">
              <div className="sectionHeader">
                <h2 className="sectionTitle">End-to-end claim automation flow</h2>
                <p className="sectionSubtitle">
                  A clear, audit-ready pipeline: clinical extraction → verification → coding → verification → rules → verification → decision → outcome loop.
                </p>
              </div>
              <div className="flowCard">
                <div className="flowKpis">
                  <div className="flowKpi">
                    <div className="flowKpiLabel">Verified steps</div>
                    <div className="flowKpiValue">3× SVM</div>
                  </div>
                  <div className="flowKpi">
                    <div className="flowKpiLabel">Governance</div>
                    <div className="flowKpiValue">Approve / Block</div>
                  </div>
                  <div className="flowKpi">
                    <div className="flowKpiLabel">Loop closure</div>
                    <div className="flowKpiValue">Fix → Resubmit</div>
                  </div>
                </div>
                <div className="flowHint">Clear workflow view (audit links shown as dashed lines).</div>
                <LandingFlowChart />
              </div>
            </section>

            <section className="section" id="features">
              <div className="sectionHeader">
                <h2 className="sectionTitle">Designed for hospital workflows</h2>
                <p className="sectionSubtitle">Built with healthcare professionals in mind, leveraging modern NLP.</p>
              </div>
              <div className="grid3">
                <div className="card">
                  <div className="cardTitle">Medical Models</div>
                  <div className="cardBody">
                    Powered by scispaCy&apos;s en_core_sci_md model for accurate biomedical entity recognition.
                  </div>
                </div>
                <div className="card">
                  <div className="cardTitle">External Dictionaries</div>
                  <div className="cardBody">Dynamic loading of ICD-10 and RxNorm terms without hardcoding.</div>
                </div>
                <div className="card">
                  <div className="cardTitle">Fuzzy Matching &amp; Fallback</div>
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
