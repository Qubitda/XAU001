import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ApiClientError } from '../../../lib/api/client';
import { useAuth } from '../../../providers/AuthProvider';
import { commerceKeys } from '../../commerce/hooks/useCommerceQueries';
import { dyoService } from '../services/dyoService';
import type { CompatibleStonesQuery, CreateDyoBundleInput } from '../types';

export const dyoKeys = {
  all: ['dyo'] as const,
  compatibleStones: (q: CompatibleStonesQuery) =>
    [...dyoKeys.all, 'compatible-stones', q.mountingSku, q.color ?? '', q.clarity ?? '', q.limit ?? 50] as const,
  bundle: (id: string) => [...dyoKeys.all, 'bundle', id] as const,
};

export function useCompatibleStonesQuery(
  query: CompatibleStonesQuery | null,
  audience: CreateDyoBundleInput['audience'] = 'b2c'
) {
  const { authenticated } = useAuth();
  return useQuery({
    queryKey: query
      ? [...dyoKeys.compatibleStones(query), audience ?? 'b2c']
      : [...dyoKeys.all, 'compatible-stones', 'idle', audience ?? 'b2c'],
    queryFn: () => dyoService.getCompatibleStones(query!, audience),
    enabled: Boolean(authenticated && query?.mountingSku),
  });
}

export function useDyoValidateMutation(audience: CreateDyoBundleInput['audience'] = 'b2c') {
  return useMutation({
    mutationFn: ({ mountingSku, stoneSku }: { mountingSku: string; stoneSku: string }) =>
      dyoService.validate(mountingSku, stoneSku, audience),
  });
}

export function useCreateDyoBundleMutation(audience: CreateDyoBundleInput['audience'] = 'b2c') {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateDyoBundleInput) =>
      dyoService.createBundle({ ...input, audience: input.audience ?? audience }),
    onSuccess: (_data, vars) => {
      const resolved = vars.audience ?? audience;
      if (resolved === 'b2b') {
        void qc.invalidateQueries({ queryKey: commerceKeys.b2bDraft() });
        toast.success('Montür + taş sipariş fişine eklendi');
      } else {
        void qc.invalidateQueries({ queryKey: commerceKeys.b2cCart() });
        toast.success('Montür + taş sepete eklendi');
      }
    },
    onError: (err) => {
      if (err instanceof ApiClientError) {
        toast.error(err.message);
        return;
      }
      toast.error('DYO paket oluşturulamadı');
    },
  });
}

export function useDeleteDyoBundleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (bundleId: string) => dyoService.deleteBundle(bundleId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: commerceKeys.b2cCart() });
      toast.success('DYO paketi sepetten çıkarıldı');
    },
    onError: (err) => {
      if (err instanceof ApiClientError) {
        toast.error(err.message);
        return;
      }
      toast.error('DYO paketi silinemedi');
    },
  });
}

export function useExtendDyoBundleMutation() {
  return useMutation({
    mutationFn: (bundleId: string) => dyoService.extendBundle(bundleId),
    onSuccess: () => toast.success('Taş rezervasyonu uzatıldı'),
  });
}
