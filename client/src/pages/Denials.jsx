import { motion } from 'framer-motion'
import { BarChart3 } from 'lucide-react'
import DenialRecoveryPanel from '../components/DenialRecoveryPanel'
import { PageHeader } from '../components/ui/page-header'
import '../App.css'

export default function Denials() {
  return (
    <>
      <PageHeader
        title="Business Impact Dashboard"
        subtitle="Revenue recovered, denial reduction, and automation metrics."
        icon={BarChart3}
      />
      <div className="container pageContent">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
        >
          <DenialRecoveryPanel />
        </motion.div>
      </div>
    </>
  )
}
