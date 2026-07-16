import { useEffect, type DependencyList } from 'react';

export function useAbortableEffect(effect: (signal: AbortSignal) => void | Promise<void>, deps: DependencyList) {
  useEffect(() => {
    const controller = new AbortController();
    void effect(controller.signal);
    return () => controller.abort();
  }, deps);
}
