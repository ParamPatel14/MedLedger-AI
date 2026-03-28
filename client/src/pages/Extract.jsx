import ClinicalExtractorPanel from '../components/ClinicalExtractorPanel'
import AgentWorkflowPanel from '../components/AgentWorkflowPanel'
import ClaimExplanationPanel from '../components/ClaimExplanationPanel'
import TermCatalogPanel from '../components/TermCatalogPanel'
import '../App.css'

export default function Extract() {
  return (
    <div className="container">
      <section className="section">
        <div className="sectionHeader">
          <h2 className="sectionTitle">Clinical Extraction</h2>
          <p className="sectionSubtitle">
            Upload documents or prescriptions, or paste text to extract diagnoses, procedures, and medications.
          </p>
        </div>
        <ClinicalExtractorPanel />
        <AgentWorkflowPanel />
        <ClaimExplanationPanel />
        <TermCatalogPanel />
      </section>
    </div>
  )
}
