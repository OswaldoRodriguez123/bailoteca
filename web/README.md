# Bailoteca Web

Frontend del directorio de academias de Bailoteca. Todavía no tiene
implementación: esta carpeta define la estructura y las decisiones para cuando
se construya.

## Stack previsto

- **Angular** (standalone components).
- Consumo de la API de Bailoteca vía `API_BASE_URL`.
- Sin acceso directo a Postgres ni a Supabase desde el navegador.

## Estructura prevista

```text
web/
├── src/
│   ├── app/
│   │   ├── pages/        # listado y detalle de academias
│   │   ├── components/   # tarjetas, filtros por comuna y estilo
│   │   └── services/     # cliente HTTP de la API
│   ├── environments/
│   └── main.ts
├── angular.json
└── package.json
```

## Variables de entorno

Copiar `.env.example` a `.env`:

```bash
cp .env.example .env
```

- `API_BASE_URL`: URL base de la API. En local, `http://localhost:8000`.

La web **no** recibe credenciales de base de datos. Todo pasa por la API.

## Cómo correrla (cuando exista el código)

```bash
cd web
npm install
npm start
```

## Despliegue

- Vercel con **Root Directory** en `web/`.
- `API_BASE_URL` configurada en Vercel, apuntando a la API desplegada.
- Sin workflow de CI hasta que exista código; cuando exista, se filtra por
  `paths: web/**`.
