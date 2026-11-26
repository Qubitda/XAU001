import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface PortalPageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

/** Shared B2B/OPS page header — zinc, Geist typography tokens. */
export function PortalPageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: PortalPageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between',
        className
      )}
    >
      <div className="min-w-0 space-y-1">
        {eyebrow ? <p className="text-caption">{eyebrow}</p> : null}
        <h1 className="text-page-title text-foreground">{title}</h1>
        {description ? <p className="text-caption max-w-2xl">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div> : null}
    </div>
  );
}
