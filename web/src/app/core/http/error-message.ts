import { HttpErrorResponse } from '@angular/common/http';

const GENERIC_MESSAGE = 'Ocurrió un error inesperado. Intenta de nuevo.';

export function errorMessage(error: unknown): string {
  if (!(error instanceof HttpErrorResponse)) {
    return GENERIC_MESSAGE;
  }

  switch (error.status) {
    case 0:
      return 'No pudimos conectar con el servidor. Revisa tu conexión.';
    case 429:
      return 'Demasiadas solicitudes. Espera un momento e intenta de nuevo.';
    case 503:
      return 'El directorio no está disponible ahora. Intenta más tarde.';
    default:
      return GENERIC_MESSAGE;
  }
}
