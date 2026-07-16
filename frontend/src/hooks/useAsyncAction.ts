import { useCallback, useRef, useState } from 'react';

type AsyncFn<TArgs extends unknown[], TResult> = (...args: TArgs) => Promise<TResult>;

export function useAsyncAction<TArgs extends unknown[], TResult>(action: AsyncFn<TArgs, TResult>) {
  const runningRef = useRef(false);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (...args: TArgs) => {
    if (runningRef.current) return undefined;
    runningRef.current = true;
    setLoading(true);
    try {
      return await action(...args);
    } finally {
      runningRef.current = false;
      setLoading(false);
    }
  }, [action]);

  return { run, loading, disabled: loading };
}
