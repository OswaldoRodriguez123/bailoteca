# Diseño: frontend web Angular + Tailwind

**Fecha:** 2026-11-09
**Estado:** propuesto (pendiente de aprobación)

## Intención

Construir el frontend público de Bailoteca: un directorio de academias de baile
en Santiago de Chile, empezando por salsa. La web consume la API FastAPI de
solo lectura y permite a una persona **encontrar una academia por comuna,
estilo o texto, y abrir su ficha**.

Es la pieza que faltaba del monorepo: `parser/` propone y publica, `shared/`
define el contrato, `api/` lo expone y `web/` lo hace usable.

## Por qué

Hoy el directorio solo existe como datos y JSON. El valor del proyecto aparece
cuando alguien que busca clases de salsa puede:

1. Ver qué academias existen cerca de su comuna.
2. Filtrar por estilo (salsa, bachata, etc.).
3. Abrir una ficha con dirección, enlaces e Instagram.
4. Compartir el enlace de una búsqueda o de una academia.

## Objetivos

- Listado paginado de academias publicadas (`GET /academies`).
- Filtros por comuna (`GET /comunas`), estilo (`GET /styles`) y búsqueda de
  texto, sincronizados con la URL para que back/forward y los enlaces
  compartidos funcionen.
- Detalle por slug (`GET /academies/{slug}`).
- Estados explícitos de carga, vacío y error (incluye 429 y 503).
- Responsive, accesible con teclado y lector de pantalla, en español de Chile.
- Deploy en Vercel con Root Directory `web/`.

## No objetivos

- Autenticación, escrituras, panel de administración.
- Mapa interactivo. Los datos traen `lat`/`lng`, pero en el MVP se muestra un
  enlace a Google Maps, no un mapa embebido.
- SSR / SSG (se evaluó y se descartó para esta etapa).
- i18n; la UI queda en español.
- Tests E2E, sitemap y SEO avanzado.
- Mostrar `source_urls` (son evidencia interna del pipeline).

## Anti-objetivos

- Duplicar el contrato de la API con tipos escritos a mano que se desincronicen
  sin tests: los modelos se mantienen pegados a los DTOs y se cubren con tests.
- Introducir NgRx para un estado read-only que cabe en signals.
- Acceder a Supabase/Postgres desde el navegador.
- Hardcodear la URL de la API en componentes.
- Pedir a la API en cada tecla sin debounce ni cancelación.

## Restricciones

- **Angular 22**, componentes standalone, `ChangeDetectionStrategy.OnPush` y
  signals para estado local.
- **Tailwind CSS** para estilos.
- `API_BASE_URL` como variable de entorno de build; nunca en el código de un
  componente.
- CORS local: la API permite `http://localhost:4200` por defecto.
- Rate limit de la API: `60/minute` por IP. La búsqueda debe hacer debounce y
  cancelar la petición anterior (`switchMap`).
- Node 24 (ya instalado) y Angular CLI 22 vía `npx`.
- Sin credenciales en el frontend.

## Enfoques considerados

1. **SPA standalone + Tailwind (elegido).** La más simple que cubre el
   directorio: rutas lazy, `HttpClient` y signals. Menos partes móviles y
   deploy directo en Vercel.
2. **SPA + SSR (Angular Universal).** Mejor SEO y first paint, pero agrega
   complejidad de build, ejecución en servidor y manejo de HTTP durante el
   render. Para un directorio pequeño no se justifica todavía.
3. **SPA + NgRx.** Store global para academias y filtros. Overkill: no hay
   escrituras ni estado compartido entre páginas; los signals del componente y
   los query params alcanzan.

Se eligió **1** porque el usuario pidió Tailwind y un MVP sin SSR.

## Arquitectura

```text
web/
├── angular.json
├── package.json
├── vercel.json
├── scripts/
│   └── write-env.mjs            # escribe environment.production.ts desde API_BASE_URL
├── src/
│   ├── environments/
│   │   ├── environment.ts       # local: http://localhost:8000
│   │   └── environment.production.ts
│   ├── styles.css               # @import "tailwindcss"
│   ├── index.html
│   ├── main.ts
│   └── app/
│       ├── app.component.ts     # shell: header + router-outlet + footer
│       ├── app.config.ts        # provideHttpClient, provideRouter, ...
│       ├── app.routes.ts        # lazy: '' y 'academias/:slug'
│       ├── core/
│       │   ├── models/
│       │   │   └── academy.models.ts
│       │   └── services/
│       │       └── academies-api.service.ts
│       ├── features/academies/
│       │   ├── academy-list/
│       │   │   └── academy-list.page.ts
│       │   ├── academy-detail/
│       │   │   └── academy-detail.page.ts
│       │   └── components/
│       │       ├── academy-card/
│       │       ├── filter-bar/
│       │       ├── pagination/
│       │       └── style-badges/
│       └── shared/
│           └── components/
│               ├── empty-state/
│               ├── error-state/
│               └── loading-grid/
└── src/app/**/*.spec.ts
```

### Rutas

| Ruta                | Página            | Notas                                   |
| ------------------- | ----------------- | --------------------------------------- |
| `''`                | `AcademyListPage` | Listado + filtros; query params mandan |
| `academias/:slug`   | `AcademyDetailPage` | Ficha; 404 → estado "no encontrada"   |
| `**`                | redirect a `''`   |                                         |

### Contrato con la API

Modelos TypeScript espejo de los DTOs de `shared/`:

```ts
interface AcademyLocation {
  label: string | null;
  address: string | null;
  comuna: string | null;
  lat: number | null;
  lng: number | null;
  source_url: string | null;
}

interface AcademyLink { kind: string; url: string; }

interface AcademyStyle {
  slug: string;
  name: string | null;
  confidence: number | null;
  evidence: string | null;
}

interface Academy {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  status: string;
  source_urls: string[];
  created_at: string | null;
  updated_at: string | null;
  verified_at: string | null;
  locations: AcademyLocation[];
  links: AcademyLink[];
  styles: AcademyStyle[];
}

interface AcademyPage {
  items: Academy[];
  page: number;
  page_size: number;
  total: number;
}

interface StyleOption { slug: string; name: string; sort: number; }
```

`AcademiesApiService` expone métodos tipados:

- `listAcademies(params: AcademyQuery): Observable<AcademyPage>`
- `getAcademy(slug: string): Observable<Academy>`
- `listStyles(): Observable<StyleOption[]>`
- `listComunas(): Observable<string[]>`

`AcademyQuery`: `{ comuna?, style?, q?, page?, pageSize? }`. El servicio arma
`HttpParams` omitiendo valores vacíos y usa `page_size` en la API.

### Estado y URL

La URL es la fuente de verdad del listado:

- `?comuna=Providencia&style=salsa&q=...&page=2`
- Al cambiar un filtro se navega con `queryParamsHandling: 'merge'` y se
  resetea `page` a 1.
- El input de búsqueda usa `debounceTime(300)` + `distinctUntilChanged` +
  `switchMap`; solo consulta con 2+ caracteres (regla de la API).
- **Decisión:** tras el debounce, la URL se actualiza en vivo con
  `replaceUrl: true` (sin llenar el historial de navegación). El fetch lo
  dispara siempre `queryParamMap`; back/forward aplican el cambio de inmediato,
  sin debounce. Así hay una sola fuente de verdad y no dos flujos de datos.

Los estilos se cargan una vez en el listado con `listStyles()`; las comunas con
`listComunas()`. Si fallan, los filtros se deshabilitan pero el listado sigue
funcionando.

### Normalización de la URL

La URL es editable y compartible, así que antes de consultar:

- `q` con menos de 2 caracteres se descarta.
- `style` que no cumple `^[a-z0-9-]+$` se descarta.
- `page` no numérico o menor a 1 se trata como 1.
- `comuna` vacía se descarta.
- Si la respuesta trae `items: []` y `page` supera la última página real, se
  redirige una vez a la última página (con `replaceUrl`). Si no hay ninguna
  página válida, se muestra el estado vacío.


### Errores y estados

`HttpErrorResponse` se traduce a un mensaje accionable:

| Situación                  | UI                                                        |
| -------------------------- | --------------------------------------------------------- |
| `0` / red                  | "No pudimos conectar con el servidor. Revisa tu conexión." |
| `429`                      | "Demasiadas solicitudes. Espera un momento e intenta de nuevo." |
| `503`                      | "El directorio no está disponible ahora. Intenta más tarde." |
| `404` (detalle)            | "No encontramos esa academia." + volver al listado        |
| otro                       | "Ocurrió un error inesperado."                            |

Cada página muestra: skeleton de carga, contenido, vacío con acción para
limpiar filtros, y error con botón "Reintentar".

### Datos visibles y estado de la academia

- La API devuelve **todas** las filas de `academies` (no filtra por `status`).
  Esas filas son las ya aprobadas por el pipeline; `status` describe el estado
  operativo de la academia, no si está publicada.
- **Decisión:** no se filtra por `status` en el cliente (rompería `total` y la
  paginación). Se muestran todas y se agrega un badge discreto:
  - `closed` → "Cerrada" (ámbar), visible en tarjeta y detalle.
  - `unknown` → "Sin verificar" (gris), solo en el detalle.
  - `active` → sin badge.
- **Decisión:** el detalle **no** muestra `confidence`, `evidence` ni
  `source_url` de estilos/ubicaciones, ni `source_urls`: son datos internos del
  pipeline. Solo se muestran `name`, `description`, `locations` (label,
  address, comuna, lat/lng para un enlace de mapa), `links` y `styles`.
- **Decisión:** los enlaces se muestran con etiqueta por `kind` (`web`,
  `instagram`, `facebook`, `tiktok`, `whatsapp`, `phone`, `email`); un `kind`
  desconocido usa "Enlace". `phone`/`email` se manejan como `tel:`/`mailto:`.
  Son datos de contacto públicos del directorio, no credenciales.

### Componentes

- **`AcademyCard`**: nombre, comunas únicas, badges de estilos, descripción
  recortada y enlace al detalle. Toda la tarjeta es clickeable con un solo
  enlace accesible (no anidar interactivos). **Decisión:** el enlace del card
  incluye los query params actuales del listado, y el detalle guarda esos
  params para que "Volver al listado" y el 404 conserven filtros y página. Si
  se entra directo por enlace compartido, vuelve a `/` sin filtros.
- **`FilterBar`**: input de búsqueda con label, select de comuna, chips o
  select de estilo, botón "Limpiar filtros".
- **`Pagination`**: anterior/siguiente + "Página X de Y"; deshabilita según
  límites y conserva los filtros en la URL.
- **`StyleBadges`**: badges de estilos; tolera `name: null` usando el slug
  capitalizado.
- **`EmptyState` / `ErrorState` / `LoadingGrid`**: presentacionales, con
  `input()`/`output()` de signals.

### Accesibilidad

- Un `<h1>` por página y jerarquía de headings correcta.
- Labels reales en inputs y selects; `aria-live="polite"` en el contador de
  resultados.
- Foco visible con `focus-visible` de Tailwind.
- Enlaces con texto descriptivo; no depender solo del color.
- Contraste AA; `prefers-reduced-motion` respetado en skeletons.

### Rendimiento

- Rutas lazy para el detalle.
- `OnPush` en todos los componentes.
- Imágenes: si no hay imágenes en la API, no se inventan; las tarjetas usan
  tipografía y badges.
- Debounce y cancelación de búsquedas.

## Configuración y despliegue

- **Tailwind CSS v4** con enfoque CSS-first: `@import "tailwindcss"` en
  `styles.css` y tokens con `@theme`; sin `tailwind.config.js` salvo que haga
  falta. Se instala con `@tailwindcss/postcss`.
- `src/environments/environment.ts`: `apiBaseUrl: 'http://localhost:8000'`.
- `src/environments/environment.production.ts`: generado por
  `scripts/write-env.mjs` desde `API_BASE_URL` durante `npm run build`. Si la
  variable falta, el build falla con un mensaje claro.
- `npm start`: `ng serve` en `http://localhost:4200`.
- Vercel, Root Directory `web/`:
  - Build: `npm run build`
  - Output: `dist/bailoteca-web/browser`
  - `vercel.json` con rewrite de SPA a `index.html`.
- En la API, `CORS_ORIGINS` debe incluir el dominio de la web en producción.

## CI

**Decisión:** se agrega `.github/workflows/web.yml` filtrado por `web/**`:

```bash
cd web
npm ci
npm test -- --watch=false
npm run build
```

## Tests

- **Servicio**: `HttpTestingController` verifica rutas, `HttpParams` (omite
  vacíos, usa `page_size`) y propagación de errores.
- **Listado**: se suscribe a query params, hace debounce (fakeAsync/timers),
  normaliza params inválidos, muestra vacío y error.
- **Detalle**: carga por slug, muestra 404 y conserva filtros al volver.
- **Componentes presentacionales**: render de badges, badge "Cerrada",
  etiquetas de enlaces y paginación.
- Se usa el runner que traiga Angular CLI 22 por defecto; se documenta el
  comando real en el plan.

## Lo que queda a criterio del builder

- Paleta y tokens visuales concretos (se parte de Tailwind por defecto),
  spacing y tipografía.
- Copy exacto de hero, header y footer.
- Formato de la descripción recortada y layout exacto de la tarjeta.
- Cómo se arma el enlace "Cómo llegar" a Google Maps con `lat`/`lng` o, si
  faltan, con `address` + `comuna`.
- Cobertura de tests adicional y si se agregan más componentes shared.
