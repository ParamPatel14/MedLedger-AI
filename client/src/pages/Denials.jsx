import DenialRecoveryPanel from '../components/DenialRecoveryPanel'
import '../App.css'

export default function Denials() {
  return (
    <div className="container">
      <section className="section">
        <div className="sectionHeader">
          <h2 className="sectionTitle">Denial Recovery Dashboard</h2>
          <p className="sectionSubtitle">Monitor denied claims, recovery progress, and recovered revenue.</p>
        </div>
        <DenialRecoveryPanel />
      </section>
    </div>
  )
}

