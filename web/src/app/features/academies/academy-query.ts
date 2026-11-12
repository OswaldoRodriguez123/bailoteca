import { ParamMap, Params } from '@angular/router';

import { PAGE_SIZE } from '../../core/models/academy.models';

export const REGION_OPTIONS: { slug: string; name: string }[] = [
  { slug: 'arica', name: 'Arica y Parinacota' },
  { slug: 'tarapaca', name: 'Tarapacá' },
  { slug: 'antofagasta', name: 'Antofagasta' },
  { slug: 'atacama', name: 'Atacama' },
  { slug: 'coquimbo', name: 'Coquimbo' },
  { slug: 'valparaiso', name: 'Valparaíso' },
  { slug: 'ohiggins', name: "O'Higgins" },
  { slug: 'maule', name: 'Maule' },
  { slug: 'nuble', name: 'Ñuble' },
  { slug: 'biobio', name: 'Biobío' },
  { slug: 'araucania', name: 'La Araucanía' },
  { slug: 'los-rios', name: 'Los Ríos' },
  { slug: 'los-lagos', name: 'Los Lagos' },
  { slug: 'aysen', name: 'Aysén' },
  { slug: 'magallanes', name: 'Magallanes' },
  { slug: 'metropolitana', name: 'Región Metropolitana' },
  { slug: 'all', name: 'Todas las regiones' },
];

export const REGION_SLUGS: string[] = REGION_OPTIONS.map(option => option.slug);

export const DEFAULT_REGION = 'metropolitana';

export function regionName(slug: string): string {
  return REGION_OPTIONS.find(option => option.slug === slug)?.name ?? slug;
}

export interface ListQuery {
  region: string;
  comuna: string | null;
  style: string | null;
  q: string | null;
  page: number;
}

const STYLE_RE = /^[a-z0-9-]+$/;

function clean(value: string | null): string | null {
  if (value === null) {
    return null;
  }

  const trimmed = value.trim();
  return trimmed || null;
}

export function normalizeQuery(params: ParamMap): ListQuery {
  const regionValue = clean(params.get('region'));
  const region =
    regionValue !== null && REGION_SLUGS.includes(regionValue) ? regionValue : DEFAULT_REGION;
  const comuna = clean(params.get('comuna'));
  const styleValue = clean(params.get('style'));
  const style = styleValue !== null && STYLE_RE.test(styleValue) ? styleValue : null;
  const qValue = clean(params.get('q'));
  const q = qValue !== null && qValue.length >= 2 ? qValue : null;
  const pageValue = Number.parseInt(params.get('page') ?? '', 10);
  const page = Number.isInteger(pageValue) && pageValue >= 1 ? pageValue : 1;

  return { region, comuna, style, q, page };
}

export function queryToParams(query: ListQuery): Params {
  const params: Params = {};

  if (query.region && query.region !== DEFAULT_REGION) {
    params['region'] = query.region;
  }
  if (query.comuna) {
    params['comuna'] = query.comuna;
  }
  if (query.style) {
    params['style'] = query.style;
  }
  if (query.q) {
    params['q'] = query.q;
  }
  params['page'] = query.page;

  return params;
}

export function sameQuery(a: ListQuery, b: ListQuery): boolean {
  return (
    a.region === b.region &&
    a.comuna === b.comuna &&
    a.style === b.style &&
    a.q === b.q &&
    a.page === b.page
  );
}

export function lastPage(total: number, pageSize = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / pageSize));
}
