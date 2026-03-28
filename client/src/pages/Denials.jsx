import DenialRecoveryPanel from '../components/DenialRecoveryPanel'
import '../App.css'

export default function Denials() {
  return (
    <div className="container">
      <section className="section">
        <div className="sectionHeader">
          <h2 className="sectionTitle">Business Impact Dashboard</h2>
          <p className="sectionSubtitle">Revenue recovered, denial reduction, and automation metrics.</p>
        </div>
        <DenialRecoveryPanel />
      </section>
    </div>
  )
}
