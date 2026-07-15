import { useCallback, useEffect, useState } from 'react';

import { getRequests } from '../services/requestService';
import type { ContractorRequest } from '../types/api';

export function useRequests() {
  const [requests, setRequests] = useState<ContractorRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setIsLoading(true);
    return getRequests()
      .then((data) => {
        setRequests(data);
        setError(null);
      })
      .catch((requestError: unknown) => {
        console.error('Failed to load contractor requests', requestError);
        setError('Не удалось загрузить заявки.');
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { requests, isLoading, error, reload };
}
