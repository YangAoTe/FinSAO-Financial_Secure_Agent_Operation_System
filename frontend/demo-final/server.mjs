// FinSAO 前端本地服务：托管 index.html，并把其余请求同源转发到 Banking Core（解决无 CORS 问题）。
// 用法：node server.mjs        （需要 Node 18+，无需 npm install）
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const BACKEND = new URL(process.env.BACKEND_URL || 'http://127.0.0.1:8000');
const PORT = Number(process.env.PORT || 5173);
const here = dirname(fileURLToPath(import.meta.url));

http.createServer(async (req, res) => {
  if (req.method === 'GET' && (req.url === '/' || req.url === '/index.html')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(await readFile(join(here, 'index.html')));
  }
  const headers = { ...req.headers, host: BACKEND.host };
  delete headers.origin; delete headers.referer;
  const up = http.request({ hostname: BACKEND.hostname, port: BACKEND.port, path: req.url, method: req.method, headers }, (r) => {
    res.writeHead(r.statusCode || 502, r.headers); r.pipe(res);
  });
  up.on('error', () => { res.writeHead(502, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ code: 'UPSTREAM_UNAVAILABLE', message: 'banking service unavailable' })); });
  req.pipe(up);
}).listen(PORT, () => console.log(`FinSAO 前端: http://localhost:${PORT}  →  后端 ${BACKEND.origin}`));
