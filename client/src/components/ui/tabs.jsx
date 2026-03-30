import * as React from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'

import { cn } from '../../lib/cn'

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef(function TabsList({ className, ...props }, ref) {
  return (
    <TabsPrimitive.List
      ref={ref}
      className={cn(
        'inline-flex h-11 items-center justify-center rounded-2xl border border-[var(--border)] bg-white/65 p-1 shadow-[0_10px_40px_rgba(2,6,23,0.06)]',
        className,
      )}
      {...props}
    />
  )
})

const TabsTrigger = React.forwardRef(function TabsTrigger({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center rounded-2xl px-4 py-2 text-sm font-semibold text-slate-600 outline-none transition hover:text-slate-900 data-[state=active]:bg-white data-[state=active]:text-slate-900 data-[state=active]:shadow-[0_18px_60px_rgba(2,6,23,0.10)] focus-visible:ring-4 focus-visible:ring-[var(--ring)]',
        className,
      )}
      {...props}
    />
  )
})

const TabsContent = React.forwardRef(function TabsContent({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Content
      ref={ref}
      className={cn('mt-4 outline-none focus-visible:ring-4 focus-visible:ring-[var(--ring)]', className)}
      {...props}
    />
  )
})

export { Tabs, TabsList, TabsTrigger, TabsContent }

