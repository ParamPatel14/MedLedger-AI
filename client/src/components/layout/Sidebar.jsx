import { motion } from 'framer-motion'
import {
  Activity,
  FileText,
  Gauge,
  PhoneCall,
  ScanSearch,
  ShieldAlert,
  SlidersHorizontal,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { useAppStore } from '../../stores/appStore'

const navItems = [
  { to: '/', label: 'Dashboard', icon: Gauge },
  { to: '/claim-processing', label: 'Claim Processing', icon: FileText },
  { to: '/denial-management', label: 'Denial Management', icon: ShieldAlert },
  { to: '/voice-agent', label: 'Voice Agent', icon: PhoneCall },
  { to: '/rule-engine', label: 'Rule Engine', icon: SlidersHorizontal },
  { to: '/audit', label: 'Audit & Explain', icon: ScanSearch },
]

function BrandMark() {
  return (
    <div className="relative grid size-10 place-items-center overflow-hidden rounded-2xl border border-white/60 bg-white/50 shadow-[0_18px_60px_rgba(2,6,23,0.12)]">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/35 via-violet-500/30 to-cyan-400/35" />
      <div className="absolute inset-0 opacity-70 [mask-image:radial-gradient(circle_at_30%_20%,black,transparent_60%)] bg-white" />
      <Activity className="relative size-5 text-slate-900/85" />
    </div>
  )
}

export function Sidebar({ className }) {
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  const MotionAside = motion.aside

  return (
    <MotionAside
      className={cn('hidden lg:block', className)}
      initial={false}
      animate={{ width: collapsed ? 88 : 292 }}
      transition={{ type: 'spring', stiffness: 320, damping: 30 }}
    >
      <div className="sticky top-4 h-[calc(100svh-32px)] px-4">
        <div className="glass-panel h-full rounded-[32px] p-4">
          <div className="flex items-center gap-3 px-2 pt-1">
            <BrandMark />
            <div className={cn('flex flex-col leading-tight', collapsed && 'hidden')}>
              <div className="text-sm font-semibold tracking-[-0.02em] text-slate-900">MedLedger AI</div>
              <div className="text-xs text-slate-600">Enterprise Claims Ops</div>
            </div>
          </div>

          <div className="mt-6 space-y-1">
            {navItems.map((it) => {
              const Icon = it.icon
              return (
                <NavLink
                  key={it.to}
                  to={it.to}
                  className={({ isActive }) =>
                    cn(
                      'group relative flex items-center gap-3 rounded-2xl px-3 py-3 text-sm font-semibold text-slate-700 outline-none transition hover:bg-white/70 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
                      isActive && 'bg-white text-slate-900 shadow-[0_18px_60px_rgba(2,6,23,0.12)]',
                    )
                  }
                >
                  <div className="grid size-10 place-items-center rounded-2xl border border-white/70 bg-white/45 shadow-[0_10px_40px_rgba(2,6,23,0.08)]">
                    <Icon className="size-4" />
                  </div>
                  <div className={cn('truncate', collapsed && 'hidden')}>{it.label}</div>
                  {collapsed && (
                    <div className="pointer-events-none absolute left-[86px] z-50 hidden w-max rounded-2xl border border-white/70 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-800 shadow-[0_30px_90px_rgba(2,6,23,0.16)] backdrop-blur-xl group-hover:block">
                      {it.label}
                    </div>
                  )}
                </NavLink>
              )
            })}
          </div>

          <div className="mt-auto flex items-center gap-3 px-2 pt-6">
            <div className="h-px flex-1 bg-white/70" />
          </div>
          <div className={cn('px-2 pt-3', collapsed && 'hidden')}>
            <div className="rounded-[26px] border border-white/70 bg-gradient-to-br from-blue-50/80 via-white/70 to-cyan-50/80 p-4 shadow-[0_18px_60px_rgba(2,6,23,0.10)]">
              <div className="text-sm font-semibold text-slate-900">Ops pulse</div>
              <div className="mt-1 text-xs text-slate-600">Live denials + agent trace</div>
              <div className="mt-3 flex items-center gap-2">
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200/70">
                  <div className="h-full w-[72%] rounded-full bg-gradient-to-r from-blue-500 via-violet-500 to-cyan-400" />
                </div>
                <div className="text-xs font-semibold tabular-nums text-slate-800">72%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </MotionAside>
  )
}
