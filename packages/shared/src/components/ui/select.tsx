import type { ComponentProps } from 'react';
import * as RadixSelect from '@radix-ui/react-select';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '../../lib/utils';

export const Select = RadixSelect.Root;
export const SelectGroup = RadixSelect.Group;
export const SelectValue = RadixSelect.Value;

export function SelectTrigger({
  className,
  children,
  ...props
}: ComponentProps<typeof RadixSelect.Trigger>) {
  return (
    <RadixSelect.Trigger
      className={cn(
        'flex h-8 w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-2.5 py-1.5 text-xs text-foreground shadow-2xs transition-colors focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer',
        className
      )}
      {...props}
    >
      <span className="truncate">{children}</span>
      <RadixSelect.Icon asChild>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      </RadixSelect.Icon>
    </RadixSelect.Trigger>
  );
}

export function SelectContent({
  className,
  children,
  position = 'popper',
  ...props
}: ComponentProps<typeof RadixSelect.Content>) {
  return (
    <RadixSelect.Portal>
      <RadixSelect.Content
        position={position}
        sideOffset={4}
        className={cn(
          'z-50 max-h-64 min-w-[8rem] overflow-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg',
          position === 'popper' && 'w-[var(--radix-select-trigger-width)]',
          className
        )}
        {...props}
      >
        <RadixSelect.Viewport className="p-0.5">{children}</RadixSelect.Viewport>
      </RadixSelect.Content>
    </RadixSelect.Portal>
  );
}

export function SelectItem({
  className,
  children,
  ...props
}: ComponentProps<typeof RadixSelect.Item>) {
  return (
    <RadixSelect.Item
      className={cn(
        'relative flex w-full cursor-pointer select-none items-center rounded-md py-1.5 pl-7 pr-2.5 text-xs text-foreground outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-40',
        className
      )}
      {...props}
    >
      <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
        <RadixSelect.ItemIndicator>
          <Check className="h-3.5 w-3.5 text-foreground" />
        </RadixSelect.ItemIndicator>
      </span>
      <RadixSelect.ItemText>{children}</RadixSelect.ItemText>
    </RadixSelect.Item>
  );
}

export function SelectSeparator({
  className,
  ...props
}: ComponentProps<typeof RadixSelect.Separator>) {
  return (
    <RadixSelect.Separator
      className={cn('-mx-1 my-1 h-px bg-border', className)}
      {...props}
    />
  );
}
