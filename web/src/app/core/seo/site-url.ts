import { InjectionToken } from '@angular/core';

import { environment } from '../../../environments/environment';

/**
 * Origen absoluto del sitio. Sale de `site.config.json` (vía
 * `scripts/write-env.mjs`), así que cambiar de dominio no obliga a tocar código.
 */
export const SITE_URL = new InjectionToken<string>('SITE_URL', {
  providedIn: 'root',
  factory: () => environment.siteUrl,
});
