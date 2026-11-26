import { FormEvent, ReactNode, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { ConfirmDialog } from './ConfirmDialog';

export type EntityModalSize = 'sm' | 'md' | 'lg' | 'xl' | '2xl';

const SIZE_CLASSES: Record<EntityModalSize, string> = {
  sm: 'max-w-md',
  md: 'max-w-xl',
  lg: 'max-w-3xl',
  xl: 'max-w-5xl',
  '2xl': 'max-w-7xl',
};

export interface EntityModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  size?: EntityModalSize;
  isDirty?: boolean;
  isSubmitting?: boolean;
  submitLabel?: string;
  cancelLabel?: string;
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  footer?: ReactNode;
  children: ReactNode;
}

/**
 * Form CRUD modal with controlled `open` + `onOpenChange`.
 * - Locks closing while `isSubmitting` is true.
 * - Intercepts close attempts when `isDirty` is true and asks via ConfirmDialog before discarding.
 */
export function EntityModal({
  open,
  onOpenChange,
  title,
  description,
  size = 'md',
  isDirty = false,
  isSubmitting = false,
  submitLabel = 'Kaydet',
  cancelLabel = 'Vazgeç',
  onSubmit,
  footer,
  children,
}: EntityModalProps) {
  const [discardDialogOpen, setDiscardDialogOpen] = useState(false);

  const requestClose = () => {
    if (isSubmitting) return;
    if (isDirty) {
      setDiscardDialogOpen(true);
      return;
    }
    onOpenChange(false);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      onOpenChange(true);
      return;
    }
    requestClose();
  };

  const handleConfirmDiscard = () => {
    setDiscardDialogOpen(false);
    onOpenChange(false);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent
          className={`${SIZE_CLASSES[size]} p-0 overflow-hidden`}
          showGlow={false}
          disableClose={isSubmitting}
          hideCloseButton={isSubmitting}
        >
          <div className="flex flex-col max-h-[86vh] min-w-0 w-full">
            <div className="px-6 py-5 border-b border-border bg-card shrink-0">
              <DialogHeader>
                <DialogTitle>{title}</DialogTitle>
                {description && <DialogDescription>{description}</DialogDescription>}
              </DialogHeader>
            </div>

            {onSubmit ? (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void onSubmit(event);
                }}
                className="flex flex-col flex-1 min-h-0 min-w-0"
              >
                <div className="flex-1 overflow-y-auto overflow-x-hidden px-6 py-5 min-w-0">{children}</div>

                <div className="px-6 py-4 border-t border-border bg-muted/30 shrink-0">
                  {footer ?? (
                    <DialogFooter className="border-t-0 pt-0 mt-0">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isSubmitting}
                        onClick={requestClose}
                      >
                        {cancelLabel}
                      </Button>
                      <Button type="submit" size="sm" disabled={isSubmitting}>
                        {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                        {submitLabel}
                      </Button>
                    </DialogFooter>
                  )}
                </div>
              </form>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto overflow-x-hidden px-6 py-5 min-w-0">{children}</div>
                {footer && (
                  <div className="px-6 py-4 border-t border-border bg-muted/30 shrink-0">
                    {footer}
                  </div>
                )}
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={discardDialogOpen}
        onOpenChange={setDiscardDialogOpen}
        variant="destructive"
        title="Kaydedilmemiş değişiklikler var"
        description="Formda yaptığınız değişiklikler kaydedilmedi. Çıkarsanız bu düzenlemeler kaybolacaktır."
        confirmLabel="Değişiklikleri Sil ve Kapat"
        cancelLabel="Düzenlemeye Dön"
        onConfirm={handleConfirmDiscard}
      />
    </>
  );
}
