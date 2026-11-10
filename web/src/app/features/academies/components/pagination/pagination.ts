import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { lastPage } from '../../academy-query';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-pagination',
  template: `
    @if (total() > 0) {
      <nav
        class="mt-8 flex items-center justify-between gap-4 border-t border-line pt-4"
        aria-label="Paginación"
      >
        <button
          type="button"
          [disabled]="page() <= 1"
          (click)="go(page() - 1)"
          class="text-sm font-medium text-accent-ink underline-offset-4 transition-colors hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
        >
          ← Anterior
        </button>

        <p class="text-sm text-muted">Página {{ page() }} de {{ last() }}</p>

        <button
          type="button"
          [disabled]="page() >= last()"
          (click)="go(page() + 1)"
          class="text-sm font-medium text-accent-ink underline-offset-4 transition-colors hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
        >
          Siguiente →
        </button>
      </nav>
    }
  `,
})
export class Pagination {
  readonly page = input.required<number>();
  readonly total = input.required<number>();
  readonly pageSize = input.required<number>();
  readonly pageChange = output<number>();

  protected readonly last = computed(() => lastPage(this.total(), this.pageSize()));

  protected go(page: number): void {
    if (page >= 1 && page <= this.last()) {
      this.pageChange.emit(page);
    }
  }
}
