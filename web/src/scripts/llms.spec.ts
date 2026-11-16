import { describe, expect, it } from 'vitest';

import { renderLlms } from '../../scripts/llms.mjs';

const SITE = 'https://sitio.test';
const API = 'https://api.test';

describe('renderLlms', () => {
  const text = renderLlms({ siteUrl: SITE, apiBaseUrl: API });

  it('enlaza el sitio y la API con las URLs recibidas', () => {
    expect(text).toContain(`(${SITE}/)`);
    expect(text).toContain(`(${SITE}/sitemap.xml)`);
    expect(text).toContain(`(${API}/academies)`);
  });

  it('no publica URLs fuera del sitio ni de la API', () => {
    const urls = text.match(/https?:\/\/[^\s)]+/g) ?? [];

    expect(urls.length).toBeGreaterThan(0);
    for (const url of urls) {
      const allowed = url.startsWith(`${SITE}/`) || url.startsWith(`${API}/`);
      expect(allowed, url).toBe(true);
    }
  });
});
