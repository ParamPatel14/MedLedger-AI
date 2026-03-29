import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'border-[#BFDBFE] bg-[#EEF2FF] text-[#1565C0]',
        success: 'border-[#A7F3D0] bg-[#D1FAE5] text-[#065F46]',
        warning: 'border-[#FDE68A] bg-[#FEF3C7] text-[#92400E]',
        danger: 'border-[#FECACA] bg-[#FEF2F2] text-[#991B1B]',
        neutral: 'border-[#E2E8F0] bg-[#F8FAFC] text-[#475569]',
        teal: 'border-[#99F6E4] bg-[#F0FDFA] text-[#0F766E]',
        dark: 'border-transparent bg-[#1E293B] text-white',
        outline: 'border-[#D1D9E6] bg-transparent text-[#6B7280]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export function Badge({ className, variant, children, ...props }) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {children}
    </span>
  )
}
