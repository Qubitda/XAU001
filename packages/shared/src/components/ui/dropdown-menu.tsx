import type { ComponentProps } from 'react';
import * as RadixMenu from '@radix-ui/react-dropdown-menu';
import { cn } from '../../lib/utils';

export const DropdownMenu = RadixMenu.Root;
export const DropdownMenuTrigger = RadixMenu.Trigger;
export const DropdownMenuGroup = RadixMenu.Group;

export function DropdownMenuContent({
  className,
  sideOffset = 6,
  align = 'end',
  ...props
}: ComponentProps<typeof RadixMenu.Content>) {
  return (
    <RadixMenu.Portal>
      <RadixMenu.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(
          'z-50 min-w-[11rem] overflow-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg',
          className
        )}
        {...props}
      />
    </RadixMenu.Portal>
  );
}

export function DropdownMenuItem({
  className,
  destructive = false,
  ...props
}: ComponentProps<typeof RadixMenu.Item> & { destructive?: boolean }) {
  return (
    <RadixMenu.Item
      className={cn(
        'relative flex cursor-pointer select-none items-center gap-2 rounded-md px-2.5 py-2 text-xs font-medium outline-none transition-colors data-[disabled]:pointer-events-none data-[disabled]:opacity-40',
        destructive
          ? 'text-destructive focus:bg-red-50 focus:text-destructive'
          : 'text-foreground focus:bg-accent focus:text-accent-foreground',
        className
      )}
      {...props}
    />
  );
}

export function DropdownMenuLabel({
  className,
  ...props
}: ComponentProps<typeof RadixMenu.Label>) {
  return (
    <RadixMenu.Label
      className={cn('px-2.5 py-1.5 text-[11px] font-semibold text-muted-foreground', className)}
      {...props}
    />
  );
}

export function DropdownMenuSeparator({
  className,
  ...props
}: ComponentProps<typeof RadixMenu.Separator>) {
  return (
    <RadixMenu.Separator
      className={cn('-mx-1 my-1 h-px bg-border', className)}
      {...props}
    />
  );
}
