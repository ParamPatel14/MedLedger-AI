import * as React from 'react'

import { cn } from '../../lib/cn'

const Textarea = React.forwardRef(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        'min-h-28 w-full resize-y rounded-3xl border border-[var(--border)] bg-white/65 p-4 text-sm text-slate-900 shadow-[0_10px_40px_rgba(2,6,23,0.06)] outline-none placeholder:text-slate-400 focus:border-blue-300/70 focus:ring-4 focus:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
})

export { Textarea }

