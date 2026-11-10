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
      class="group block h-full rounded-2xl border border-stone-200 bg-white p-6 transition-shadow hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600"
    >
      <div class="flex items-start justify-between gap-3">
        <h2 class="text-lg font-semibold text-stone-900 transition-colors group-hover:text-rose-600">
          {{ academy().name }}
        </h2>
        @if (academy().status === 'closed') {
          <span class="shrink-0 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800">
            Cerrada
          </span>
        }
      </div>

      @if (comunas().length) {
        <p class="mt-1 text-sm text-stone-500">{{ comunas().join(' · ') }}</p>
      }

      @if (academy().description) {
        <p class="mt-3 text-sm leading-relaxed text-stone-600">{{ description() }}</p>
      }

      <div class="mt-4">
        <app-style-badges [styles]="academy().styles" />
      </div>
    </a>
  `,
})
export class AcademyCard {
  readonly academy = input.required<Academy>();
  readonly queryParams = input<Params | null>(null);

  protected readonly comunas = computed(() => uniqueComunas(this.academy()));
  protected readonly description = computed(() => truncated(this.academy().description));
}
