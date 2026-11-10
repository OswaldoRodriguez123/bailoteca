import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-loading-grid',
  template: `
    <div aria-busy="true" class="border-t border-line">
      @for (skeleton of skeletons(); track $index) {
        <div
          aria-hidden="true"
          class="grid animate-pulse grid-cols-[4.5rem_minmax(0,1fr)] items-start gap-4 border-b border-line py-5 motion-reduce:animate-none sm:grid-cols-[6rem_minmax(0,1fr)] sm:gap-6"
        >
          <div class="h-18 w-18 bg-paper-deep sm:h-24 sm:w-24"></div>
          <div class="min-w-0">
            <div class="h-5 w-2/3 bg-paper-deep"></div>
            <div class="mt-3 h-4 w-1/2 bg-paper-deep/70"></div>
            <div class="mt-4 h-3 w-full bg-paper-deep/70"></div>
            <div class="mt-2 h-3 w-5/6 bg-paper-deep/70"></div>
          </div>
        </div>
      }
    </div>
  `,
})
export class LoadingGrid {
  readonly count = input(6);
  protected readonly skeletons = computed(() => Array.from({ length: this.count() }));
}
