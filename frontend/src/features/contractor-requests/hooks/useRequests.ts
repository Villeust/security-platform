import axios from 'axios';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { getRequests } from '../services/requestService';
import type { ContractorRequest, RequestListParams } from '../types/api';

export function useRequests(params: RequestListParams = {}) {
  const [requests, setRequests] = useState<ContractorRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const stableParams = useMemo(() => params, [JSON.stringify(params)]);

  const reload = useCallback((signal?: AbortSignal) => {
    setIsLoading(true);
    return getRequests(stableParams, signal)
      .then((data) => {
        if (signal?.aborted) return;
        setRequests(data);
        setError(null);
      })
      .catch((requestError: unknown) => {
        if (axios.isCancel(requestError) || signal?.aborted) return;
        console.error('Failed to load contractor requests', requestError);
        setError('Не удалось загрузить заявки.');
      })
      .finally(() => {
        if (!signal?.aborted) setIsLoading(false);
      });
  }, [stableParams]);

  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal);
    return () => controller.abort();
  }, [reload]);

  return { requests, isLoading, error, reload };
}
