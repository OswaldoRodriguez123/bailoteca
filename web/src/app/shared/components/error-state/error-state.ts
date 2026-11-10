import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-error-state',
  template: `
    <div role="alert" class="border-y border-line py-12 text-center">
      <h2 class="font-display text-2xl font-bold tracking-tight text-ink">Algo salió mal</h2>
      <p class="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-soft">{{ message() }}</p>
      <button
        type="button"
        (click)="retry.emit()"
        class="mt-6 text-sm font-medium text-accent-ink underline-offset-4 transition-colors hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink"
      >
        Reintentar
      </button>
    </div>
  `,
})
export class ErrorState {
  readonly message = input.required<string>();
  readonly retry = output<void>();
}
