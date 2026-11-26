import type { ComponentProps } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        outline: 'border border-input bg-card text-foreground hover:bg-accent hover:border-border',
        ghost: 'text-muted-foreground hover:bg-accent hover:text-foreground',
        /** Icon/text delete affordance — always red (ghost surface) */
        'ghost-destructive':
          'text-destructive hover:bg-destructive/10 hover:text-destructive',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        success: 'bg-primary text-primary-foreground hover:bg-primary/90',
        link: 'text-foreground underline-offset-4 hover:underline',
      },
      size: {
        xs: 'h-7 min-h-7 px-2.5 text-[11px]',
        sm: 'min-h-10 h-10 px-3 text-sm md:min-h-8 md:h-8',
        default: 'min-h-11 h-11 px-4 text-base md:min-h-9 md:h-9 md:text-sm',
        lg: 'min-h-12 h-12 px-5 text-base md:min-h-10 md:h-10 md:text-sm',
        icon: 'min-h-11 h-11 w-11 p-0 md:min-h-8 md:h-8 md:w-8',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends ComponentProps<'button'>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : 'button';
  return (
    <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
