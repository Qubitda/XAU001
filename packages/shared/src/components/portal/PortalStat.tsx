import type { ReactNode } from 'react';
import { Card, CardContent } from '../ui/card';
import { cn } from '../../lib/utils';

export interface PortalStatProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  className?: string;
  valueClassName?: string;
}

/** Compact OPS/B2B metric tile (label + value + optional hint). */
export function PortalStat({
  label,
  value,
  hint,
  icon,
  className,
  valueClassName,
}: PortalStatProps) {
  return (
    <Card className={cn('shadow-none', className)}>
      <CardContent className="p-5 space-y-1.5">
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>{label}</span>
          {icon}
        </div>
        <div
          className={cn(
            'font-mono text-2xl font-semibold text-foreground tabular-nums',
            valueClassName
          )}
        >
          {value}
        </div>
        {hint ? <div className="text-[11px] text-muted-foreground">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}