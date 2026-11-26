import type { ComponentProps } from 'react';
import * as RadixTooltip from '@radix-ui/react-tooltip';
import { cn } from '../../lib/utils';

export const TooltipProvider = RadixTooltip.Provider;
export const Tooltip = RadixTooltip.Root;
export const TooltipTrigger = RadixTooltip.Trigger;

export function TooltipContent({
  className,
  sideOffset = 6,
  children,
  ...props
}: ComponentProps<typeof RadixTooltip.Content>) {
  return (
    <RadixTooltip.Portal>
      <RadixTooltip.Content
        sideOffset={sideOffset}
        className={cn(
          'z-50 max-w-xs rounded-md bg-primary px-2.5 py-1.5 text-[11px] font-medium text-primary-foreground shadow-md select-none',
          className
        )}
        {...props}
      >
        {children}
      </RadixTooltip.Content>
    </RadixTooltip.Portal>
  );
}
