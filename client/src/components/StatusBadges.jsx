import { useMemo } from 'react'

export default function StatusBadges({ apiState, dbState }) {
  const apiBadge = useMemo(() => {
    if (apiState === 'loading') return { label: 'Checking…', tone: 'neutral' }
    if (apiState === 'ok') return { label: 'Online', tone: 'success' }
    if (apiState === 'error') return { label: 'Offline', tone: 'danger' }
    return { label: 'Not checked', tone: 'neutral' }
  }, [apiState])

  const dbBadge = useMemo(() => {
    if (dbState === 'loading') return { label: 'Checking…', tone: 'neutral' }
    if (dbState === 'ok') return { label: 'Online', tone: 'success' }
    if (dbState === 'error') return { label: 'Offline', tone: 'danger' }
    return { label: 'Not checked', tone: 'neutral' }
  }, [dbState])

  return (
    <div className="heroMeta">
      <span className={`badge badge-${apiBadge.tone}`}>API: {apiBadge.label}</span>
      <span className={`badge badge-${dbBadge.tone}`}>DB: {dbBadge.label}</span>
      <span className="metaText">Dev proxy: /api → 127.0.0.1:8000</span>
    </div>
  )
}

