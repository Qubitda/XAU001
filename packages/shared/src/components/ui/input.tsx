import type { ComponentProps } from 'react';
import { cn } from '../../lib/utils';

export function Input({ className, type, ...props }: ComponentProps<'input'>) {
  return (
    <input
      type={type}
      className={cn(
        'flex min-h-11 h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base md:min-h-9 md:h-9 md:py-1 md:text-sm shadow-xs transition-colors',
        'file:border-0 file:bg-transparent file:text-sm file:font-medium',
        'placeholder:text-muted-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      {...props}
    />
  );
}