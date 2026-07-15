import { useCallback, useEffect, useState } from 'react';

import { getRequests } from '../services/requestService';
import type { ContractorRequest, RequestListParams } from '../types/api';

export function useRequests(params: RequestListParams = {}) {
  const [requests, setRequests] = useState<ContractorRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setIsLoading(true);
    return getRequests(params)
      .then((data) => {
        setRequests(data);
        setError(null);
      })
      .catch((requestError: unknown) => {
        console.error('Failed to load contractor requests', requestError);
        setError('Не удалось загрузить заявки.');
      })
      .finally(() => setIsLoading(false));
  }, [JSON.stringify(params)]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { requests, isLoading, error, reload };
}
