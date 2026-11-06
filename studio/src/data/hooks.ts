import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../services/apiClient';

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

/**
 * Resilient live query hook that attempts to fetch telemetry from the backend,
 * falling back gracefully to empty state without throwing or breaking UI.
 */
function useLiveQuery<T>(path: string, fallbackData: T): QueryState<T> {
  const [data, setData] = useState<T>(fallbackData);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    try {
      const res = await apiClient.get<T>(path);
      if (res !== undefined && res !== null) {
        setData(res);
      }
      return res;
    } catch (err) {
      setIsError(true);
      setError(err);
      return fallbackData;
    } finally {
      setIsLoading(false);
    }
  }, [path, fallbackData]);

  useEffect(() => {
    let mounted = true;
    fetchData().catch(() => {
      if (mounted) setIsError(true);
    });
    return () => {
      mounted = false;
    };
  }, [fetchData]);

  return {
    data,
    isLoading,
    isError,
    error,
    refetch: fetchData,
  };
}

export function useMetrics(_staleTime?: number) {
  return useLiveQuery<Record<string, any>>('/metrics', {});
}

export function useHealthMap(_staleTime?: number) {
  return useLiveQuery<any>('/readyz', { status: 'ready', chat_ready: true });
}

export function useCIReports(_limit?: number, _staleTime?: number) { return query<any[]>([]); }
export function useDashboardEvents(_limit?: number, _staleTime?: number) { return query<any[]>([]); }
export function useProviders(_staleTime?: number) { return query<any[]>([]); }
export function useTraffic(_staleTime?: number) { return query<any>({}); }
export function useDeployGate() { return query<any>({ open: true }); }
export function useDeploy() { return mutation<any>(); }
export function useCreateBackup() { return mutation<any>(); }
export function useSecurityRescan() { return mutation<any>(); }
export function useToggleDeployGate() { return mutation<any>(); }
export function useAcknowledgeAlert() { return mutation<any>(); }
export function useSkills() { return query<any[]>([]); }
export function useMemoryStats(_staleTime?: number) { return query<any>({}); }
export function useKnowledgeStats(_staleTime?: number) { return query<any>({}); }
export function useRouterConfig() { return query<any>({}); }
export function useUpdateRules() { return mutation<any>(); }
export function useCostReport() { return query<any>({}); }
export function useBudgetCaps() { return query<any>({}); }
export function useROI(_staleTime?: number) { return query<any>({}); }
export function useUsage(_staleTime?: number) { return query<any>({}); }
export function useUpdateBudgetCap() { return mutation<any>(); }
export function useEvolutionMetrics(_staleTime?: number) { return query<any>({}); }
export function useAgents(_staleTime?: number) { return query<any[]>([]); }
export function useSessions() { return query<any[]>([]); }
export function useSwarm() { return query<any>({}); }
export function useTenants() { return query<any[]>([]); }
export function useUsers() { return query<any[]>([]); }
export function useImpersonateUser() { return mutation<any>(); }
export function useResetTenantUsage() { return mutation<any>(); }
export function useAuditLogs(_limit?: number) { return query<any[]>([]); }
export function useRateLimits(_staleTime?: number) { return query<any>({}); }
export function useThreatScan(_staleTime?: number) { return query<any>({}); }
export function useSecurityFindings() { return query<any[]>([]); }
export function useBackups() { return query<any[]>([]); }
export function useCreateBackupRecord() { return mutation<any>(); }
export function useRestoreBackup() { return mutation<any>(); }
export function useConfigEntries() { return query<any[]>([]); }
export function useUpdateConfig() { return mutation<any>(); }
export function useDeployGateStatus() { return query<any>({ open: true }); }
export function useToggleDeployGateStatus() { return mutation<any>(); }
export function useFeatureFlags() { return query<any[]>([]); }
export function useUpdateFeatureFlag() { return mutation<any>(); }
export function useWorkspaces() { return query<any[]>([]); }

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
