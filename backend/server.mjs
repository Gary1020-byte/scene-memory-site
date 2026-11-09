#!/usr/bin/env node
/**
 * server.mjs —— 場景記憶架構 · 後端 API 與靜態前端
 *
 * 端點：
 *   GET  /api/meta                  後端 meta（built_at / 筆數）
 *   GET  /api/scenes                場景清單（不含檔案全文）
 *   GET  /api/scenes/:id            單一場景（含檔案與技能）
 *   GET  /api/scenes/:id/files/:f   單一檔案全文
 *   GET  /api/shared                共享層檔案
 *   GET  /api/concepts              概念頁清單（含 block）
 *   GET  /api/concepts/:slug        單一概念頁
 *   GET  /api/graph                 連結圖（edges）
 *   GET  /api/search?q=             跨場景／跨概念搜尋
 *   GET  /api/db.json               整包 JSON（靜態前端 fallback）
 *   GET  /*                         靜態檔（web/）
 *
 * 設計：唯讀。資料由 backend/build_db.py 產生，本服務只負責讀與出。
 */
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DatabaseSync } from 'node:sqlite'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..')
const DB_PATH = path.join(ROOT, 'data', 'db.sqlite3')
const WEB = path.join(ROOT, 'web')
const PORT = Number(process.env.PORT || 8787)
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
  '.woff2': 'font/woff2',
}

function send (res, code, body, type = 'application/json; charset=utf-8') {
  const buf = Buffer.isBuffer(body) ? body : Buffer.from(typeof body === 'string' ? body : JSON.stringify(body))
  res.writeHead(code, {
    'content-type': type,
    'content-length': buf.length,
    'cache-control': 'no-cache',
    'access-control-allow-origin': '*',
  })
  res.end(buf)
}

function listConcepts () {
  return q('SELECT slug,title,type,summary,tags,order_no FROM concepts ORDER BY order_no')
    .map(c => ({ ...c, blocks: q('SELECT idx,heading,level FROM concept_blocks WHERE slug=? ORDER BY idx', c.slug) }))
}

function listScenes () {
  return q('SELECT id,name,path,has_git,handover_size,skill_count,file_count,scanned_at FROM scenes ORDER BY name')
    .map(s => ({
      ...s,
      panels: q('SELECT id,title,type FROM scene_panels WHERE scene=?', s.id),
      skills: q('SELECT name,size,desc FROM scene_skills WHERE scene=?', s.id),
      files: q('SELECT name,kind,role,layer,desc,size,sha,count FROM scene_files WHERE scene=?', s.id),
    }))
}

function fullScene (id) {
  const s = q1('SELECT * FROM scenes WHERE id=?', id)
  if (!s) return null
  return {
    ...s,
    panels: q('SELECT id,title,type FROM scene_panels WHERE scene=?', id),
    skills: q('SELECT name,size,desc FROM scene_skills WHERE scene=?', id),
    files: q('SELECT * FROM scene_files WHERE scene=?', id),
  }
}

function graph () {
  const nodes = []
  for (const c of q('SELECT slug,title,type FROM concepts ORDER BY order_no')) nodes.push({ id: c.slug, label: c.title, type: c.type, group: 'concept' })
  for (const s of q('SELECT id,name FROM scenes ORDER BY name')) nodes.push({ id: s.id, label: s.name, type: 'scene', group: 'scene' })
  const edges = q('SELECT src,dst,kind FROM edges')
  return { nodes, edges }
}

function search (term) {
  if (!term) return { scenes: [], concepts: [], files: [] }
  const like = '%' + term + '%'
  return {
    scenes: q('SELECT id,name,path FROM scenes WHERE name LIKE ? OR path LIKE ?', like, like),
    concepts: q('SELECT slug,title,type,summary FROM concepts WHERE title LIKE ? OR summary LIKE ? OR body LIKE ?', like, like, like),
    files: q('SELECT scene,name,role,desc FROM scene_files WHERE name LIKE ? OR content LIKE ?', like, like).slice(0, 200),
  }
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
        scene_files: q1('SELECT COUNT(*) c FROM scene_files').c,
        skills: q1('SELECT COUNT(*) c FROM scene_skills').c,
        panels: q1('SELECT COUNT(*) c FROM scene_panels').c,
        shared: q1('SELECT COUNT(*) c FROM shared_files').c,
        concepts: q1('SELECT COUNT(*) c FROM concepts').c,
        blocks: q1('SELECT COUNT(*) c FROM concept_blocks').c,
        edges: q1('SELECT COUNT(*) c FROM edges').c,
      },
      db_path: DB_PATH,
      db_size: fs.statSync(DB_PATH).size,
    })
  }
  if (p === '/api/scenes') return send(res, 200, { scenes: listScenes() })
  if (p === '/api/shared') return send(res, 200, { shared: q('SELECT * FROM shared_files') })
  if (p === '/api/concepts') return send(res, 200, { concepts: listConcepts() })
  if (p === '/api/graph') return send(res, 200, graph())
  if (p === '/api/search') return send(res, 200, search(url.searchParams.get('q')))
  if (p === '/api/db.json') {
    const f = path.join(ROOT, 'data', 'db.json')
    if (!fs.existsSync(f)) return send(res, 404, { error: 'db.json 不存在，先跑 build_db.py --json' })
    return send(res, 200, fs.readFileSync(f))
  }

  let m = p.match(/^\/api\/scenes\/([^/]+)$/)
  if (m) {
    const s = fullScene(m[1])
    return s ? send(res, 200, s) : send(res, 404, { error: 'no such scene' })
  }
  m = p.match(/^\/api\/scenes\/([^/]+)\/files\/(.+)$/)
  if (m) {
    const f = q1('SELECT * FROM scene_files WHERE scene=? AND name=?', m[1], m[2])
    return f ? send(res, 200, f) : send(res, 404, { error: 'no such file' })
  }
  m = p.match(/^\/api\/concepts\/([^/]+)$/)
  if (m) {
    const c = q1('SELECT * FROM concepts WHERE slug=?', m[1])
    if (!c) return send(res, 404, { error: 'no such concept' })
    return send(res, 200, { ...c, blocks: q('SELECT * FROM concept_blocks WHERE slug=? ORDER BY idx', m[1]) })
  }

  // 靜態
  if (p === '/') {
    const f = path.join(WEB, 'index.html')
    if (fs.existsSync(f)) return send(res, 200, fs.readFileSync(f), MIME['.html'])
    return send(res, 404, 'web/index.html 不存在')
  }
  const safe = path.normalize(p).replace(/^(\.\.[\/])+/, '')
  const f = path.join(WEB, safe)
  if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) {
    return send(res, 200, fs.readFileSync(f), MIME[path.extname(f)] || 'application/octet-stream')
  }
  send(res, 404, { error: 'not found', path: p })
})

server.listen(PORT, HOST, () => {
  const m = q1('SELECT value FROM meta WHERE key=?', 'built_at')
  console.log(`場景記憶架構後端 → http://${HOST}:${PORT}`)
  console.log(`  db: ${DB_PATH}`)
  console.log(`  built_at: ${m ? m.value : '?'}`)
})
