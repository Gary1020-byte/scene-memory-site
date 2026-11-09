/* Gary 的場景記憶架構 · 共用前端 */
// 站台根：從 assets 的 href 反推（相容掛在子路徑下，例如 /scene-memory-public/）
const BASE = (() => {
  const link = document.querySelector('link[href*="/assets/"]');
  if (link) {
    const u = new URL(link.href, location.href);
    const i = u.pathname.indexOf('/assets/');
    if (i >= 0) return u.pathname.slice(0, i);
  }
  let p = location.pathname; if (!p.endsWith('/')) p = p.replace(/[^/]*$/, '');
  return p.replace(/\/$/, '');
})();
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const kb = n => n < 1024 ? n + ' B' : n < 1048576 ? (n/1024).toFixed(1) + ' KB' : (n/1048576).toFixed(1) + ' MB';
async function api(p){ const r = await fetch(BASE + '/data' + p.replace(/^\/api/, '') + '.json'); if(!r.ok) throw new Error(p+' → '+r.status); return r.json(); }

function md(src){
  const lines = String(src ?? '').split('\n');
  let out = '', i = 0, inCode = false, codeBuf = [];
  const inline = t => esc(t)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  while (i < lines.length){
    const L = lines[i];
    if (/^```/.test(L)){
      if (!inCode){ inCode = true; codeBuf = []; } else { out += '<pre><code>' + esc(codeBuf.join('\n')) + '</code></pre>'; inCode = false; }
      i++; continue;
    }
    if (inCode){ codeBuf.push(L); i++; continue; }
    if (/^\s*\|/.test(L) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i+1]||'')){
      const cells = r => r.trim().replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
      const head = cells(L); i += 2; const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(cells(lines[i])); i++; }
      out += '<table><thead><tr>' + head.map(h=>'<th>'+inline(h)+'</th>').join('')+'</tr></thead><tbody>'
           + rows.map(r=>'<tr>'+r.map(c=>'<td>'+inline(c)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
      continue;
    }
    let m;
    if ((m = L.match(/^(#{1,6})\s+(.*)$/))){ const lv = Math.min(Math.max(m[1].length,2),4);
      out += `<h${lv}>${inline(m[2])}</h${lv}>`; i++; continue; }
    if (/^#+\s*$/.test(L)){ i++; continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(L)){ out += '<hr>'; i++; continue; }
    if ((m = L.match(/^\s*>\s?(.*)$/))){
      const buf = []; let g=0;
      while (i < lines.length && /^\s*>\s?/.test(lines[i]) && g++ < 500) { buf.push(lines[i].replace(/^\s*>\s?/,'')); i++; }
      out += '<blockquote>' + md(buf.join('\n')) + '</blockquote>'; continue;
    }
    if ((m = L.match(/^\s*[-*]\s+(.*)$/))){
      const items = []; let g=0;
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i]) && g++ < 500) { items.push(lines[i].replace(/^\s*[-*]\s+/,'')); i++; }
      out += '<ul>' + items.map(x=>'<li>'+inline(x)+'</li>').join('')+'</ul>'; continue;
    }
    if ((m = L.match(/^\s*\d+\.\s+(.*)$/))){
      const items = []; let g=0;
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i]) && g++ < 500) { items.push(lines[i].replace(/^\s*\d+\.\s+/,'')); i++; }
      out += '<ol>' + items.map(x=>'<li>'+inline(x)+'</li>').join('')+'</ol>'; continue;
    }
    if (!L.trim()){ i++; continue; }
    const buf = []; let guard=0;
    while (i < lines.length && lines[i].trim() && !/^\s*([-*]\s|\d+\.\s|>|#)/.test(lines[i])
           && !/^\s*\|/.test(lines[i]) && !/^\s*```/.test(lines[i]) && guard++ < 500) { buf.push(lines[i]); i++; }
    if (!buf.length){ i++; continue; }
    out += '<p>' + inline(buf.join(' ')) + '</p>';
  }
  if (inCode && codeBuf.length) out += '<pre><code>' + esc(codeBuf.join('\n')) + '</code></pre>';
  return out;
}

const NAV = [
  { path: '/',            key: 'home',    label: '首頁' },
  { path: '/architecture', key: 'arch',    label: '架構' },
  { path: '/scenes',       key: 'scenes',  label: '場景' },
  { path: '/reading',      key: 'reading', label: '導讀' },
  { path: '/start',        key: 'start',   label: '開始使用' },
].map(n => ({ ...n, href: BASE + n.path }));

const PAGE = document.body.dataset.page || 'home';

// 站內連結前綴 BASE（相容掛在子路徑下）
function fixLinks(){
  document.querySelectorAll('a[href^="/"]').forEach(a => {
    const h = a.getAttribute('href');
    if (h.startsWith(BASE + '/') || h === BASE) return;
    a.setAttribute('href', BASE + h);
  });
}
const S = { scenes: [], layers: [], reading: [] };

function renderNav(){
  const nav = document.getElementById('nav');
  if (nav) nav.innerHTML = NAV.map((n,i) =>
    `<a class="nav-item ${PAGE===n.key?'on':''}" href="${esc(n.href)}"><span class="n">${i+1}</span><span>${esc(n.label)}</span></a>`).join('');
  const rd = document.getElementById('reading');
  if (rd) rd.innerHTML = S.reading.map(r =>
    `<a class="reading-item" href="${BASE}/reading/${esc(r.slug)}"><span class="idx">${String(r.seq).padStart(2,'0')}</span>
      <span><span class="t">${esc(r.title)}</span><br><span class="st">${r.status==='published'?'已發布':'待撰寫'}</span></span></a>`).join('');
}

const saved = localStorage.getItem('sm-theme');
document.documentElement.dataset.theme = saved || 'dark';
document.addEventListener('click', e => { if (e.target.closest('#theme')) {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next; localStorage.setItem('sm-theme', next);
}});

(async function init(){
  try{
    const [sc, la, rd] = await Promise.all([api('/api/scenes'), api('/api/layers'), api('/api/reading')]);
    S.scenes = sc.scenes; S.layers = la.layers; S.reading = rd.reading;
  } catch(e){ console.error(e); }
  renderNav();
  fixLinks();
  if (window.pageInit) { try { await window.pageInit(S); } catch(e){ console.error(e); } }
  fixLinks();
})();
