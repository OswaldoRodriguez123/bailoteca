import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { ParamMap, Params, ActivatedRoute, Router } from '@angular/router';
import {
  EMPTY,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  map,
  merge,
  of,
  switchMap,
  tap,
} from 'rxjs';

import { AcademyPage, PAGE_SIZE, StyleOption } from '../../../core/models/academy.models';
import { errorMessage } from '../../../core/http/error-message';
import { SeoService } from '../../../core/seo/seo.service';
import { SITE_URL } from '../../../core/seo/site-url';
import { AcademiesApiService } from '../../../core/services/academies-api';
import { EmptyState } from '../../../shared/components/empty-state/empty-state';
import { ErrorState } from '../../../shared/components/error-state/error-state';
import { LoadingGrid } from '../../../shared/components/loading-grid/loading-grid';
import {
  DEFAULT_REGION,
  DEFAULT_SORT,
  lastPage,
  ListQuery,
  normalizeQuery,
  queryToParams,
  REGION_OPTIONS,
  sameQuery,
  SORT_KEYS,
  SORT_OPTIONS,
  SortKey,
} from '../academy-query';
import { AcademyCard } from '../components/academy-card/academy-card';
import { FilterBar } from '../components/filter-bar/filter-bar';
import { Pagination } from '../components/pagination/pagination';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AcademyCard, EmptyState, ErrorState, FilterBar, LoadingGrid, Pagination],
  selector: 'app-academy-list',
  templateUrl: './academy-list.html',
})
export class AcademyListPage {
  private readonly api = inject(AcademiesApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly seo = inject(SeoService);
  private readonly siteUrl = inject(SITE_URL);
  private readonly search$ = new Subject<string>();
  private readonly reload$ = new Subject<void>();

  readonly query = signal<ListQuery>({
    region: DEFAULT_REGION,
    comuna: null,
    style: null,
    q: null,
    sort: DEFAULT_SORT,
    lat: null,
    lng: null,
    page: 1,
  });
  readonly queryParams = computed<Params>(() => queryToParams(this.query()));
  readonly page = signal<AcademyPage | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly styles = signal<StyleOption[]>([]);
  readonly comunas = signal<string[]>([]);
  readonly filtersError = signal(false);
  readonly geoError = signal(false);
  readonly regions = REGION_OPTIONS;
  readonly sortOptions = SORT_OPTIONS;
  readonly emptyMessage = computed(() => {
    const region = this.query().region;

    if (region === 'all') {
      return 'Aún no hay academias publicadas en Chile.';
    }
    if (region !== DEFAULT_REGION) {
      return 'Aún no hay academias en esta región.';
    }
    return 'No encontramos academias con esos filtros.';
  });

  constructor() {
    this.api
      .listStyles()
      .pipe(
        catchError(() => {
          this.filtersError.set(true);
          return of([]);
        }),
        takeUntilDestroyed(),
      )
      .subscribe(styles => this.styles.set(styles));

    toObservable(this.query)
      .pipe(
        map(query => query.region),
        distinctUntilChanged(),
        switchMap(region =>
          this.api.listComunas(region).pipe(
            catchError(() => {
              this.filtersError.set(true);
              return of([] as string[]);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(comunas => {
        this.comunas.set(comunas);

        const query = this.query();
        if (query.comuna && !comunas.includes(query.comuna)) {
          this.navigate({ region: query.region, comuna: null, page: 1 }, { replaceUrl: true });
        }
      });

    const query$ = this.route.queryParamMap.pipe(
      map(params => normalizeQuery(params)),
      distinctUntilChanged(sameQuery),
      tap(query => {
        this.query.set(query);
        this.seo.set({
          title: 'Academias de baile en Chile',
          description:
            'Directorio de academias de baile en Chile: salsa, bachata, tango y otros ritmos latinos. Encuentra clases por región, comuna y estilo.',
          path: '/',
          image: '/og-image.png',
          imageAlt: 'Bailoteca — academias de baile en Chile',
          imageWidth: 1200,
          imageHeight: 630,
          noindex: Boolean(
            query.comuna ||
            query.style ||
            query.q ||
            query.page > 1 ||
            query.region !== DEFAULT_REGION ||
            query.sort !== DEFAULT_SORT,
          ),
          jsonLd: [
            {
              '@context': 'https://schema.org',
              '@type': 'WebSite',
              name: 'Bailoteca',
              url: `${this.siteUrl}/`,
              inLanguage: 'es-CL',
              publisher: { '@id': `${this.siteUrl}/#organization` },
              potentialAction: {
                '@type': 'SearchAction',
                target: {
                  '@type': 'EntryPoint',
                  urlTemplate: `${this.siteUrl}/?q={search_term_string}`,
                },
                'query-input': 'required name=search_term_string',
              },
            },
            {
              '@context': 'https://schema.org',
              '@type': 'Organization',
              '@id': `${this.siteUrl}/#organization`,
              name: 'Bailoteca',
              url: `${this.siteUrl}/`,
              logo: `${this.siteUrl}/icon-512.png`,
              email: 'oswaldo_rodriguez_1@hotmail.com',
              sameAs: ['https://github.com/OswaldoRodriguez123/bailoteca'],
              description:
                'Directorio de academias de baile en Chile, con sedes, estilos y datos de contacto.',
            },
          ],
        });

        if (this.needsRewrite(this.route.snapshot.queryParamMap, query)) {
          void this.router.navigate([], {
            relativeTo: this.route,
            queryParams: queryToParams(query),
            replaceUrl: true,
          });
        }
      }),
    );

    merge(query$, this.reload$.pipe(map(() => this.query())))
      .pipe(
        switchMap(query => {
          this.loading.set(true);
          this.error.set(null);

          return this.api
            .listAcademies({
              region: query.region,
              comuna: query.comuna,
              style: query.style,
              q: query.q,
              sort: query.sort,
              lat: query.lat,
              lng: query.lng,
              page: query.page,
              pageSize: PAGE_SIZE,
            })
            .pipe(
              map(page => ({ page, query })),
              catchError(error => {
                this.error.set(errorMessage(error));
                this.loading.set(false);
                return EMPTY;
              }),
            );
        }),
        takeUntilDestroyed(),
      )
      .subscribe(({ page, query }) => {
        const last = lastPage(page.total);

        if (page.items.length === 0 && page.total > 0 && query.page > last) {
          void this.router.navigate([], {
            relativeTo: this.route,
            queryParams: { ...queryToParams(query), page: last },
            replaceUrl: true,
          });
          return;
        }

        this.page.set(page);
        this.loading.set(false);
      });

    this.search$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        map(value => value.trim()),
        takeUntilDestroyed(),
      )
      .subscribe(value => {
        if (value.length === 1) {
          return;
        }

        this.navigate({ q: value.length >= 2 ? value : null, page: 1 });
      });
  }

  onRegion(region: string): void {
    this.navigate({ region, comuna: null, page: 1 });
  }

  onComuna(comuna: string | null): void {
    this.navigate({ comuna, page: 1 });
  }

  onStyle(style: string | null): void {
    this.navigate({ style, page: 1 });
  }

  onQ(value: string): void {
    this.search$.next(value);
  }

  onSort(sort: string): void {
    if (!SORT_KEYS.includes(sort)) {
      return;
    }
    if (sort !== 'cercanas') {
      this.geoError.set(false);
      this.navigate({ sort: sort as SortKey, lat: null, lng: null, page: 1 });
      return;
    }
    const geo = typeof navigator !== 'undefined' ? navigator.geolocation : undefined;
    if (!geo) return this.geoDenied();
    geo.getCurrentPosition(
      position => {
        this.geoError.set(false);
        this.navigate({ sort: 'cercanas', lat: position.coords.latitude,
                        lng: position.coords.longitude, page: 1 });
      },
      () => this.geoDenied(),
      { maximumAge: 600_000, timeout: 10_000 },
    );
  }

  clearFilters(): void {
    this.geoError.set(false);
    void this.router.navigate(['/']);
  }

  retry(): void {
    this.reload$.next();
  }

  private navigate(partial: Partial<ListQuery>, options: { replaceUrl?: boolean } = {}): void {
    const next = { ...this.query(), ...partial };
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: queryToParams(next),
      replaceUrl: options.replaceUrl ?? false,
    });
  }

  private geoDenied(): void {
    this.geoError.set(true);
    this.navigate({ sort: DEFAULT_SORT, lat: null, lng: null, page: 1 }, { replaceUrl: true });
  }

  private needsRewrite(raw: ParamMap, query: ListQuery): boolean {
    return (
      (raw.get('region') ?? null) !== (query.region === DEFAULT_REGION ? null : query.region) ||
      (raw.get('comuna') ?? null) !== query.comuna ||
      (raw.get('style') ?? null) !== query.style ||
      (raw.get('q') ?? null) !== query.q ||
      (raw.get('sort') ?? null) !== (query.sort === DEFAULT_SORT ? null : query.sort) ||
      (raw.get('lat') === null ? null : Number(raw.get('lat'))) !== query.lat ||
      (raw.get('lng') === null ? null : Number(raw.get('lng'))) !== query.lng ||
      (raw.get('page') !== null && raw.get('page') !== String(query.page))
    );
  }
}
