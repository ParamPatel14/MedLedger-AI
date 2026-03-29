import { motion, AnimatePresence } from 'framer-motion'
import { useMemo, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import RuleConflictViewer from '../components/RuleConflictViewer'
import RuleExplorer from '../components/RuleExplorer'
import RuleMonitoringDashboard from '../components/RuleMonitoringDashboard'
import { Button } from '../components/ui/button'
import { PageHeader } from '../components/ui/page-header'
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
    <>
      <PageHeader
        title="Rule Intelligence"
        subtitle="Monitor active rules, review updates, inspect conflicts, and explore by TPA or category."
        icon={ShieldCheck}
      />
      <div className="container pageContent">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
        >
          {/* Tab bar */}
          <div
            style={{
              display: 'flex',
              gap: 6,
              marginBottom: 24,
              background: 'white',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: 5,
              width: 'fit-content',
              boxShadow: 'var(--shadow-xs)',
            }}
          >
            {tabs.map((t) => (
              <Button
                key={t.id}
                variant={tab === t.id ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </Button>
            ))}
          </div>

          {/* Tab content */}
          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
            >
              {tab === 'monitoring' && <RuleMonitoringDashboard />}
              {tab === 'conflicts' && <RuleConflictViewer />}
              {tab === 'explorer' && <RuleExplorer />}
            </motion.div>
          </AnimatePresence>
        </motion.div>
      </div>
    </>
  )
}
