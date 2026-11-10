import { ParamMap, Params } from '@angular/router';

import { PAGE_SIZE } from '../../core/models/academy.models';

export interface ListQuery {
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
  const comuna = clean(params.get('comuna'));
  const styleValue = clean(params.get('style'));
  const style = styleValue !== null && STYLE_RE.test(styleValue) ? styleValue : null;
  const qValue = clean(params.get('q'));
  const q = qValue !== null && qValue.length >= 2 ? qValue : null;
  const pageValue = Number.parseInt(params.get('page') ?? '', 10);
  const page = Number.isInteger(pageValue) && pageValue >= 1 ? pageValue : 1;

  return { comuna, style, q, page };
}

export function queryToParams(query: ListQuery): Params {
  const params: Params = {};

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
    a.comuna === b.comuna && a.style === b.style && a.q === b.q && a.page === b.page
  );
}

export function lastPage(total: number, pageSize = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / pageSize));
}
