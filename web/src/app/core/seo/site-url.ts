import { InjectionToken } from '@angular/core';

export const SITE_URL = new InjectionToken<string>('SITE_URL', {
  providedIn: 'root',
  factory: () => 'https://bailoteca.vercel.app',
});
