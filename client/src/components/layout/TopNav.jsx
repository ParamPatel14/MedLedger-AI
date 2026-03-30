import * as Avatar from '@radix-ui/react-avatar'
import { motion } from 'framer-motion'
import { Menu, PanelLeftClose, PanelLeftOpen, Search, Settings } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'

import { cn } from '../../lib/cn'
import { useAppStore } from '../../stores/appStore'
import { Button } from '../ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
import { Input } from '../ui/input'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/claim-processing', label: 'Claim Processing' },
  { to: '/denial-management', label: 'Denial Management' },
  { to: '/voice-agent', label: 'Voice Agent' },
  { to: '/rule-engine', label: 'Rule Engine' },
  { to: '/audit', label: 'Audit & Explain' },
]

function UserChip() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="inline-flex items-center gap-3 rounded-2xl border border-white/70 bg-white/55 px-3 py-2 shadow-[0_12px_50px_rgba(2,6,23,0.10)] outline-none transition hover:bg-white/75 focus-visible:ring-4 focus-visible:ring-[var(--ring)]">
          <Avatar.Root className="relative inline-flex size-9 overflow-hidden rounded-2xl border border-white/70 bg-gradient-to-br from-blue-500/25 via-violet-500/20 to-cyan-400/25 shadow-[0_12px_40px_rgba(2,6,23,0.12)]">
            <Avatar.Fallback className="grid h-full w-full place-items-center text-xs font-semibold text-slate-800">
              ML
            </Avatar.Fallback>
          </Avatar.Root>
          <div className="hidden text-left leading-tight sm:block">
            <div className="text-xs font-semibold text-slate-900">MedLedger Admin</div>
            <div className="text-[11px] text-slate-600">Enterprise</div>
          </div>
          <Settings className="hidden size-4 text-slate-700 sm:block" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Workspace</DropdownMenuLabel>
        <DropdownMenuItem onSelect={(e) => e.preventDefault()}>Settings</DropdownMenuItem>
        <DropdownMenuItem onSelect={(e) => e.preventDefault()}>Team</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={(e) => e.preventDefault()}>Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function MobileNav() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="glass" size="icon" className="lg:hidden">
          <Menu className="size-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Navigation</DialogTitle>
        </DialogHeader>
        <div className="mt-4 grid gap-2">
          {navItems.map((it) => {
            const active = location.pathname === it.to
            return (
              <button
                key={it.to}
                onClick={() => navigate(it.to)}
                className={cn(
                  'w-full rounded-2xl border border-[var(--border)] bg-white/60 px-4 py-3 text-left text-sm font-semibold text-slate-800 shadow-[0_12px_40px_rgba(2,6,23,0.08)] outline-none transition hover:bg-white/80 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
                  active && 'bg-gradient-to-br from-blue-50 via-white to-cyan-50',
                )}
              >
                {it.label}
              </button>
            )
          })}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function TopNav({ className }) {
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const MotionDiv = motion.div

  return (
    <div className={cn('sticky top-4 z-30 px-4', className)}>
      <div className="glass-panel rounded-[32px] px-4 py-3">
        <div className="flex items-center gap-3">
          <MobileNav />

          <Button
            variant="glass"
            size="icon"
            className="hidden lg:inline-flex"
            onClick={toggleSidebar}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </Button>

          <div className="hidden min-w-0 items-center gap-2 lg:flex">
            {navItems.slice(0, 3).map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-2xl px-3 py-2 text-xs font-semibold text-slate-700 outline-none transition hover:bg-white/70 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
                    isActive && 'bg-white text-slate-900 shadow-[0_12px_40px_rgba(2,6,23,0.10)]',
                  )
                }
              >
                {it.label}
              </NavLink>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden w-[360px] max-w-[44vw] items-center sm:flex">
              <div className="relative w-full">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                <Input className="pl-10" placeholder="Search claims, rules, calls…" />
              </div>
            </div>

            <MotionDiv initial={false} whileHover={{ y: -1 }} whileTap={{ y: 0 }}>
              <UserChip />
            </MotionDiv>
          </div>
        </div>
      </div>
    </div>
  )
}
