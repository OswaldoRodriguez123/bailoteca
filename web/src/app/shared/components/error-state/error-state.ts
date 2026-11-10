import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-error-state',
  template: `
    <div
      role="alert"
      class="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center text-rose-900"
    >
      <h2 class="text-lg font-semibold">Algo salió mal</h2>
      <p class="mx-auto mt-2 max-w-md text-sm">{{ message() }}</p>
      <button
        type="button"
        (click)="retry.emit()"
        class="mt-6 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600"
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
