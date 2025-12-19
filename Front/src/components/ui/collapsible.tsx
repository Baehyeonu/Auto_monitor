import * as React from "react"
import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from "@/lib/utils"

interface CollapsibleProps {
  children: React.ReactNode
  defaultOpen?: boolean
  className?: string
}

export function Collapsible({ children, defaultOpen = false, className }: CollapsibleProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  const toggleMenu = () => {
    setIsOpen(isOpen => !isOpen)
  }

  return (
    <div className={cn("border rounded-lg overflow-hidden", className)}>
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          if (child.type === CollapsibleTrigger) {
            return React.cloneElement(child as React.ReactElement<any>, {
              isOpen,
              onClick: toggleMenu
            })
          }
          if (child.type === CollapsibleContent) {
            return React.cloneElement(child as React.ReactElement<any>, {
              isOpen
            })
          }
        }
        return child
      })}
    </div>
  )
}

interface CollapsibleTriggerProps {
  children: React.ReactNode
  isOpen?: boolean
  onClick?: () => void
}

export function CollapsibleTrigger({ children, isOpen, onClick }: CollapsibleTriggerProps) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between px-4 py-3 font-semibold hover:bg-muted/50 transition-colors"
    >
      {children}
      <ChevronDown
        className={cn(
          "h-5 w-5 transition-transform duration-300",
          isOpen && "transform rotate-180"
        )}
      />
    </button>
  )
}

interface CollapsibleContentProps {
  children: React.ReactNode
  isOpen?: boolean
}

export function CollapsibleContent({ children, isOpen }: CollapsibleContentProps) {
  return (
    <div
      className={cn(
        "transition-all duration-300 ease-in-out",
        isOpen ? "max-h-[2000px] opacity-100" : "max-h-0 opacity-0"
      )}
      style={{
        overflow: isOpen ? 'visible' : 'hidden'
      }}
    >
      <div className="px-4 pb-4 space-y-4">
        {children}
      </div>
    </div>
  )
}
