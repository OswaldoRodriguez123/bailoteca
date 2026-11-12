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

export type SortKey = 'destacadas' | 'cercanas' | 'nuevas' | 'nombre';
export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'destacadas', label: 'Destacadas' },
  { value: 'cercanas', label: 'Cercanas' },
  { value: 'nuevas', label: 'Nuevas' },
  { value: 'nombre', label: 'A-Z' },
];
export const SORT_KEYS: string[] = SORT_OPTIONS.map(option => option.value);
export const DEFAULT_SORT: SortKey = 'destacadas';

export function regionName(slug: string): string {
  return REGION_OPTIONS.find(option => option.slug === slug)?.name ?? slug;
}

export interface ListQuery {
  region: string;
  comuna: string | null;
  style: string | null;
  q: string | null;
  sort: SortKey;
  lat: number | null;
  lng: number | null;
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

function parseCoord(value: string | null, maxAbs: number): number | null {
  const raw = clean(value);
  if (raw === null) {
    return null;
  }

  const parsed = Number(raw);
  return Number.isFinite(parsed) && Math.abs(parsed) <= maxAbs ? parsed : null;
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
  const sortValue = clean(params.get('sort'));
  let sort: SortKey =
    sortValue !== null && SORT_KEYS.includes(sortValue) ? (sortValue as SortKey) : DEFAULT_SORT;
  let lat = parseCoord(params.get('lat'), 90);
  let lng = parseCoord(params.get('lng'), 180);

  if (sort === 'cercanas' && (lat === null || lng === null)) {
    sort = DEFAULT_SORT;
  }

  if (sort !== 'cercanas') {
    lat = null;
    lng = null;
  }

  return { region, comuna, style, q, sort, lat, lng, page };
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
  if (query.sort && query.sort !== DEFAULT_SORT) {
    params['sort'] = query.sort;
  }
  if (query.sort === 'cercanas') {
    if (query.lat !== null && query.lat !== undefined) {
      params['lat'] = query.lat.toFixed(6);
    }
    if (query.lng !== null && query.lng !== undefined) {
      params['lng'] = query.lng.toFixed(6);
    }
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
    a.sort === b.sort &&
    a.lat === b.lat &&
    a.lng === b.lng &&
    a.page === b.page
  );
}

export function lastPage(total: number, pageSize = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / pageSize));
}
