import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Params, RouterLink } from '@angular/router';
import { Observable, Subject, catchError, map, merge, of, switchMap, tap } from 'rxjs';

import { Academy } from '../../../core/models/academy.models';
import { errorMessage } from '../../../core/http/error-message';
import { AcademiesApiService } from '../../../core/services/academies-api';
import { EmptyState } from '../../../shared/components/empty-state/empty-state';
import { ErrorState } from '../../../shared/components/error-state/error-state';
import { LoadingGrid } from '../../../shared/components/loading-grid/loading-grid';
import { linkLabel, mapUrl } from '../academy-display';
import { StyleBadges } from '../components/style-badges/style-badges';

const LIST_QUERY_KEYS = ['comuna', 'style', 'q', 'page'] as const;

interface LoadResult {
  academy: Academy | null;
  error: unknown;
}

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [EmptyState, ErrorState, LoadingGrid, RouterLink, StyleBadges],
  selector: 'app-academy-detail',
  templateUrl: './academy-detail.html',
})
export class AcademyDetailPage {
  private readonly api = inject(AcademiesApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly retry$ = new Subject<void>();
  private currentSlug = '';

  readonly academy = signal<Academy | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly error = signal<string | null>(null);
  readonly backQuery = signal<Params>({});

  constructor() {
    const slug$ = this.route.paramMap.pipe(map(params => params.get('slug') ?? ''));
    const retrySlug$ = this.retry$.pipe(map(() => this.currentSlug));

    merge(slug$, retrySlug$)
      .pipe(
        tap(slug => {
          this.currentSlug = slug;
          this.captureBackQuery();
          this.loading.set(true);
          this.notFound.set(false);
          this.error.set(null);
          this.academy.set(null);
        }),
        switchMap(slug =>
          this.api.getAcademy(slug).pipe(
            map((academy): LoadResult => ({ academy, error: null })),
            catchError((error): Observable<LoadResult> => of({ academy: null, error })),
          ),
        ),
      )
      .subscribe(({ academy, error }) => {
        if (error) {
          if (error instanceof HttpErrorResponse && error.status === 404) {
            this.notFound.set(true);
          } else {
            this.error.set(errorMessage(error));
          }
        } else {
          this.academy.set(academy);
        }

        this.loading.set(false);
      });
  }

  retry(): void {
    this.retry$.next();
  }

  protected linkLabel = linkLabel;
  protected mapUrl = mapUrl;

  private captureBackQuery(): void {
    const params = this.route.snapshot.queryParamMap;
    const kept: Params = {};

    for (const key of LIST_QUERY_KEYS) {
      const value = params.get(key);

      if (value !== null) {
        kept[key] = value;
      }
    }

    this.backQuery.set(kept);
  }
}
