import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Params, RouterLink } from '@angular/router';

import { lastPage } from '../../academy-query';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  selector: 'app-pagination',
  template: `
    @if (total() > 0) {
      <nav
        class="flex items-center justify-between gap-4"
        aria-label="Paginación"
      >
        @if (page() > 1) {
          <a
            [routerLink]="['/']"
            [queryParams]="paramsFor(page() - 1)"
            rel="prev"
            class="text-sm font-medium text-accent-ink underline-offset-4 transition-colors hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
          >
            ← Anterior
          </a>
        } @else {
          <span aria-disabled="true" class="text-sm font-medium text-muted">← Anterior</span>
        }

        <p class="text-sm text-muted">Página {{ page() }} de {{ last() }}</p>

        @if (page() < last()) {
          <a
            [routerLink]="['/']"
            [queryParams]="paramsFor(page() + 1)"
            rel="next"
            class="text-sm font-medium text-accent-ink underline-offset-4 transition-colors hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
          >
            Siguiente →
          </a>
        } @else {
          <span aria-disabled="true" class="text-sm font-medium text-muted">Siguiente →</span>
        }
      </nav>
    }
  `,
})
export class Pagination {
  readonly page = input.required<number>();
  readonly total = input.required<number>();
  readonly pageSize = input.required<number>();
  readonly queryParams = input<Params | null>(null);

  protected readonly last = computed(() => lastPage(this.total(), this.pageSize()));

  protected paramsFor(page: number): Params {
    return { ...(this.queryParams() ?? {}), page };
  }
}
