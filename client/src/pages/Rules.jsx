import { useMemo, useState } from 'react'
import RuleConflictViewer from '../components/RuleConflictViewer'
import RuleExplorer from '../components/RuleExplorer'
import RuleMonitoringDashboard from '../components/RuleMonitoringDashboard'
import '../App.css'

export default function Rules() {
  const [tab, setTab] = useState('monitoring')
  const tabs = useMemo(
    () => [
      { id: 'monitoring', label: 'Rule Monitoring' },
      { id: 'conflicts', label: 'Conflict Viewer' },
      { id: 'explorer', label: 'Rule Explorer' },
    ],
    [],
  )

  return (
    <div className="container">
      <section className="section">
        <div className="sectionHeader">
          <h2 className="sectionTitle">Rule Intelligence</h2>
          <p className="sectionSubtitle">Monitor active rules, review updates, inspect conflicts, and explore by TPA/category.</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`btn ${tab === t.id ? 'btnPrimary' : 'btnGhost'}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="mt-4">
          {tab === 'monitoring' && <RuleMonitoringDashboard />}
          {tab === 'conflicts' && <RuleConflictViewer />}
          {tab === 'explorer' && <RuleExplorer />}
        </div>
      </section>
    </div>
  )
}

