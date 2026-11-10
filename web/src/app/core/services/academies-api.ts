import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { API_BASE_URL } from '../api-base-url';
import {
  Academy,
  AcademyPage,
  AcademyQuery,
  PAGE_SIZE,
  StyleOption,
} from '../models/academy.models';

interface StyleListResponse {
  items: StyleOption[];
}

interface ComunaListResponse {
  items: string[];
}

@Injectable({ providedIn: 'root' })
export class AcademiesApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL).replace(/\/$/, '');

  listAcademies(query: AcademyQuery = {}): Observable<AcademyPage> {
    let params = new HttpParams()
      .set('page', String(query.page ?? 1))
      .set('page_size', String(query.pageSize ?? PAGE_SIZE));

    if (query.comuna) {
      params = params.set('comuna', query.comuna);
    }
    if (query.style) {
      params = params.set('style', query.style);
    }
    if (query.q) {
      params = params.set('q', query.q);
    }

    return this.http.get<AcademyPage>(`${this.baseUrl}/academies`, { params });
  }

  getAcademy(slug: string): Observable<Academy> {
    return this.http.get<Academy>(`${this.baseUrl}/academies/${encodeURIComponent(slug)}`);
  }

  listStyles(): Observable<StyleOption[]> {
    return this.http
      .get<StyleListResponse>(`${this.baseUrl}/styles`)
      .pipe(map(response => response.items));
  }

  listComunas(): Observable<string[]> {
    return this.http
      .get<ComunaListResponse>(`${this.baseUrl}/comunas`)
      .pipe(map(response => response.items));
  }
}
