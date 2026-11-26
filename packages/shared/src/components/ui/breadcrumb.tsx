import type { ComponentProps, ReactNode } from 'react';
import { ChevronRight, MoreHorizontal } from 'lucide-react';
import { cn } from '../../lib/utils';

export function Breadcrumb({ ...props }: ComponentProps<'nav'>) {
  return <nav aria-label="Breadcrumb" {...props} />;
}

export function BreadcrumbList({ className, ...props }: ComponentProps<'ol'>) {
  return (
    <ol
      className={cn('flex flex-wrap items-center gap-1.5 break-words text-caption sm:gap-2', className)}
      {...props}
    />
  );
}

export function BreadcrumbItem({ className, ...props }: ComponentProps<'li'>) {
  return <li className={cn('inline-flex items-center gap-1.5', className)} {...props} />;
}

export function BreadcrumbLink({
  className,
  asChild,
  children,
  ...props
}: ComponentProps<'a'> & { asChild?: boolean }) {
  if (asChild && children) {
    return <span className={cn('transition-colors hover:text-foreground', className)}>{children}</span>;
  }
  return (
    <a className={cn('transition-colors hover:text-foreground', className)} {...props}>
      {children}
    </a>
  );
}

export function BreadcrumbPage({ className, ...props }: ComponentProps<'span'>) {
  return (
    <span
      role="link"
      aria-disabled="true"
      aria-current="page"
      className={cn('font-medium text-foreground', className)}
      {...props}
    />
  );
}

export function BreadcrumbSeparator({ children, className, ...props }: ComponentProps<'li'>) {
  return (
    <li role="presentation" aria-hidden="true" className={cn('[&>svg]:size-3.5', className)} {...props}>
      {children ?? <ChevronRight />}
    </li>
  );
}

export function BreadcrumbEllipsis({ className, ...props }: ComponentProps<'span'>) {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      className={cn('flex h-9 w-9 items-center justify-center', className)}
      {...props}
    >
      <MoreHorizontal className="h-4 w-4" />
      <span className="sr-only">Daha fazla</span>
    </span>
  );
}

export type BreadcrumbNavItem = { label: ReactNode; href?: string };