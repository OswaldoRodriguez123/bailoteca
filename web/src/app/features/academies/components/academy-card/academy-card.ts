import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Params, RouterLink } from '@angular/router';

import { Academy } from '../../../../core/models/academy.models';
import { truncated, uniqueComunas } from '../../academy-display';
import { StyleBadges } from '../style-badges/style-badges';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, StyleBadges],
  selector: 'app-academy-card',
  template: `
    <a
      [routerLink]="['/academias', academy().slug]"
      [queryParams]="queryParams()"
      class="group grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-start gap-4 border-b border-line py-5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent-ink sm:grid-cols-[6rem_minmax(0,1fr)_auto] sm:gap-6"
    >
      @if (academy().google?.thumbnail) {
        <img
          [src]="academy().google!.thumbnail!"
          alt=""
          width="96"
          height="96"
          class="h-18 w-18 border border-ink object-cover sm:h-24 sm:w-24"
          loading="lazy"
        />
      } @else {
        <div
          aria-hidden="true"
          class="flex h-18 w-18 items-center justify-center border border-line bg-paper-deep font-display text-xl font-bold text-ink/50 sm:h-24 sm:w-24 sm:text-2xl"
        >
          {{ initials() }}
        </div>
      }

      <div class="min-w-0">
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2
            class="break-words font-display text-xl font-bold leading-tight tracking-tight text-ink transition-colors group-hover:text-accent-ink sm:text-2xl"
          >
            {{ academy().name }}
          </h2>
          @if (academy().status === 'closed') {
            <span class="border border-ink px-2 py-0.5 text-xs font-medium text-ink">Cerrada</span>
          }
        </div>

        @if (comunas().length || (academy().google?.rating ?? null) !== null) {
          <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            @if (comunas().length) {
              <span>{{ comunas().join(' · ') }}</span>
            }
            @if (academy().google && academy().google!.rating !== null) {
              <span class="tabular-nums text-ink-soft">
                ★ {{ academy().google!.rating }}
                @if (academy().google!.reviews !== null) {
                  <span class="text-muted">({{ academy().google!.reviews }})</span>
                }
              </span>
            }
          </p>
        }

        @if (academy().description) {
          <p class="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-soft">
            {{ description() }}
          </p>
        }

        <div class="mt-2">
          <app-style-badges [styles]="academy().styles" />
        </div>
      </div>

      <span
        aria-hidden="true"
        class="pt-1 text-lg text-accent-ink transition-transform group-hover:translate-x-1 motion-reduce:transform-none"
      >
        →
      </span>
    </a>
  `,
})
export class AcademyCard {
  readonly academy = input.required<Academy>();
  readonly queryParams = input<Params | null>(null);

  protected readonly comunas = computed(() => uniqueComunas(this.academy()));
  protected readonly description = computed(() => truncated(this.academy().description));
  protected readonly initials = computed(() =>
    this.academy()
      .name.split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map(word => word[0]?.toUpperCase() ?? '')
      .join(''),
  );
}
