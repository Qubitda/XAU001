import { createContext, ReactNode, useContext, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AudienceRole } from '../types/jewelry';
import {
  apiFetch,
  isDemoModeEnabled,
  isRemoteBackendConfigured,
  syncRemoteSessionContext,
} from '../lib/api/client';
import type {
  BranchDto,
  OrganizationDto,
  OrganizationMembershipDto,
  PortalCapability,
  SessionUserDto,
} from '../lib/api/openapi';

interface AuthContextValue {
  user: SessionUserDto;
  authenticated: boolean;
  isRemoteBackend: boolean;
  role: AudienceRole;
  isLoading: boolean;
  memberships: OrganizationMembershipDto[];
  organizations: OrganizationDto[];
  activeMembership: OrganizationMembershipDto | null;
  activeOrganization: OrganizationDto | null;
  activeBranch: BranchDto | null;
  authModalOpen: boolean;
  setAuthModalOpen: (open: boolean) => void;
  login: (credentials: { email: string; password: string }) => Promise<SessionUserDto>;
  register: (payload: {
    email: string;
    password: string;
    fullName: string;
    phone?: string;
  }) => Promise<SessionUserDto>;
  logout: () => Promise<void>;
  isLoggingIn: boolean;
  isRegistering: boolean;
  loginError: string | null;
  setRole: (role: AudienceRole) => void;
  switchMembership: (membershipId: string) => Promise<SessionUserDto>;
  switchBranch: (branchId: string) => Promise<SessionUserDto>;
  hasCapability: (capability: PortalCapability) => boolean;
}

/**
 * Unauthenticated session shape before /api/v1/session resolves (not catalog mock data).
 * Capabilities are NEVER granted client-side; they come strictly from the backend Session API.
 */
const ANON_SESSION_PLACEHOLDER: SessionUserDto = {
  authenticated: false,
  id: '',
  email: '',
  fullName: 'Misafir',
  emailVerified: false,
  role: 'b2c',
  roleKey: 'B2C_CUSTOMER',
  capabilities: [],
  activeMembershipId: '',
  activeOrganizationId: null,
  activeBranchId: null,
  memberships: [],
  organizations: [],
  csrfToken: '',
};

const AuthContext = createContext<AuthContextValue | null>(null);

export const SESSION_QUERY_KEY = ['portal', 'session'] as const;

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const isRemoteBackend = isRemoteBackendConfigured();
  const demoMode = isDemoModeEnabled();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const sessionQuery = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: async () => {
      const res = await apiFetch<SessionUserDto>('/api/v1/session');
      return res.data;
    },
    retry: isRemoteBackend || !demoMode ? 0 : 1,
  });

  const loginMutation = useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      const res = await apiFetch<SessionUserDto>('/api/v1/session/login', {
        method: 'POST',
        body: credentials,
      });
      return res.data;
    },
    onSuccess: (session) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
      setAuthModalOpen(false);
      void queryClient.invalidateQueries({ queryKey: ['catalog'] });
      void queryClient.invalidateQueries({ queryKey: ['commerce'] });
    },
  });

  const registerMutation = useMutation({
    mutationFn: async (payload: {
      email: string;
      password: string;
      fullName: string;
      phone?: string;
    }) => {
      const res = await apiFetch<SessionUserDto>('/api/v1/auth/register', {
        method: 'POST',
        body: payload,
      });
      return res.data;
    },
    onSuccess: (session) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
      setAuthModalOpen(false);
      void queryClient.invalidateQueries({ queryKey: ['catalog'] });
      void queryClient.invalidateQueries({ queryKey: ['commerce'] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await apiFetch<{ loggedOut: boolean }>('/api/v1/session/logout', {
        method: 'POST',
      });
      syncRemoteSessionContext({ membershipId: null, organizationId: null, branchId: null });
      const res = await apiFetch<SessionUserDto>('/api/v1/session');
      return res.data;
    },
    onSuccess: (anonSession) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, anonSession);
      void queryClient.invalidateQueries({ queryKey: ['catalog'] });
      void queryClient.invalidateQueries({ queryKey: ['commerce'] });
    },
  });

  const switchContextMutation = useMutation({
    mutationFn: async (payload: {
      membershipId?: string;
      branchId?: string;
      role?: AudienceRole;
    }) => {
      // Prevent an in-flight GET /session from overwriting the switched context.
      await queryClient.cancelQueries({ queryKey: SESSION_QUERY_KEY });
      const res = await apiFetch<SessionUserDto>('/api/v1/session/context', {
        method: 'PATCH',
        body: payload,
      });
      return res.data;
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, updated);
      // Invalidate both audience-scoped catalog & tenant-isolated commerce queries immediately
      void queryClient.invalidateQueries({ queryKey: ['catalog'] });
      void queryClient.invalidateQueries({ queryKey: ['commerce'] });
    },
  });

  const value = useMemo<AuthContextValue>(() => {
    const user = sessionQuery.data ?? ANON_SESSION_PLACEHOLDER;
    const authenticated = Boolean(user.authenticated);
    const memberships = user.memberships ?? [];
    const organizations = user.organizations ?? [];
    const activeMembership =
      memberships.find((m) => m.id === user.activeMembershipId) ?? memberships[0] ?? null;
    const activeOrganization = user.activeOrganizationId
      ? organizations.find((o) => o.id === user.activeOrganizationId) ?? null
      : null;
    const activeBranch = activeOrganization
      ? activeOrganization.branches.find((b) => b.id === user.activeBranchId) ??
        activeOrganization.branches[0] ??
        null
      : null;

    return {
      user,
      authenticated,
      isRemoteBackend,
      role: user.role,
      isLoading: sessionQuery.isLoading,
      memberships,
      organizations,
      activeMembership,
      activeOrganization,
      activeBranch,
      authModalOpen,
      setAuthModalOpen,
      login: (creds) => loginMutation.mutateAsync(creds),
      register: (payload) => registerMutation.mutateAsync(payload),
      logout: async () => {
        await logoutMutation.mutateAsync();
      },
      isLoggingIn: loginMutation.isPending,
      isRegistering: registerMutation.isPending,
      loginError: loginMutation.error instanceof Error ? loginMutation.error.message : null,
      setRole: (nextRole) => {
        void switchContextMutation.mutateAsync({ role: nextRole });
      },
      switchMembership: (membershipId) =>
        switchContextMutation.mutateAsync({ membershipId }),
      switchBranch: (branchId) => switchContextMutation.mutateAsync({ branchId }),
      hasCapability: (capability) => user.capabilities.includes(capability),
    };
  }, [
    sessionQuery.data,
    sessionQuery.isLoading,
    isRemoteBackend,
    authModalOpen,
    loginMutation,
    registerMutation,
    logoutMutation,
    switchContextMutation,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}

interface CapabilityGateProps {
  capability: PortalCapability;
  children: ReactNode;
  fallback?: ReactNode;
}

export function CapabilityGate({
  capability,
  children,
  fallback = null,
}: CapabilityGateProps) {
  const { hasCapability } = useAuth();
  return hasCapability(capability) ? <>{children}</> : <>{fallback}</>;
}
