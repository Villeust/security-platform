import { useEffect, useState } from 'react';

import { getCities, getContractors, getFacilities, getPremises, getWorkTypes } from '../services/referenceDataService';
import type { City, Contractor, Facility, Premise, WorkType } from '../types/api';

type ReferenceData = {
  cities: City[];
  facilities: Facility[];
  premises: Premise[];
  workTypes: WorkType[];
  contractors: Contractor[];
};

const emptyData: ReferenceData = {
  cities: [],
  facilities: [],
  premises: [],
  workTypes: [],
  contractors: [],
};

export function useReferenceData() {
  const [data, setData] = useState<ReferenceData>(emptyData);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    Promise.all([getCities(), getFacilities(), getPremises(), getWorkTypes(), getContractors()])
      .then(([cities, facilities, premises, workTypes, contractors]) => {
        if (!isMounted) {
          return;
        }
        setData({ cities, facilities, premises, workTypes, contractors });
        setError(null);
      })
      .catch((requestError: unknown) => {
        console.error('Failed to load reference data', requestError);
        if (isMounted) {
          setError('Не удалось загрузить справочники.');
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return { ...data, isLoading, error };
}
