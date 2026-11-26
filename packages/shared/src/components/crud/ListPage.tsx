import { ReactNode } from 'react';
import { PortalPageHeader } from '../portal/PortalPageHeader';
import { cn } from '../../lib/utils';

export interface ListPageProps {
  kicker?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  filters?: ReactNode;
  isLoading?: boolean;
  isEmpty?: boolean;
  emptyState?: ReactNode;
  className?: string;
  children: ReactNode;
}

/**
 * Standard portal list/resource page shell used across feature domains.
 */
export function ListPage({
  kicker,
  title,
  subtitle,
  actions,
  filters,
  isLoading = false,
  isEmpty = false,
  emptyState,
  className,
  children,
}: ListPageProps) {
  return (
    <div className={cn('space-y-6', className)}>
      <PortalPageHeader
        eyebrow={kicker}
        title={title}
        description={subtitle}
        actions={actions}
      />

      {filters ? <div>{filters}</div> : null}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[0, 1, 2].map((idx) => (
            <div
              key={idx}
              className="h-72 rounded-xl border border-border bg-card p-5 space-y-4 animate-pulse"
            >
              <div className="h-40 rounded-lg bg-muted" />
              <div className="h-4 w-2/3 rounded bg-muted" />
              <div className="h-3 w-1/2 rounded bg-muted" />
            </div>
          ))}
        </div>
      ) : isEmpty && emptyState ? (
        <div>{emptyState}</div>
      ) : (
        children
      )}
    </div>
  );
}