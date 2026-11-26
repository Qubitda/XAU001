import type { ReactNode } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { cn } from '../../lib/utils';

interface PortalDataCardProps {
  title?: string;
  toolbar?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}

/** Card wrapper for dense OPS/B2B data tables and panels. */
export function PortalDataCard({
  title,
  toolbar,
  children,
  className,
  contentClassName,
}: PortalDataCardProps) {
  return (
    <Card className={cn('overflow-hidden shadow-none max-w-full min-w-0', className)}>
      {(title || toolbar) && (
        <CardHeader className="flex flex-col gap-2 space-y-0 border-b border-border bg-muted/40 px-3 sm:px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3 min-w-0">
          {title ? (
            <CardTitle className="text-sm font-medium min-w-0 truncate">{title}</CardTitle>
          ) : (
            <span />
          )}
          {toolbar ? <div className="min-w-0 max-w-full">{toolbar}</div> : null}
        </CardHeader>
      )}
      <CardContent className={cn('p-0 min-w-0 max-w-full', contentClassName)}>{children}</CardContent>
    </Card>
  );
}
