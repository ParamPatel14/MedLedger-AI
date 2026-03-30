import * as React from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { Check, ChevronRight } from 'lucide-react'

import { cn } from '../../lib/cn'

const DropdownMenu = DropdownMenuPrimitive.Root
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
const DropdownMenuGroup = DropdownMenuPrimitive.Group
const DropdownMenuPortal = DropdownMenuPrimitive.Portal
const DropdownMenuSub = DropdownMenuPrimitive.Sub
const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup

const DropdownMenuSubTrigger = React.forwardRef(function DropdownMenuSubTrigger(
  { className, inset, children, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.SubTrigger
      ref={ref}
      className={cn(
        'flex cursor-default select-none items-center rounded-xl px-3 py-2 text-sm outline-none focus:bg-white/70 data-[state=open]:bg-white/70',
        inset && 'pl-8',
        className,
      )}
      {...props}
    >
      {children}
      <ChevronRight className="ml-auto size-4 opacity-70" />
    </DropdownMenuPrimitive.SubTrigger>
  )
})

const DropdownMenuSubContent = React.forwardRef(function DropdownMenuSubContent(
  { className, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.SubContent
      ref={ref}
      className={cn(
        'z-50 min-w-44 overflow-hidden rounded-2xl border border-[var(--border)] bg-white/75 p-1.5 shadow-[0_30px_90px_rgba(2,6,23,0.18)] backdrop-blur-xl',
        className,
      )}
      {...props}
    />
  )
})

const DropdownMenuContent = React.forwardRef(function DropdownMenuContent(
  { className, sideOffset = 10, ...props },
  ref,
) {
  return (
    <DropdownMenuPortal>
      <DropdownMenuPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          'z-50 min-w-52 overflow-hidden rounded-2xl border border-[var(--border)] bg-white/75 p-1.5 shadow-[0_30px_90px_rgba(2,6,23,0.18)] backdrop-blur-xl',
          className,
        )}
        {...props}
      />
    </DropdownMenuPortal>
  )
})

const DropdownMenuItem = React.forwardRef(function DropdownMenuItem(
  { className, inset, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.Item
      ref={ref}
      className={cn(
        'relative flex cursor-default select-none items-center rounded-xl px-3 py-2 text-sm outline-none transition focus:bg-white/70 data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        inset && 'pl-8',
        className,
      )}
      {...props}
    />
  )
})

const DropdownMenuCheckboxItem = React.forwardRef(function DropdownMenuCheckboxItem(
  { className, children, checked, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.CheckboxItem
      ref={ref}
      className={cn(
        'relative flex cursor-default select-none items-center rounded-xl py-2 pl-8 pr-3 text-sm outline-none transition focus:bg-white/70 data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        className,
      )}
      checked={checked}
      {...props}
    >
      <span className="absolute left-2 flex size-4 items-center justify-center">
        <DropdownMenuPrimitive.ItemIndicator>
          <Check className="size-4" />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.CheckboxItem>
  )
})

const DropdownMenuSeparator = React.forwardRef(function DropdownMenuSeparator({ className, ...props }, ref) {
  return (
    <DropdownMenuPrimitive.Separator
      ref={ref}
      className={cn('my-1 h-px bg-[var(--border-2)]', className)}
      {...props}
    />
  )
})

const DropdownMenuLabel = React.forwardRef(function DropdownMenuLabel({ className, inset, ...props }, ref) {
  return (
    <DropdownMenuPrimitive.Label
      ref={ref}
      className={cn('px-3 py-2 text-xs font-semibold text-slate-500', inset && 'pl-8', className)}
      {...props}
    />
  )
})

const DropdownMenuRadioItem = React.forwardRef(function DropdownMenuRadioItem(
  { className, children, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.RadioItem
      ref={ref}
      className={cn(
        'relative flex cursor-default select-none items-center rounded-xl py-2 pl-8 pr-3 text-sm outline-none transition focus:bg-white/70 data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        className,
      )}
      {...props}
    >
      <span className="absolute left-2 flex size-4 items-center justify-center">
        <DropdownMenuPrimitive.ItemIndicator>
          <Check className="size-4" />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.RadioItem>
  )
})

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
}

