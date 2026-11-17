// Servidor estático para la salida prerenderizada (outputMode: "static").
// Sin dependencias: sirve dist/bailoteca-web/browser en el puerto 4100 para
// las pruebas e2e (Playwright) y para revisar el build localmente.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';

const root = resolve(new URL('../dist/bailoteca-web/browser', import.meta.url).pathname);
const port = Number(process.env.PORT ?? 4100);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.avif': 'image/avif',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.webmanifest': 'application/manifest+json',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

async function send(res, status, file) {
  try {
    const body = await readFile(file);
    res.writeHead(status, {
      'Content-Type': MIME[extname(file)] ?? 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('not found');
  }
}

const server = createServer((req, res) => {
  const url = new URL(req.url ?? '/', `http://localhost:${port}`);
  let pathname = decodeURIComponent(url.pathname);
  // Sin path traversal: el resuelto debe quedar dentro de root.
  let file = resolve(join(root, normalize(pathname)));
  if (!file.startsWith(root)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('forbidden');
    return;
  }
  if (pathname.endsWith('/')) {
    file = join(file, 'index.html');
  } else if (!extname(file)) {
    file = join(file, 'index.html');
  }
  void send(res, 200, file);
});

server.listen(port, () => {
  console.log(`sirviendo ${root} en http://localhost:${port}`);
});
