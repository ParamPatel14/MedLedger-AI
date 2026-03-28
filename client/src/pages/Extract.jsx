import ClinicalExtractorPanel from '../components/ClinicalExtractorPanel'
import '../App.css'

export default function Extract() {
  return (
    <div className="container">
      <section className="section">
        <div className="sectionHeader">
          <h2 className="sectionTitle">Claim Processing</h2>
          <p className="sectionSubtitle">
            Upload a record or paste text to extract structured data and ICD-10 codes.
          </p>
        </div>
        <ClinicalExtractorPanel />
      </section>
    </div>
  )
}
