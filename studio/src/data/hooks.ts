import { useCallback, useState } from 'react';

export interface QueryState<T> {
  data: T | undefined;
  isLoading: boolean;
  isError?: boolean;
  error?: unknown;
  refetch?: () => Promise<unknown>;
}

export interface MutationState<T = unknown> {
  mutate: (value: T) => void;
  mutateAsync?: (value: T) => Promise<void>;
  isPending?: boolean;
}

const query = <T,>(data?: T): QueryState<T> => ({ data, isLoading: false, isError: false });
const mutation = <T,>(): MutationState<T> => ({ mutate: () => undefined, mutateAsync: async () => undefined, isPending: false });

export function useMetrics(_staleTime?: number) { return query<Record<string, any>>(); }
export function useHealthMap(_staleTime?: number) { return query<any>(); }
export function useCIReports(_limit?: number, _staleTime?: number) { return query<any[]>(); }
export function useDashboardEvents(_limit?: number, _staleTime?: number) { return query<any[]>(); }
export function useProviders(_staleTime?: number) { return query<any[]>(); }
export function useTraffic(_staleTime?: number) { return query<any>(); }
export function useDeployGate() { return query<any>(); }
export function useDeploy() { return mutation<any>(); }
export function useCreateBackup() { return mutation<any>(); }
export function useSecurityRescan() { return mutation<any>(); }
export function useToggleDeployGate() { return mutation<any>(); }
export function useAcknowledgeAlert() { return mutation<any>(); }
export function useSkills() { return query<any[]>(); }
export function useMemoryStats(_staleTime?: number) { return query<any>(); }
export function useKnowledgeStats(_staleTime?: number) { return query<any>(); }
export function useRouterConfig() { return query<any>(); }
export function useUpdateRules() { return mutation<any>(); }
export function useCostReport() { return query<any>(); }
export function useBudgetCaps() { return query<any>(); }
export function useROI(_staleTime?: number) { return query<any>(); }
export function useUsage(_staleTime?: number) { return query<any>(); }
export function useUpdateBudgetCap() { return mutation<any>(); }
export function useEvolutionMetrics(_staleTime?: number) { return query<any>(); }
export function useAgents(_staleTime?: number) { return query<any[]>(); }
export function useSessions() { return query<any[]>(); }
export function useSwarm() { return query<any>(); }
export function useTenants() { return query<any[]>(); }
export function useUsers() { return query<any[]>(); }
export function useImpersonateUser() { return mutation<any>(); }
export function useResetTenantUsage() { return mutation<any>(); }
export function useAuditLogs(_limit?: number) { return query<any[]>(); }
export function useRateLimits(_staleTime?: number) { return query<any>(); }
export function useThreatScan(_staleTime?: number) { return query<any>(); }
export function useSecurityFindings() { return query<any[]>(); }
export function useBackups() { return query<any[]>(); }
export function useCreateBackupRecord() { return mutation<any>(); }
export function useRestoreBackup() { return mutation<any>(); }
export function useConfigEntries() { return query<any[]>(); }
export function useUpdateConfig() { return mutation<any>(); }
export function useDeployGateStatus() { return query<any>(); }
export function useToggleDeployGateStatus() { return mutation<any>(); }
export function useFeatureFlags() { return query<any[]>(); }
export function useUpdateFeatureFlag() { return mutation<any>(); }
export function useWorkspaces() { return query<any[]>(); }

// Keep these imports available to strict builds without coupling this temporary
// compatibility layer to a particular query client implementation.
export function useMutationSeam<T>(handler?: (value: T) => Promise<void> | void) {
  const [isPending, setPending] = useState(false);
  const mutate = useCallback((value: T) => {
    setPending(true);
    Promise.resolve(handler?.(value)).finally(() => setPending(false));
  }, [handler]);
  return { mutate, isPending };
}
