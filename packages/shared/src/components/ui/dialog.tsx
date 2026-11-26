import type { ComponentProps, HTMLAttributes } from 'react';
import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { AiStudioGlowLayers } from './ai-studio-glow';

const OUTER_CLASS_PATTERN =
  /^(?:[a-z0-9-]+:)?-?(?:max-w-|min-w-|w-|max-h-|min-h-|h-|top-|left-|right-|bottom-|inset-|translate-|z-|rounded)/;

function splitDialogClassName(className?: string): { outer: string; inner: string } {
  if (!className) return { outer: '', inner: '' };
  const outerTokens: string[] = [];
  const innerTokens: string[] = [];

  for (const token of className.trim().split(/\s+/)) {
    if (!token) continue;
    if (OUTER_CLASS_PATTERN.test(token)) {
      outerTokens.push(token);
    } else {
      innerTokens.push(token);
    }
  }

  return {
    outer: outerTokens.join(' '),
    inner: innerTokens.join(' '),
  };
}

export const Dialog = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;
export const DialogPortal = RadixDialog.Portal;
export const DialogClose = RadixDialog.Close;

export function DialogOverlay({
  className,
  ...props
}: ComponentProps<typeof RadixDialog.Overlay>) {
  return (
    <RadixDialog.Overlay
      className={cn(
        'dialog-overlay fixed inset-0 z-50 bg-primary/45 backdrop-blur-[2px]',
        className
      )}
      {...props}
    />
  );
}

export interface DialogContentProps extends ComponentProps<typeof RadixDialog.Content> {
  showGlow?: boolean;
  hideCloseButton?: boolean;
  disableClose?: boolean;
  innerClassName?: string;
}

/**
 * Radix Dialog content shell that splits layout classes into:
 * - Outer container: fixed position, width/height sizing, and rotating AI Studio glow layers
 * - Inner card: opaque bg-card surface, scroll container, and interior padding
 */
export function DialogContent({
  children,
  className,
  innerClassName,
  showGlow = true,
  hideCloseButton = false,
  disableClose = false,
  onEscapeKeyDown,
  onInteractOutside,
  onPointerDownOutside,
  ...props
}: DialogContentProps) {
  const { outer, inner } = splitDialogClassName(className);

  return (
    <DialogPortal>
      <DialogOverlay />
      <RadixDialog.Content
        onEscapeKeyDown={(event) => {
          if (disableClose) event.preventDefault();
          onEscapeKeyDown?.(event);
        }}
        onInteractOutside={(event) => {
          if (disableClose) event.preventDefault();
          onInteractOutside?.(event);
        }}
        onPointerDownOutside={(event) => {
          if (disableClose) event.preventDefault();
          onPointerDownOutside?.(event);
        }}
        className={cn(
          'dialog-content fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[calc(100%-2rem)] max-w-xl max-h-[90vh] min-w-0 overflow-hidden rounded-xl focus:outline-none',
          outer
        )}
        {...props}
      >
        {showGlow && <AiStudioGlowLayers />}

        <div
          className={cn(
            'relative z-10 isolate bg-card text-foreground rounded-[inherit] shadow-2xl h-full max-h-[90vh] overflow-y-auto overflow-x-hidden p-6 min-w-0',
            inner,
            innerClassName
          )}
        >
          {children}

          {!hideCloseButton && (
            <RadixDialog.Close
              disabled={disableClose}
              aria-label="Kapat"
              className="absolute right-4 top-4 p-1.5 rounded-md text-zinc-400 hover:text-foreground hover:bg-zinc-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
            >
              <X className="w-4 h-4" />
            </RadixDialog.Close>
          )}
        </div>
      </RadixDialog.Content>
    </DialogPortal>
  );
}

export function DialogHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex flex-col space-y-1.5 pr-8 text-left', className)}
      {...props}
    />
  );
}

export function DialogFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'flex flex-col-reverse sm:flex-row sm:justify-end sm:items-center gap-2.5 pt-4 mt-4 border-t border-zinc-200',
        className
      )}
      {...props}
    />
  );
}

export function DialogTitle({
  className,
  ...props
}: ComponentProps<typeof RadixDialog.Title>) {
  return (
    <RadixDialog.Title
      className={cn('font-serif text-2xl font-semibold text-foreground leading-tight', className)}
      {...props}
    />
  );
}

export function DialogDescription({
  className,
  ...props
}: ComponentProps<typeof RadixDialog.Description>) {
  return (
    <RadixDialog.Description
      className={cn('text-xs text-zinc-500 leading-relaxed', className)}
      {...props}
    />
  );
}
