import * as React from 'react'

import { cn } from '../../lib/cn'

const Input = React.forwardRef(function Input({ className, type = 'text', ...props }, ref) {
  return (
    <input
      ref={ref}
      type={type}
      className={cn(
        'h-11 w-full rounded-2xl border border-[var(--border)] bg-white/65 px-4 text-sm text-slate-900 shadow-[0_10px_40px_rgba(2,6,23,0.06)] outline-none placeholder:text-slate-400 focus:border-blue-300/70 focus:ring-4 focus:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
})

export { Input }

