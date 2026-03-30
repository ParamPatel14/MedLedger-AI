import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'

import { cn } from '../../lib/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl text-sm font-semibold transition will-change-transform outline-none disabled:pointer-events-none disabled:opacity-50 focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
  {
    variants: {
      variant: {
        default:
          'bg-gradient-to-br from-[color:var(--primary)] via-[color:var(--primary-2)] to-[color:var(--primary-3)] text-white shadow-[0_18px_60px_rgba(2,6,23,0.20)] hover:translate-y-[-1px] hover:shadow-[0_26px_70px_rgba(2,6,23,0.22)] active:translate-y-0',
        secondary:
          'clay-surface text-slate-900 hover:translate-y-[-1px] hover:shadow-[0_22px_64px_rgba(2,6,23,0.14),0_2px_0_rgba(255,255,255,0.85)_inset] active:translate-y-0',
        glass:
          'glass-panel text-slate-900 hover:translate-y-[-1px] hover:shadow-[0_26px_80px_rgba(2,6,23,0.14),0_1px_0_rgba(255,255,255,0.75)_inset] active:translate-y-0',
        outline:
          'bg-white/60 text-slate-900 border border-[var(--border)] shadow-[0_10px_40px_rgba(2,6,23,0.08)] hover:bg-white/80 hover:translate-y-[-1px] active:translate-y-0',
        ghost: 'text-slate-900 hover:bg-white/70',
        danger:
          'bg-rose-600 text-white shadow-[0_18px_60px_rgba(225,29,72,0.20)] hover:bg-rose-700 hover:translate-y-[-1px] active:translate-y-0',
      },
      size: {
        sm: 'h-9 px-4 rounded-xl',
        md: 'h-10 px-5',
        lg: 'h-11 px-6',
        icon: 'h-10 w-10 rounded-2xl',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  },
)

const Button = React.forwardRef(function Button(
  { className, variant, size, asChild = false, ...props },
  ref,
) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
})

export { Button }
