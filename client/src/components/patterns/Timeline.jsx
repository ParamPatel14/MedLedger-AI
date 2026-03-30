import { motion } from 'framer-motion'

import { Badge } from '../ui/badge'
import { cn } from '../../lib/cn'

function toneFor(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'success' || s === 'ok' || s === 'done') return { badge: 'success', dot: 'from-emerald-400 to-cyan-400' }
  if (s === 'warning' || s === 'needs_review' || s === 'warn') return { badge: 'warning', dot: 'from-amber-400 to-orange-400' }
  if (s === 'error' || s === 'failed') return { badge: 'error', dot: 'from-rose-500 to-fuchsia-500' }
  return { badge: 'neutral', dot: 'from-slate-300 to-slate-200' }
}

export function Timeline({ items = [], className }) {
  const MotionDiv = motion.div
  return (
    <div className={cn('relative', className)}>
      <div className="absolute left-[18px] top-2 h-[calc(100%-8px)] w-px bg-[var(--border-2)]" aria-hidden="true" />
      <div className="space-y-3">
        {items.map((it, idx) => {
          const tone = toneFor(it.status)
          return (
            <MotionDiv
              key={it.id || `${it.title}-${idx}`}
              whileHover={{ y: -1 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
              className="relative pl-12"
            >
              <div className={cn('absolute left-2 top-3 grid size-8 place-items-center rounded-2xl bg-gradient-to-br', tone.dot)}>
                <div className="size-3 rounded-full bg-white/80" />
              </div>
              <div className="rounded-[26px] border border-white/70 bg-white/55 p-4 shadow-[0_14px_50px_rgba(2,6,23,0.10)]">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-900">{it.title}</div>
                    {it.subtitle ? <div className="mt-1 text-xs text-slate-600">{it.subtitle}</div> : null}
                  </div>
                  <Badge variant={tone.badge}>{it.badgeLabel || it.status}</Badge>
                </div>
                {it.meta ? <div className="mt-3 text-xs text-slate-600">{it.meta}</div> : null}
              </div>
            </MotionDiv>
          )
        })}
      </div>
    </div>
  )
}
