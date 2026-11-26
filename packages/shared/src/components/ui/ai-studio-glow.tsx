import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface AiStudioGlowLayersProps {
  className?: string;
}

/**
 * Renders the rotating spectrum halo (outer blurred glow) and thin 2px border ring.
 * Must be placed inside a positioned container with stacking context (`relative isolate` or `fixed z-*`).
 */
export function AiStudioGlowLayers({ className }: AiStudioGlowLayersProps) {
  return (
    <>
      <span aria-hidden="true" className={cn('ai-studio-halo', className)}>
        <span className="ai-studio-spectrum" />
      </span>
      <span aria-hidden="true" className={cn('ai-studio-ring', className)}>
        <span className="ai-studio-spectrum" />
      </span>
    </>
  );
}

interface AiStudioFrameProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  innerClassName?: string;
  active?: boolean;
}

/**
 * Card/panel wrapper that applies the rotating spectrum edge around any content surface.
 */
export function AiStudioFrame({
  children,
  className,
  innerClassName,
  active = true,
  ...rest
}: AiStudioFrameProps) {
  return (
    <div className={cn('ai-studio-frame rounded-xl', className)} {...rest}>
      {active && <AiStudioGlowLayers />}
      <div
        className={cn(
          'relative z-10 bg-card rounded-[inherit] border border-zinc-200/70',
          innerClassName
        )}
      >
        {children}
      </div>
    </div>
  );
}
