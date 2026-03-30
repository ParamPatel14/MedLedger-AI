import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Outlet, useLocation } from 'react-router-dom'

import { Sidebar } from './Sidebar'
import { TopNav } from './TopNav'

export function AppShell() {
  const location = useLocation()
  const reduceMotion = useReducedMotion()
  const MotionDiv = motion.div

  return (
    <div className="min-h-svh">
      <div className="mx-auto flex w-full max-w-[1600px] gap-4 px-2 py-4 md:px-4">
        <Sidebar />
        <div className="min-w-0 flex-1">
          <TopNav />
          <div className="px-4 pb-10 pt-6">
            <AnimatePresence mode="wait">
              <MotionDiv
                key={location.pathname}
                initial={reduceMotion ? false : { opacity: 0, y: 10, filter: 'blur(6px)' }}
                animate={reduceMotion ? { opacity: 1 } : { opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8, filter: 'blur(6px)' }}
                transition={{ duration: 0.22, ease: 'easeOut' }}
              >
                <Outlet />
              </MotionDiv>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
