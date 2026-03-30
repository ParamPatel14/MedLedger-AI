import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

import { cn } from '../../lib/cn'

const Dialog = DialogPrimitive.Root
const DialogTrigger = DialogPrimitive.Trigger
const DialogPortal = DialogPrimitive.Portal
const DialogClose = DialogPrimitive.Close

const DialogOverlay = React.forwardRef(function DialogOverlay({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Overlay
      ref={ref}
      className={cn(
        'fixed inset-0 z-50 bg-slate-950/20 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        className,
      )}
      {...props}
    />
  )
})

const DialogContent = React.forwardRef(function DialogContent({ className, children, ...props }, ref) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          'fixed left-1/2 top-1/2 z-50 w-[calc(100%-24px)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-[var(--border)] bg-white/85 p-5 shadow-[0_40px_120px_rgba(2,6,23,0.22)] backdrop-blur-xl outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          className,
        )}
        {...props}
      >
        {children}
        <DialogClose className="absolute right-3 top-3 inline-flex size-10 items-center justify-center rounded-2xl border border-[var(--border)] bg-white/70 text-slate-700 shadow-[0_10px_40px_rgba(2,6,23,0.10)] outline-none transition hover:bg-white focus-visible:ring-4 focus-visible:ring-[var(--ring)]">
          <X className="size-4" />
        </DialogClose>
      </DialogPrimitive.Content>
    </DialogPortal>
  )
})

const DialogHeader = ({ className, ...props }) => (
  <div className={cn('flex flex-col gap-1.5', className)} {...props} />
)

const DialogTitle = React.forwardRef(function DialogTitle({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Title
      ref={ref}
      className={cn('text-base font-semibold tracking-[-0.01em] text-slate-900', className)}
      {...props}
    />
  )
})

const DialogDescription = React.forwardRef(function DialogDescription({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Description ref={ref} className={cn('text-sm text-slate-600', className)} {...props} />
  )
})

export { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription }

