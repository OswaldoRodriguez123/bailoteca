// Servidor estático para la salida prerenderizada (outputMode: "static").
// Sin dependencias: sirve dist/bailoteca-web/browser en el puerto 4100 para
// las pruebas e2e (Playwright) y para revisar el build localmente.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve, sep } from 'node:path';

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

async function sendFile(res, status, file) {
  const body = await readFile(file);
  res.writeHead(status, {
    'Content-Type': MIME[extname(file)] ?? 'application/octet-stream',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

async function sendNotFound(res) {
  try {
    await sendFile(res, 404, join(root, '404.html'));
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('not found');
  }
}

async function isFile(file) {
  try {
    return (await stat(file)).isFile();
  } catch {
    return false;
  }
}

const server = createServer((req, res) => {
  const handle = async () => {
    let pathname;
    try {
      const url = new URL(req.url ?? '/', `http://localhost:${port}`);
      pathname = decodeURIComponent(url.pathname);
    } catch {
      res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('bad request');
      return;
    }
    let file = resolve(join(root, normalize(pathname)));
    if (file !== root && !file.startsWith(root + sep)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('forbidden');
      return;
    }
    if (pathname.endsWith('/')) {
      file = join(file, 'index.html');
    } else if (!extname(file)) {
      file = join(file, 'index.html');
    }
    if (await isFile(file)) {
      await sendFile(res, 200, file);
    } else {
      await sendNotFound(res);
    }
  };
  handle().catch(() => {
    if (!res.headersSent) {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('internal error');
    } else {
      res.end();
    }
  });
});

server.listen(port, () => {
  console.log(`sirviendo ${root} en http://localhost:${port}`);
});
