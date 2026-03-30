import * as React from 'react'

import { cn } from '../../lib/cn'

function Card({ className, variant = 'clay', ...props }) {
  const base =
    variant === 'glass'
      ? 'glass-panel rounded-[28px]'
      : 'clay-surface rounded-[28px]'
  return <div className={cn(base, 'p-5 md:p-6', className)} {...props} />
}

function CardHeader({ className, ...props }) {
  return <div className={cn('flex items-start justify-between gap-4', className)} {...props} />
}

function CardTitle({ className, ...props }) {
  return (
    <div
      className={cn('text-[15px] font-semibold tracking-[-0.01em] text-slate-900', className)}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }) {
  return <div className={cn('text-sm text-slate-600', className)} {...props} />
}

function CardContent({ className, ...props }) {
  return <div className={cn('mt-4', className)} {...props} />
}

function CardFooter({ className, ...props }) {
  return <div className={cn('mt-5 flex items-center justify-between gap-3', className)} {...props} />
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter }

