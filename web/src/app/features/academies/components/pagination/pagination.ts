import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { lastPage } from '../../academy-query';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-pagination',
  template: `
    @if (total() > 0) {
      <nav class="mt-8 flex items-center justify-center gap-4" aria-label="Paginación">
        <button
          type="button"
          [disabled]="page() <= 1"
          (click)="go(page() - 1)"
          class="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:cursor-not-allowed disabled:text-stone-400"
        >
          Anterior
        </button>

        <p class="text-sm text-stone-600">Página {{ page() }} de {{ last() }}</p>

        <button
          type="button"
          [disabled]="page() >= last()"
          (click)="go(page() + 1)"
          class="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:cursor-not-allowed disabled:text-stone-400"
        >
          Siguiente
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
