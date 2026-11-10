import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-empty-state',
  template: `
    <div class="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center">
      <h2 class="text-lg font-semibold text-stone-900">{{ title() }}</h2>
      @if (message()) {
        <p class="mx-auto mt-2 max-w-md text-sm text-stone-600">{{ message() }}</p>
      }
      @if (actionLabel()) {
        <button
          type="button"
          (click)="action.emit()"
          class="mt-6 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600"
        >
          {{ actionLabel() }}
        </button>
      }
    </div>
  `,
})
export class EmptyState {
  readonly title = input.required<string>();
  readonly message = input<string>('');
  readonly actionLabel = input<string | null>(null);
  readonly action = output<void>();
}
