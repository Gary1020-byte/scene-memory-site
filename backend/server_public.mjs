#!/usr/bin/env node
/**
 * server_public.mjs —— 公開版 API + 網站
 *
 * 這是**唯一**的後端。它只讀 data/public.sqlite3，
 * 那個庫裡沒有絕對路徑、沒有 session id、沒有場景私有記憶全文。
 * 任何會洩漏本機狀態的端點都不存在——不是靠隱藏，是沒有。
 */
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DatabaseSync } from 'node:sqlite'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..')
const DB_PATH = path.join(ROOT, 'data', 'public.sqlite3')
const SITE = path.join(ROOT, 'site')
const DL = path.join(ROOT, 'public', 'downloads')
const PORT = Number(process.env.PORT || 8788)
const HOST = process.env.HOST || '127.0.0.1'

const db = new DatabaseSync(DB_PATH, { readOnly: true })
const q = (sql, ...a) => db.prepare(sql).all(...a)
const q1 = (sql, ...a) => db.prepare(sql).get(...a)

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.zip': 'application/zip',
  '.woff2': 'font/woff2',
}

function send (res, code, body, type = 'application/json; charset=utf-8') {
  const buf = Buffer.isBuffer(body) ? body : Buffer.from(typeof body === 'string' ? body : JSON.stringify(body))
  res.writeHead(code, { 'content-type': type, 'content-length': buf.length, 'cache-control': 'no-cache', 'access-control-allow-origin': '*' })
  res.end(buf)
}

function listScenes () {
  return q('SELECT * FROM scenes ORDER BY name').map(s => ({
    ...s,
    skills: q('SELECT name FROM scene_skills WHERE scene=?', s.id).map(r => r.name),
    panels: q('SELECT id,title,type FROM scene_panels WHERE scene=?', s.id),
    download_url: s.download ? `/downloads/${s.download}` : null,
  }))
}

const server = http.createServer((req, res) => {
  let url
  try { url = new URL(req.url, `http://${req.headers.host}`) } catch { return send(res, 400, { error: 'bad url' }) }
  const p = decodeURIComponent(url.pathname)

  if (p === '/api/meta') {
    return send(res, 200, {
      meta: Object.fromEntries(q('SELECT key,value FROM meta').map(r => [r.key, r.value])),
      counts: {
        scenes: q1('SELECT COUNT(*) c FROM scenes').c,
        layers: q1('SELECT COUNT(*) c FROM layers').c,
        reading: q1('SELECT COUNT(*) c FROM reading').c,
        published: q1('SELECT COUNT(*) c FROM reading WHERE status=?', 'published').c,
        downloads: q1('SELECT COUNT(*) c FROM scenes WHERE download IS NOT NULL').c,
      },
    })
  }
  if (p === '/api/scenes') return send(res, 200, { scenes: listScenes() })
  if (p === '/api/layers') return send(res, 200, { layers: q('SELECT * FROM layers ORDER BY id') })
  if (p === '/api/reading') {
    return send(res, 200, {
      reading: q('SELECT slug,seq,title,status,body FROM reading ORDER BY seq'),
    })
  }
  let m = p.match(/^\/api\/reading\/([^/]+)$/)
  if (m) {
    const r = q1('SELECT * FROM reading WHERE slug=?', m[1])
    return r ? send(res, 200, r) : send(res, 404, { error: 'not found' })
  }
  m = p.match(/^\/downloads\/([a-z0-9-]+)\.zip$/)
  if (m) {
    const f = path.join(DL, m[1] + '.zip')
    if (!fs.existsSync(f) || !f.startsWith(DL)) return send(res, 404, { error: 'no such download' })
    return send(res, 200, fs.readFileSync(f), MIME['.zip'])
  }

  // 靜態（site/）
  let rel = p === '/' ? '/index.html' : p
  rel = path.normalize(rel).replace(/^(\.\.[/\\])+/, '')
  const f = path.join(SITE, rel)
  if (f.startsWith(SITE) && fs.existsSync(f) && fs.statSync(f).isFile()) {
    return send(res, 200, fs.readFileSync(f), MIME[path.extname(f)] || 'application/octet-stream')
  }
  send(res, 404, { error: 'not found', path: p })
})

server.listen(PORT, HOST, () => {
  const m = q1('SELECT value FROM meta WHERE key=?', 'built_at')
  console.log(`公開版 → http://${HOST}:${PORT}`)
  console.log(`  db: ${DB_PATH}`)
  console.log(`  built_at: ${m ? m.value : '?'}`)
})
