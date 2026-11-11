import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Pagination } from './pagination';

describe('Pagination', () => {
  let fixture: ComponentFixture<Pagination>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Pagination],
      providers: [provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(Pagination);
    fixture.componentRef.setInput('total', 45);
    fixture.componentRef.setInput('pageSize', 20);
  });

  function link(label: string): HTMLAnchorElement | null {
    return Array.from(
      fixture.nativeElement.querySelectorAll('a') as NodeListOf<HTMLAnchorElement>,
    ).find(candidate => candidate.textContent?.includes(label)) ?? null;
  }

  it('enlaza la página siguiente para que los buscadores la sigan', async () => {
    fixture.componentRef.setInput('page', 1);
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Página 1 de 3');
    expect(link('Anterior')).toBeNull();
    expect(text).toContain('← Anterior');
    expect(link('Siguiente')?.getAttribute('href')).toBe('/?page=2');
  });

  it('conserva los filtros en los enlaces de paginación', async () => {
    fixture.componentRef.setInput('page', 2);
    fixture.componentRef.setInput('queryParams', { comuna: 'Maipú' });
    await fixture.whenStable();

    expect(link('Anterior')?.getAttribute('href')).toBe('/?comuna=Maip%C3%BA&page=1');
    expect(link('Siguiente')?.getAttribute('href')).toBe('/?comuna=Maip%C3%BA&page=3');
  });

  it('no enlaza fuera de rango en la última página', async () => {
    fixture.componentRef.setInput('page', 3);
    await fixture.whenStable();

    expect(link('Siguiente')).toBeNull();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Siguiente →');
    expect(link('Anterior')?.getAttribute('href')).toBe('/?page=2');
  });

  it('no renderiza controles sin resultados', async () => {
    fixture.componentRef.setInput('page', 1);
    fixture.componentRef.setInput('total', 0);
    await fixture.whenStable();

    expect(fixture.nativeElement.querySelector('nav')).toBeNull();
  });
});
