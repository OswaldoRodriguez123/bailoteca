import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Params, RouterLink } from '@angular/router';
import { Observable, Subject, catchError, map, merge, of, switchMap, tap } from 'rxjs';

import { Academy } from '../../../core/models/academy.models';
import { errorMessage } from '../../../core/http/error-message';
import { SeoJsonLd, SeoService } from '../../../core/seo/seo.service';
import { SITE_URL } from '../../../core/seo/site-url';
import { AcademiesApiService } from '../../../core/services/academies-api';
import { EmptyState } from '../../../shared/components/empty-state/empty-state';
import { ErrorState } from '../../../shared/components/error-state/error-state';
import { LoadingGrid } from '../../../shared/components/loading-grid/loading-grid';
import { linkHref, linkLabel, mapUrl } from '../academy-display';
import { StyleBadges } from '../components/style-badges/style-badges';

const LIST_QUERY_KEYS = ['comuna', 'style', 'q', 'page'] as const;

interface LoadResult {
  academy: Academy | null;
  error: unknown;
}

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, EmptyState, ErrorState, LoadingGrid, RouterLink, StyleBadges],
  selector: 'app-academy-detail',
  templateUrl: './academy-detail.html',
})
export class AcademyDetailPage {
  private readonly api = inject(AcademiesApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly seo = inject(SeoService);
  private readonly siteUrl = inject(SITE_URL);
  private readonly retry$ = new Subject<void>();
  private currentSlug = '';

  readonly academy = signal<Academy | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly error = signal<string | null>(null);
  readonly backQuery = signal<Params>({});

  private readonly contactKinds = new Set(['phone', 'email', 'whatsapp']);

  protected readonly contactLinks = computed(() => {
    const academy = this.academy();
    const hasGooglePhone = Boolean(academy?.google?.phone);

    return (academy?.links ?? []).filter(link => {
      const kind = link.kind.toLowerCase();
      if (!this.contactKinds.has(kind)) {
        return false;
      }
      return !(kind === 'phone' && hasGooglePhone);
    });
  });

  protected readonly otherLinks = computed(() => {
    const academy = this.academy();
    const hasGoogleWebsite = Boolean(academy?.google?.website);

    return (academy?.links ?? []).filter(link => {
      const kind = link.kind.toLowerCase();
      if (this.contactKinds.has(kind)) {
        return false;
      }
      return !(kind === 'web' && hasGoogleWebsite);
    });
  });

  protected readonly initials = computed(() =>
    (this.academy()?.name ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map(word => word[0]?.toUpperCase() ?? '')
      .join(''),
  );

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
        takeUntilDestroyed(),
      )
      .subscribe(({ academy, error }) => {
        if (error) {
          if (error instanceof HttpErrorResponse && error.status === 404) {
            this.notFound.set(true);
            this.seo.set({
              title: 'Academia no encontrada',
              description: 'La academia que buscas no está en el directorio de Bailoteca.',
              path: `/academias/${this.currentSlug}`,
              noindex: true,
            });
          } else {
            this.error.set(errorMessage(error));
            this.seo.set({
              title: 'No pudimos cargar la academia',
              description: 'Hubo un problema al cargar esta academia en Bailoteca.',
              path: `/academias/${this.currentSlug}`,
              noindex: true,
            });
          }
        } else if (academy) {
          this.academy.set(academy);
          this.updateMetadata(academy);
        }

        this.loading.set(false);
      });
  }

  retry(): void {
    this.retry$.next();
  }

  protected linkHref = linkHref;
  protected linkLabel = linkLabel;
  protected mapUrl = mapUrl;

  protected googleHoursEntries(
    hours: Record<string, string> | null,
  ): [string, string][] {
    if (!hours) {
      return [];
    }
    return Object.entries(hours);
  }

  private updateMetadata(academy: Academy): void {
    const comuna = academy.locations[0]?.comuna?.trim() || 'Santiago';
    const path = `/academias/${academy.slug}`;
    const description = academy.description?.trim() || `Academia de baile en ${comuna}.`;
    const jsonLd: SeoJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'DanceSchool',
      name: academy.name,
      description: academy.description?.trim() || undefined,
      url: `${this.siteUrl}${path}`,
    };

    if (academy.locations.length > 0) {
      jsonLd['address'] = academy.locations.map(location => ({
        '@type': 'PostalAddress',
        streetAddress: location.address ?? undefined,
        addressLocality: location.comuna ?? undefined,
        addressCountry: 'CL',
      }));
    }

    if (academy.links.length > 0) {
      jsonLd['sameAs'] = academy.links.map(link => link.url);
    }

    this.seo.set({
      title: `${academy.name} — ${comuna}`,
      description,
      path,
      jsonLd,
    });
  }

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
