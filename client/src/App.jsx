import ClinicalExtractorPanel from './components/ClinicalExtractorPanel'
import TermCatalogPanel from './components/TermCatalogPanel'
import './App.css'

function App() {
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
            <a className="navLink ctaLink" href="#extraction-panel">
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
              <a className="btn btnPrimary" href="#extraction-panel">
                Start Extraction
              </a>
              <a className="btn btnGhost" href="#features">
                Explore Features
              </a>
            </div>

            <div id="extraction-panel" className="mt-8">
              <ClinicalExtractorPanel />
              <TermCatalogPanel />
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
