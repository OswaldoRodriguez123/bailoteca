import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Pagination } from './pagination';

describe('Pagination', () => {
  let fixture: ComponentFixture<Pagination>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [Pagination] }).compileComponents();
    fixture = TestBed.createComponent(Pagination);
    fixture.componentRef.setInput('total', 45);
    fixture.componentRef.setInput('pageSize', 20);
  });

  function button(label: string): HTMLButtonElement {
    return Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find(candidate => candidate.textContent?.includes(label)) as HTMLButtonElement;
  }

  it('muestra la página actual y deshabilita Anterior en la primera', async () => {
    fixture.componentRef.setInput('page', 1);
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Página 1 de 3');
    expect(button('Anterior').disabled).toBe(true);
    expect(button('Siguiente').disabled).toBe(false);
  });

  it('deshabilita Siguiente en la última página', async () => {
    fixture.componentRef.setInput('page', 3);
    await fixture.whenStable();

    expect(button('Siguiente').disabled).toBe(true);
    expect(button('Anterior').disabled).toBe(false);
  });

  it('emite pageChange al avanzar', async () => {
    fixture.componentRef.setInput('page', 1);
    const changes = vi.fn();
    fixture.componentInstance.pageChange.subscribe(changes);
    await fixture.whenStable();

    button('Siguiente').click();

    expect(changes).toHaveBeenCalledWith(2);
  });

  it('no renderiza controles sin resultados', async () => {
    fixture.componentRef.setInput('page', 1);
    fixture.componentRef.setInput('total', 0);
    await fixture.whenStable();

    expect(fixture.nativeElement.querySelector('nav')).toBeNull();
  });
});
