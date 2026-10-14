import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * Single-client enforcement: pages and contexts must use the shared
 * src/api/axios instance (token interceptor + 401 handling), never
 * import `axios` directly or rebuild the API base URL per page.
 */
const SRC = join(process.cwd(), 'src');
const SCOPES = ['pages', 'contexts'];

function jsxFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return jsxFiles(full);
    if (name.includes('.test.')) return []; // tests may mock axios legitimately
    return full.endsWith('.jsx') || full.endsWith('.js') ? [full] : [];
  });
}

describe('single API client', () => {
  const files = SCOPES.flatMap((scope) => jsxFiles(join(SRC, scope)));

  it('has files to scan', () => {
    expect(files.length).toBeGreaterThan(10);
  });

  it.each(files.map((f) => [f.slice(SRC.length)]))(
    '%s imports no direct axios',
    (rel) => {
      const text = readFileSync(join(SRC, rel), 'utf8');
      expect(text).not.toMatch(/from ['"]axios['"]/);
      expect(text).not.toMatch(/require\(['"]axios['"]\)/);
    }
  );

  it.each(files.map((f) => [f.slice(SRC.length)]))(
    '%s defines no per-page API_URL',
    (rel) => {
      const text = readFileSync(join(SRC, rel), 'utf8');
      expect(text).not.toMatch(/API_URL/);
    }
  );
});
