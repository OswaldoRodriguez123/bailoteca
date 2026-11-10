import { ComponentFixture, TestBed } from '@angular/core/testing';

import { EmptyState } from './empty-state';

describe('EmptyState', () => {
  let fixture: ComponentFixture<EmptyState>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [EmptyState] }).compileComponents();
    fixture = TestBed.createComponent(EmptyState);
  });

  it('renderiza título y mensaje', async () => {
    fixture.componentRef.setInput('title', 'Sin resultados');
    fixture.componentRef.setInput('message', 'Prueba con otros filtros.');
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Sin resultados');
    expect(element.textContent).toContain('Prueba con otros filtros.');
  });

  it('emite action al hacer click en el botón', async () => {
    fixture.componentRef.setInput('title', 'Sin resultados');
    fixture.componentRef.setInput('actionLabel', 'Limpiar filtros');
    const action = vi.fn();
    fixture.componentInstance.action.subscribe(action);
    await fixture.whenStable();

    const button = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    button.click();

    expect(action).toHaveBeenCalledTimes(1);
  });
});
