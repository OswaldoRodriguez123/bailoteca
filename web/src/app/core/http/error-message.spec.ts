import { HttpErrorResponse } from '@angular/common/http';

import { errorMessage } from './error-message';

describe('errorMessage', () => {
  it('explica errores de red', () => {
    expect(errorMessage(new HttpErrorResponse({ status: 0 }))).toContain('conectar');
  });

  it('explica el rate limit', () => {
    expect(errorMessage(new HttpErrorResponse({ status: 429 }))).toContain(
      'Demasiadas solicitudes',
    );
  });

  it('explica la base de datos no disponible', () => {
    expect(errorMessage(new HttpErrorResponse({ status: 503 }))).toContain('no está disponible');
  });

  it('usa un mensaje genérico para otros errores', () => {
    expect(errorMessage(new HttpErrorResponse({ status: 500 }))).toContain('inesperado');
  });

  it('usa un mensaje genérico para valores que no son HttpErrorResponse', () => {
    expect(errorMessage(new Error('boom'))).toContain('inesperado');
  });
});
