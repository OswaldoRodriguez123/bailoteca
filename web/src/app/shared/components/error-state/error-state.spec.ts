import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ErrorState } from './error-state';

describe('ErrorState', () => {
  let fixture: ComponentFixture<ErrorState>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ErrorState] }).compileComponents();
    fixture = TestBed.createComponent(ErrorState);
  });

  it('renderiza el mensaje y emite retry', async () => {
    fixture.componentRef.setInput('message', 'El directorio no está disponible ahora.');
    const retry = vi.fn();
    fixture.componentInstance.retry.subscribe(retry);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('El directorio no está disponible ahora.');

    const button = element.querySelector('button') as HTMLButtonElement;
    button.click();

    expect(retry).toHaveBeenCalledTimes(1);
  });
});
