import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-empty-state',
  template: `
    <div class="border-y border-line py-16 text-center">
      <h2 class="font-display text-2xl font-bold tracking-tight text-ink">{{ title() }}</h2>
      @if (message()) {
        <p class="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-soft">{{ message() }}</p>
      }
      @if (actionLabel()) {
        <button
          type="button"
          (click)="action.emit()"
          class="mt-6 text-sm font-medium text-accent-ink underline-offset-4 transition-colors hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
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
