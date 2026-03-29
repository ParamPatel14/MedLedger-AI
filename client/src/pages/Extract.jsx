import { motion } from 'framer-motion'
import { FileText } from 'lucide-react'
import ClinicalExtractorPanel from '../components/ClinicalExtractorPanel'
import { PageHeader } from '../components/ui/page-header'
import '../App.css'

export default function Extract() {
  return (
    <>
      <PageHeader
        title="Claim Processing"
        subtitle="Upload a record or paste clinical text to extract structured data and ICD-10 codes."
        icon={FileText}
      />
      <div className="container pageContent">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
        >
          <ClinicalExtractorPanel />
        </motion.div>
      </div>
    </>
  )
}
