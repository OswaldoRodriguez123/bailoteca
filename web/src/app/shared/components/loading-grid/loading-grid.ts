import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-loading-grid',
  template: `
    <div aria-busy="true" class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      @for (skeleton of skeletons(); track $index) {
        <div
          aria-hidden="true"
          class="animate-pulse rounded-2xl border border-stone-200 bg-white p-6 motion-reduce:animate-none"
        >
          <div class="h-5 w-2/3 rounded bg-stone-200"></div>
          <div class="mt-3 h-4 w-1/2 rounded bg-stone-100"></div>
          <div class="mt-6 h-3 w-full rounded bg-stone-100"></div>
          <div class="mt-2 h-3 w-5/6 rounded bg-stone-100"></div>
        </div>
      }
    </div>
  `,
})
export class LoadingGrid {
  readonly count = input(6);
  protected readonly skeletons = computed(() => Array.from({ length: this.count() }));
}
