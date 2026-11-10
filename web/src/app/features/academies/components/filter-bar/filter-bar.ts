import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { StyleOption } from '../../../../core/models/academy.models';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-filter-bar',
  template: `
    <section aria-label="Filtros del directorio" class="border-y border-line py-4">
      <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_14rem_12rem] md:items-end">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-muted">Buscar</span>
          <input
            id="filter-q"
            name="q"
            type="search"
            autocomplete="off"
            [value]="q()"
            [disabled]="disabled()"
            (input)="onQ($event)"
            placeholder="Nombre o descripción…"
            class="w-full border-0 border-b border-line bg-transparent px-0 py-2 text-base text-ink placeholder:text-muted/70 focus-visible:border-accent-ink focus-visible:outline-none focus-visible:ring-0 disabled:text-muted"
          />
        </label>

        <label class="block">
          <span class="mb-1 block text-xs font-medium text-muted">Comuna</span>
          <select
            id="filter-comuna"
            name="comuna"
            [value]="comuna() ?? ''"
            [disabled]="disabled()"
            (change)="onComuna($event)"
            class="w-full border-0 border-b border-line bg-paper px-0 py-2 text-base text-ink focus-visible:border-accent-ink focus-visible:outline-none focus-visible:ring-0 disabled:text-muted"
          >
            <option value="">Todas las comunas</option>
            @for (option of comunas(); track option) {
              <option [value]="option">{{ option }}</option>
            }
          </select>
        </label>

        <label class="block">
          <span class="mb-1 block text-xs font-medium text-muted">Estilo</span>
          <select
            id="filter-estilo"
            name="style"
            [value]="style() ?? ''"
            [disabled]="disabled()"
            (change)="onStyle($event)"
            class="w-full border-0 border-b border-line bg-paper px-0 py-2 text-base text-ink focus-visible:border-accent-ink focus-visible:outline-none focus-visible:ring-0 disabled:text-muted"
          >
            <option value="">Todos los estilos</option>
            @for (option of styles(); track option.slug) {
              <option [value]="option.slug">{{ option.name }}</option>
            }
          </select>
        </label>
      </div>

      <div class="mt-3 flex justify-end">
        <button
          type="button"
          [disabled]="disabled()"
          (click)="clearFilters.emit()"
          class="text-sm font-medium text-accent-ink underline-offset-4 transition-colors hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink disabled:text-muted disabled:no-underline"
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
