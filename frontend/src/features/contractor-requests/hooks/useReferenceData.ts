import axios from 'axios';
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
    const controller = new AbortController();
    setIsLoading(true);

    Promise.all([
      getCities(controller.signal),
      getFacilities(controller.signal),
      getPremises(controller.signal),
      getWorkTypes(controller.signal),
      getContractors(controller.signal),
    ])
      .then(([cities, facilities, premises, workTypes, contractors]) => {
        if (controller.signal.aborted) return;
        setData({ cities, facilities, premises, workTypes, contractors });
        setError(null);
      })
      .catch((requestError: unknown) => {
        if (axios.isCancel(requestError) || controller.signal.aborted) return;
        console.error('Failed to load reference data', requestError);
        setError('Не удалось загрузить справочники.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, []);

  return { ...data, isLoading, error };
}
