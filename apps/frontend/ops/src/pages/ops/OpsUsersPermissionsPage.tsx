import { useEffect, useState } from 'react';
import { Plus, Search, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import {
  useCreateOpsMembershipMutation,
  useCreateOpsUserMutation,
  useOpsOrganizationsQuery,
  useOpsRolesQuery,
  useOpsUsersQuery,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { ApiClientError } from '@taragold/shared/lib/api/client';

export function OpsUsersPermissionsPage() {
  const { user } = useAuth();
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [membershipOpen, setMembershipOpen] = useState(false);
  const [membershipUserId, setMembershipUserId] = useState('');
  const [membershipOrgId, setMembershipOrgId] = useState('');
  const [membershipRoleKey, setMembershipRoleKey] = useState('');

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedQ(q.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(t);
  }, [q]);

  const usersQuery = useOpsUsersQuery({ q: debouncedQ || undefined, page, pageSize: 30 });
  const rolesQuery = useOpsRolesQuery();
  const createMut = useCreateOpsUserMutation();
  const membershipMut = useCreateOpsMembershipMutation();
  const orgsQuery = useOpsOrganizationsQuery({ pageSize: 200, isActive: true });
  const orgs = orgsQuery.data?.items ?? [];

  const rows = usersQuery.data?.items ?? [];
  const pagination = usersQuery.data?.pagination;
  const roles = rolesQuery.data?.roles ?? [];

  const openAssignMembership = (userId: string) => {
    setMembershipUserId(userId);
    setMembershipOrgId('');
    setMembershipRoleKey('');
    setMembershipOpen(true);
  };

  const onAssignMembership = async () => {
    try {
      await membershipMut.mutateAsync({
        userId: membershipUserId,
        organizationId: membershipOrgId || null,
        roleKey: membershipRoleKey,
        isActive: true,
      });
      toast.success('Üyelik atandı');
      setMembershipOpen(false);
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Atama başarısız');
    }
  };

  const onCreate = async () => {
    try {
      await createMut.mutateAsync({
        email: email.trim(),
        fullName: fullName.trim(),
        password,
        isStaff: true,
        isActive: true,
      });
      toast.success('Kullanıcı oluşturuldu');
      setCreateOpen(false);
      setEmail('');
      setFullName('');
      setPassword('');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Oluşturulamadı');
    }
  };

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Sunucu Otoriteli Rol & Yetki Matrisi (RBAC)"
        title={`Kullanıcı & Yetki${pagination ? ` (${pagination.total})` : ''}`}
        actions={
          <>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="E-posta veya ad ara..."
                className="h-9 pl-8 w-52 text-xs"
              />
            </div>
            <Button size="sm" variant="success" onClick={() => setCreateOpen(true)}>
              <Plus className="w-3.5 h-3.5" />
              Kullanıcı Davet Et
            </Button>
          </>
        }
      />

      <PortalDataCard title="Aktif Yönetici Oturumu" contentClassName="p-5 space-y-3 text-xs">
        <div className="flex items-center gap-2 font-semibold text-foreground text-sm">
          <ShieldCheck className="w-4 h-4 text-muted-foreground" />
          Oturum özeti
        </div>
        <div className="text-muted-foreground">
          <strong className="text-foreground">{user.fullName}</strong> ({user.email}) · Rol:{' '}
          <span className="font-mono font-semibold text-foreground">{user.roleKey}</span>
        </div>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {user.capabilities.map((cap) => (
            <Badge key={cap} variant="secondary" className="font-mono text-[11px]">
              {cap}
            </Badge>
          ))}
        </div>
      </PortalDataCard>

      <PortalDataCard>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Kullanıcı</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Üyelik / Rol</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Durum</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Son Giriş</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">İşlem</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {usersQuery.isLoading ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  Yükleniyor...
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  Kullanıcı bulunamadı.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => {
                const primary = row.memberships.find((m) => m.isActive) ?? row.memberships[0];
                return (
                  <TableRow key={row.id}>
                    <TableCell className="px-4">
                      <div className="font-medium">{row.fullName}</div>
                      <div className="text-[11px] text-muted-foreground">{row.email}</div>
                    </TableCell>
                    <TableCell className="px-4">
                      {primary ? (
                        <>
                          <div className="font-mono font-semibold">{primary.roleKey}</div>
                          <div className="text-[11px] text-muted-foreground">{primary.organizationName}</div>
                        </>
                      ) : (
                        <span className="text-muted-foreground">Üyelik yok</span>
                      )}
                    </TableCell>
                    <TableCell className="px-4">
                      <Badge variant={row.isActive ? 'outline' : 'secondary'}>
                        {row.isActive ? 'Aktif' : 'Pasif'}
                      </Badge>
                    </TableCell>
                    <TableCell className="px-4 font-mono text-muted-foreground">
                      {row.lastLogin ? new Date(row.lastLogin).toLocaleString('tr-TR') : '—'}
                    </TableCell>
                    <TableCell className="px-4 text-right">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => openAssignMembership(row.id)}
                      >
                        Üyelik Ata
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </PortalDataCard>

      <PortalDataCard title="Sistem Rol Tanımları (API)">
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Rol Anahtarı</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Etiket</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Yetkiler</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roles.map((r) => (
              <TableRow key={r.roleKey}>
                <TableCell className="px-4 font-mono font-semibold">{r.roleKey}</TableCell>
                <TableCell className="px-4 text-muted-foreground">{r.label}</TableCell>
                <TableCell className="px-4 font-mono text-[11px] text-muted-foreground">
                  {r.permissions.join(', ')}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </PortalDataCard>

      {pagination && pagination.totalPages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-xs">
          <Button type="button" size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Önceki
          </Button>
          <span className="text-muted-foreground font-mono tabular-nums">
            {pagination.page} / {pagination.totalPages}
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page >= pagination.totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Sonraki
          </Button>
        </div>
      ) : null}

      <Dialog open={membershipOpen} onOpenChange={setMembershipOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Organizasyon Üyeliği Ata</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label>Firma</Label>
              <Select value={membershipOrgId} onValueChange={setMembershipOrgId}>
                <SelectTrigger className="text-xs">
                  <SelectValue placeholder="Firma seçin" />
                </SelectTrigger>
                <SelectContent>
                  {orgs.map((org) => (
                    <SelectItem key={org.id} value={org.id}>
                      {org.code} — {org.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Rol</Label>
              <Select value={membershipRoleKey} onValueChange={setMembershipRoleKey}>
                <SelectTrigger className="text-xs">
                  <SelectValue placeholder="Rol seçin" />
                </SelectTrigger>
                <SelectContent>
                  {roles.map((r) => (
                    <SelectItem key={r.roleKey} value={r.roleKey}>
                      {r.roleKey} — {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              disabled={membershipMut.isPending || !membershipUserId || !membershipRoleKey}
              onClick={() => void onAssignMembership()}
            >
              Ata
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Yeni OPS Kullanıcısı</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="user-email">E-posta</Label>
              <Input id="user-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="user-name">Ad Soyad</Label>
              <Input id="user-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="user-pass">Geçici Şifre</Label>
              <Input
                id="user-pass"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              disabled={!email.trim() || !fullName.trim() || password.length < 8 || createMut.isPending}
              onClick={() => void onCreate()}
            >
              Oluştur
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}