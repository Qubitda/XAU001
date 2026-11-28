import { Input, Label } from '../../../components/ui';
import type { ProductState } from '../../../types/jewelry';

const FIELD_TEXTAREA_CLASS =
  'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1';

export function ProductSalesWarrantyPanel({
  draft,
  fieldErrors,
  onPatchField,
}: {
  draft: ProductState;
  fieldErrors: Record<string, string>;
  onPatchField: <K extends keyof ProductState>(key: K, value: ProductState[K]) => void;
}) {
  return (
    <div className="space-y-5">
      <p className="text-xs text-muted-foreground">
        Satış sonrası garanti, bakım, sigortalı teslimat ve iade politikaları ürün kartı seviyesinde kaydedilir.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <Label className="font-medium block">Garanti Süresi (Ay)</Label>
          <Input
            type="number"
            min={0}
            max={120}
            value={draft.warrantyMonths}
            onChange={(e) =>
              onPatchField('warrantyMonths', Math.max(0, Math.round(Number(e.target.value) || 0)))
            }
            className="text-right font-mono tabular-nums"
          />
          {fieldErrors.warrantyMonths && (
            <p className="text-[11px] text-red-700">{fieldErrors.warrantyMonths}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label className="font-medium block">Ömür Boyu Bakım</Label>
          <Input
            type="text"
            value={draft.lifetimeMaintenance}
            onChange={(e) => onPatchField('lifetimeMaintenance', e.target.value)}
            placeholder="Evet (Ücretsiz)"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="font-medium block">Sigortalı Kargo Bilgisi</Label>
          <Input
            type="text"
            value={draft.insuredShippingInfo}
            onChange={(e) => onPatchField('insuredShippingInfo', e.target.value)}
            placeholder="Tam sigortalı özel kurye"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label className="font-medium block">İade &amp; Değişim Politikası</Label>
        <textarea
          rows={3}
          value={draft.returnPolicyText}
          onChange={(e) => onPatchField('returnPolicyText', e.target.value)}
          placeholder="14 gün içinde koşulsuz iade; kişiye özel yazı/ölçü yapılan ürünlerde cayma istisnası uygulanır."
          className={FIELD_TEXTAREA_CLASS}
        />
      </div>

      <div className="space-y-1.5">
        <Label className="font-medium block">Tedarikçi (katalog etiketi)</Label>
        <Input
          type="text"
          value={draft.supplierName}
          onChange={(e) => onPatchField('supplierName', e.target.value)}
          placeholder="Tara Gold Atölye"
        />
        <p className="text-[10px] text-muted-foreground">
          Fiziksel depo/tedarikçi stok satırında yaşar; bu alan ürün kartı etiketidir.
        </p>
      </div>
    </div>
  );
}
