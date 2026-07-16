import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

describe('Phase D frontend stability infrastructure', () => {
  it('uses global and route error boundaries with Russian fallback copy', () => {
    const boundary = read('src/components/errors/ErrorBoundary.tsx');
    const app = read('src/App.tsx');
    assert.match(boundary, /Ошибка приложения/);
    assert.match(boundary, /Что-то пошло не так/);
    assert.match(boundary, /Reference:/);
    assert.match(boundary, /copyCorrelationId/);
    assert.match(app, /ErrorBoundary scope="global"/);
    assert.match(app, /RouteErrorBoundary scope/);
  });

  it('normalizes legacy and standardized API errors', () => {
    const parser = read('src/lib/apiError.ts');
    for (const status of ['401', '403', '404', '409', '413', '422', '500']) {
      assert.match(parser, new RegExp(`status === ${status}|status && status >= ${status}`));
    }
    assert.match(parser, /CSRF_TOKEN_INVALID/);
    assert.match(parser, /PASSWORD_CHANGE_REQUIRED/);
    assert.match(parser, /ECONNABORTED/);
    assert.match(parser, /navigator\.onLine/);
  });

  it('tracks correlation IDs and deduplicates toasts', () => {
    const api = read('src/services/api.ts');
    const correlation = read('src/lib/correlation.ts');
    const toast = read('src/lib/toast.ts');
    assert.match(api, /x-correlation-id/);
    assert.match(correlation, /sessionStorage/);
    assert.match(correlation, /clipboard\.writeText/);
    assert.match(toast, /shouldNotify/);
    assert.match(toast, /recent = new Map/);
  });

  it('supports abortable requests and double-submit protection', () => {
    const requestService = read('src/features/contractor-requests/services/requestService.ts');
    const referenceHook = read('src/features/contractor-requests/hooks/useReferenceData.ts');
    const asyncAction = read('src/hooks/useAsyncAction.ts');
    const button = read('src/components/design-system/Button.tsx');
    assert.match(requestService, /signal\?: AbortSignal/);
    assert.match(referenceHook, /AbortController/);
    assert.match(referenceHook, /controller\.abort/);
    assert.match(asyncAction, /runningRef/);
    assert.match(button, /disabled=\{Boolean\(props\.disabled\) \|\| Boolean\(props\.loading\)\}/);
  });

  it('lazy-loads major route modules with loading fallbacks', () => {
    const app = read('src/App.tsx');
    assert.match(app, /lazy\(\(\) => import\('\.\/features\/admin/);
    assert.match(app, /lazy\(\(\) => import\('\.\/features\/workflow-center/);
    assert.match(app, /lazy\(\(\) => import\('\.\/features\/contractor-portal/);
    assert.match(app, /Suspense fallback=\{<PageLoader/);
  });

  it('keeps unified loading and empty-state primitives', () => {
    const loader = read('src/components/design-system/Loader.tsx');
    const empty = read('src/components/design-system/EmptyState.tsx');
    assert.match(loader, /PageLoader/);
    assert.match(loader, /InlineLoader/);
    assert.match(loader, /ButtonLoader/);
    assert.match(empty, /primaryAction/);
    assert.match(empty, /secondaryAction/);
  });
});
