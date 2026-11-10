# Bailoteca web

SPA en Angular 22 con Tailwind CSS 4 que consume la API pública de solo lectura
de Bailoteca. No usa SSR ni SSG, no incluye NgRx y no tiene acceso a la base de
datos: todo pasa por los endpoints públicos.

## Stack

- Angular 22 con componentes standalone, signals y rutas lazy.
- Tailwind CSS 4 (configuración CSS-first, sin `tailwind.config.js`).
- Vitest 5 con `jsdom` para tests unitarios.
- TypeScript 6.

## Estructura

```text
web/
├── scripts/write-env.mjs             # genera environment.production.ts antes del build
├── src/
│   ├── environments/                 # development y production
│   └── app/
│       ├── core/                     # token API_BASE_URL, modelos, cliente HTTP, mensajes de error
│       ├── shared/components/        # EmptyState, ErrorState, LoadingGrid
│       └── features/academies/
│           ├── academy-list/         # listado con filtros y paginación
│           ├── academy-detail/       # detalle por slug
│           ├── academy-display.ts    # etiquetas, mapas y comunas
│           ├── academy-query.ts      # normalización de la URL
│           └── components/           # AcademyCard, FilterBar, Pagination, StyleBadges
└── vercel.json
```

## Requisitos

- Node.js 24
- npm 11
- La API corriendo (por defecto en `http://localhost:8000`)

## Desarrollo

```bash
cd web
npm install
npm start
```

La app queda en `http://localhost:4200` y lee `API_BASE_URL` desde
`src/environments/environment.ts` (`http://localhost:8000` por defecto).

## Tests

```bash
cd web
npm test -- --watch=false
```

Los tests usan `HttpTestingController` y fixtures; no necesitan la API real.

## Build de producción

```bash
cd web
API_BASE_URL=https://api.example.com npm run build
```

`API_BASE_URL` es obligatoria: el script `prebuild` (`scripts/write-env.mjs`)
falla si falta y escribe `src/environments/environment.production.ts` antes de
compilar. La salida queda en `dist/bailoteca-web/browser/`.

## Variables

| Variable       | Dónde                          | Uso                                   |
| -------------- | ------------------------------ | ------------------------------------- |
| `API_BASE_URL` | entorno del build / `.env`     | URL base de la API pública            |

No hay secretos en el navegador. `web/.env.example` solo documenta
`API_BASE_URL`.

## Endpoints consumidos

| Método | Endpoint             | Uso                                    |
| ------ | -------------------- | -------------------------------------- |
| `GET`  | `/academies`         | Listado con `comuna`, `style`, `q`, `page`, `page_size` |
| `GET`  | `/academies/{slug}`  | Detalle de una academia                |
| `GET`  | `/styles`            | Opciones del filtro de estilo          |
| `GET`  | `/comunas`           | Opciones del filtro de comuna          |

El cliente está en `src/app/core/services/academies-api.ts` y solo hace lecturas.

## Rutas

| Ruta               | Página                                     |
| ------------------ | ------------------------------------------ |
| `/`                | Listado con filtros, búsqueda y paginación |
| `/academias/:slug` | Detalle de la academia                     |

Ambas se cargan con `loadComponent` (lazy). Una ruta desconocida redirige a `/`.

## Decisiones

- **La URL es el estado del listado**: `comuna`, `style`, `q` y `page` viven en
  query params. La búsqueda se debouncea 300 ms y reescribe la URL con
  `replaceUrl`, así el botón atrás no guarda cada tecla.
- **Sin filtro por `status` en el cliente**: se muestran todas las academias que
  devuelve la API; las cerradas llevan el badge "Cerrada" y las no verificadas
  "Sin verificar".
- **Datos internos ocultos**: `confidence`, `evidence`, `source_url` y
  `source_urls` no se renderizan. Solo se muestran datos públicos.
- **Entradas inválidas se normalizan**: estilos con formato inválido, búsquedas
  de un carácter y páginas fuera de rango se corrigen en la URL.
- **Los enlaces de tarjeta conservan los filtros** para volver al mismo listado.

## Despliegue en Vercel

1. Crear un proyecto con **Root Directory** `web/`.
2. Build command: `npm run build`.
3. Output directory: `dist/bailoteca-web/browser`.
4. Configurar `API_BASE_URL` con la URL pública de la API en las variables de
   entorno del proyecto.
5. `vercel.json` reescribe todas las rutas a `index.html` para que el router de
   Angular funcione al recargar.

La API debe permitir el origen del sitio en `CORS_ORIGINS`
(`https://<proyecto>.vercel.app`). El CI de `.github/workflows/web.yml` corre
tests y build con un `API_BASE_URL` de relleno cuando cambia `web/**`.
