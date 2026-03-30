import { cva } from 'class-variance-authority'

import { cn } from '../../lib/cn'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-[-0.01em]',
  {
    variants: {
      variant: {
        neutral: 'border-[var(--border)] bg-white/70 text-slate-700',
        info: 'border-blue-200/70 bg-blue-50/70 text-blue-700',
        success: 'border-emerald-200/70 bg-emerald-50/70 text-emerald-700',
        warning: 'border-amber-200/70 bg-amber-50/70 text-amber-800',
        error: 'border-rose-200/70 bg-rose-50/70 text-rose-700',
      },
    },
    defaultVariants: {
      variant: 'neutral',
    },
  },
)

function Badge({ className, variant, ...props }) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge }
