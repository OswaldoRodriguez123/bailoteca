import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FilterBar } from './filter-bar';

describe('FilterBar', () => {
  let fixture: ComponentFixture<FilterBar>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [FilterBar] }).compileComponents();
    fixture = TestBed.createComponent(FilterBar);
    fixture.componentRef.setInput('comunas', ['Providencia', 'Ñuñoa']);
    fixture.componentRef.setInput('styles', [
      { slug: 'salsa', name: 'Salsa', sort: 1 },
      { slug: 'bachata', name: 'Bachata', sort: 2 },
    ]);
    await fixture.whenStable();
  });

  it('renderiza los labels de los filtros', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Buscar');
    expect(text).toContain('Comuna');
    expect(text).toContain('Estilo');
  });

  it('emite el texto crudo de búsqueda', () => {
    const changes = vi.fn();
    fixture.componentInstance.qChange.subscribe(changes);
    const input = fixture.nativeElement.querySelector('#filter-q') as HTMLInputElement;

    input.value = 'salsa';
    input.dispatchEvent(new Event('input'));

    expect(changes).toHaveBeenCalledWith('salsa');
  });

  it('emite la comuna y null para "Todas las comunas"', () => {
    const changes = vi.fn();
    fixture.componentInstance.comunaChange.subscribe(changes);
    const select = fixture.nativeElement.querySelector('#filter-comuna') as HTMLSelectElement;

    select.value = 'Providencia';
    select.dispatchEvent(new Event('change'));
    select.value = '';
    select.dispatchEvent(new Event('change'));

    expect(changes).toHaveBeenNthCalledWith(1, 'Providencia');
    expect(changes).toHaveBeenNthCalledWith(2, null);
  });

  it('emite el estilo y null para "Todos los estilos"', () => {
    const changes = vi.fn();
    fixture.componentInstance.styleChange.subscribe(changes);
    const select = fixture.nativeElement.querySelector('#filter-estilo') as HTMLSelectElement;

    select.value = 'salsa';
    select.dispatchEvent(new Event('change'));
    select.value = '';
    select.dispatchEvent(new Event('change'));

    expect(changes).toHaveBeenNthCalledWith(1, 'salsa');
    expect(changes).toHaveBeenNthCalledWith(2, null);
  });

  it('emite clearFilters', () => {
    const clear = vi.fn();
    fixture.componentInstance.clearFilters.subscribe(clear);
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find(candidate => candidate.textContent?.includes('Limpiar filtros')) as HTMLButtonElement;

    button.click();

    expect(clear).toHaveBeenCalledTimes(1);
  });

  it('deshabilita los controles cuando disabled es true', async () => {
    fixture.componentRef.setInput('disabled', true);
    await fixture.whenStable();

    const controls = fixture.nativeElement.querySelectorAll(
      'input, select, button',
    ) as NodeListOf<HTMLInputElement | HTMLSelectElement | HTMLButtonElement>;

    expect(controls.length).toBeGreaterThan(0);
    controls.forEach(control => expect(control.disabled).toBe(true));
  });
});
