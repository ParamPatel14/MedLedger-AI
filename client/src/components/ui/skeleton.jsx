import { cn } from '../../lib/cn'

function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-2xl bg-gradient-to-r from-slate-200/60 via-white/60 to-slate-200/60',
        className,
      )}
      {...props}
    />
  )
}

export { Skeleton }

