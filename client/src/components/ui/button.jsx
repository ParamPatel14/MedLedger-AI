import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 cursor-pointer select-none',
  {
    variants: {
      variant: {
        default:
          'bg-[#1565C0] text-white shadow hover:bg-[#0D47A1] focus-visible:ring-[#1565C0] active:scale-[0.98]',
        destructive:
          'bg-[#C62828] text-white shadow-sm hover:bg-[#B71C1C] focus-visible:ring-[#C62828] active:scale-[0.98]',
        outline:
          'border border-[#D1D9E6] bg-white text-[#374151] shadow-sm hover:bg-[#F4F7FB] hover:border-[#B0BEC5] focus-visible:ring-[#1565C0] active:scale-[0.98]',
        secondary:
          'bg-[#EEF2FF] text-[#1565C0] border border-[#BFDBFE] hover:bg-[#E0EAFF] focus-visible:ring-[#1565C0] active:scale-[0.98]',
        ghost:
          'text-[#6B7280] hover:bg-[#F4F7FB] hover:text-[#374151] focus-visible:ring-[#1565C0]',
        link: 'text-[#1565C0] underline-offset-4 hover:underline p-0 h-auto',
        danger:
          'bg-transparent border border-[#FECACA] text-[#DC2626] hover:bg-[#FEF2F2] focus-visible:ring-[#DC2626] active:scale-[0.98]',
      },
      size: {
        default: 'h-9 px-4 py-2 text-sm',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-11 rounded-md px-8 text-base',
        xl: 'h-12 rounded-lg px-10 text-base',
        icon: 'h-9 w-9 p-0',
        'icon-sm': 'h-8 w-8 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export function Button({ className, variant, size, children, ...props }) {
  return (
    <button className={cn(buttonVariants({ variant, size }), className)} {...props}>
      {children}
    </button>
  )
}

export { buttonVariants }
