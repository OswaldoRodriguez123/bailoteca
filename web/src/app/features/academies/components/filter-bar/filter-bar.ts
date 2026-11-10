import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { StyleOption } from '../../../../core/models/academy.models';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-filter-bar',
  template: `
    <section
      aria-label="Filtros del directorio"
      class="rounded-2xl border border-stone-200 bg-white p-4 sm:p-6"
    >
      <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_auto]">
        <label class="block">
          <span class="mb-1 block text-sm font-medium text-stone-700">Buscar</span>
          <input
            id="filter-q"
            type="search"
            [value]="q()"
            [disabled]="disabled()"
            (input)="onQ($event)"
            placeholder="Nombre o descripción"
            class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus-visible:border-rose-500 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-rose-500 disabled:bg-stone-100"
          />
        </label>

        <label class="block">
          <span class="mb-1 block text-sm font-medium text-stone-700">Comuna</span>
          <select
            id="filter-comuna"
            [value]="comuna() ?? ''"
            [disabled]="disabled()"
            (change)="onComuna($event)"
            class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 focus-visible:border-rose-500 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-rose-500 disabled:bg-stone-100 md:w-56"
          >
            <option value="">Todas las comunas</option>
            @for (option of comunas(); track option) {
              <option [value]="option">{{ option }}</option>
            }
          </select>
        </label>

        <label class="block">
          <span class="mb-1 block text-sm font-medium text-stone-700">Estilo</span>
          <select
            id="filter-estilo"
            [value]="style() ?? ''"
            [disabled]="disabled()"
            (change)="onStyle($event)"
            class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 focus-visible:border-rose-500 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-rose-500 disabled:bg-stone-100 md:w-48"
          >
            <option value="">Todos los estilos</option>
            @for (option of styles(); track option.slug) {
              <option [value]="option.slug">{{ option.name }}</option>
            }
          </select>
        </label>
      </div>

      <div class="mt-4 flex justify-end">
        <button
          type="button"
          [disabled]="disabled()"
          (click)="clearFilters.emit()"
          class="rounded-lg px-3 py-2 text-sm font-medium text-rose-700 transition-colors hover:bg-rose-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:text-stone-400"
        >
          Limpiar filtros
        </button>
      </div>
    </section>
  `,
})
export class FilterBar {
  readonly comunas = input<string[]>([]);
  readonly styles = input<StyleOption[]>([]);
  readonly comuna = input<string | null>(null);
  readonly style = input<string | null>(null);
  readonly q = input<string>('');
  readonly disabled = input(false);

  readonly comunaChange = output<string | null>();
  readonly styleChange = output<string | null>();
  readonly qChange = output<string>();
  readonly clearFilters = output<void>();

  protected onQ(event: Event): void {
    this.qChange.emit((event.target as HTMLInputElement).value);
  }

  protected onComuna(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.comunaChange.emit(value || null);
  }

  protected onStyle(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.styleChange.emit(value || null);
  }
}
