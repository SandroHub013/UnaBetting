'use strict';

const info = document.getElementById('hud-info');
const escHtml = SafeHtml.escape;
const PALETTE = ['#7DF9FF', '#FF6EC7', '#FFD700', '#7CFF6E', '#FF8C42',
                 '#B19CD9', '#FF5C5C', '#5CB8FF', '#F9F871', '#66FFC2',
                 '#FF9EE5', '#9DFF70'];
const hasTHREE = typeof THREE !== 'undefined';

if (typeof ForceGraph3D === 'undefined') {
  info.textContent = 'errore: libreria grafo non caricata (rete?)';
  throw new Error('ForceGraph3D missing');
}

// Build reusable star textures when Three.js is available.
const textures = {};
function texFor(group) {
  const color = PALETTE[group % PALETTE.length];
  if (textures[color]) return textures[color];
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, '#ffffff'); g.addColorStop(0.25, color);
  g.addColorStop(0.6, color + '44'); g.addColorStop(1, 'transparent');
  ctx.fillStyle = g; ctx.fillRect(0, 0, 64, 64);
  return (textures[color] = new THREE.CanvasTexture(c));
}

const elGraph = document.getElementById('graph');
const Graph = ForceGraph3D()(elGraph)
  .backgroundColor('#02020A')
  .showNavInfo(false)
  .width(elGraph.clientWidth || window.innerWidth)
  .height(elGraph.clientHeight || window.innerHeight)
  .nodeAutoColorBy('group')
  .nodeVal(n => n.__deg || 1)
  .nodeOpacity(0.92)
  .nodeResolution(12)
  .linkColor(() => 'rgba(140,160,255,0.16)')
  .linkWidth(0.4)
  .linkDirectionalParticles(1)
  .linkDirectionalParticleWidth(1.1)
  .linkDirectionalParticleSpeed(0.004)
  .linkDirectionalParticleColor(() => '#7DF9FF')
  .nodeLabel(n => `<div style="font-family:monospace;font-size:12px;color:#fff;
    background:rgba(5,8,25,.92);padding:6px 10px;border:1px solid #39406e">
    <b>${escHtml(n.label)}</b><br><span style="color:#8b93c9">${escHtml(n.file || '')}</span></div>`)
  .onNodeClick(n => {
    const r = 1 + 90 / Math.hypot(n.x, n.y, n.z);
    Graph.cameraPosition({ x: n.x * r, y: n.y * r, z: n.z * r }, n, 1200);
  });

if (hasTHREE) {
  try {
    Graph.nodeThreeObject(n => {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({
        map: texFor(n.group), blending: THREE.AdditiveBlending,
        depthWrite: false, transparent: true,
      }));
      const s = Math.min(26, 7 + Math.sqrt(n.__deg || 1) * 4);
      sp.scale.set(s, s, 1);
      return sp;
    });
  } catch (e) { /* Keep the built-in node renderer as a fallback. */ }
}

fetch('/api/graph').then(r => r.json()).then(data => {
  if (data.error) { info.textContent = 'errore: ' + (data.detail || data.error); return; }
  const deg = {};
  data.links.forEach(l => {
    deg[l.source] = (deg[l.source] || 0) + 1;
    deg[l.target] = (deg[l.target] || 0) + 1;
  });
  data.nodes.forEach(n => n.__deg = deg[n.id] || 1);
  Graph.graphData(data);
  info.innerHTML = `<b>${data.nodes.length}</b> nodi · <b>${data.links.length}</b> archi · `
    + (hasTHREE ? 'stelle additive' : 'nodi colorati') + ' · colore = community';

  if (hasTHREE) {
    try {
      const geo = new THREE.BufferGeometry();
      const N = 1500, pos = new Float32Array(N * 3);
      for (let i = 0; i < N * 3; i++) pos[i] = (Math.random() - 0.5) * 4000;
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      Graph.scene().add(new THREE.Points(geo, new THREE.PointsMaterial(
        { color: 0x8890bb, size: 1.1, transparent: true, opacity: 0.7 })));
    } catch (e) { /* The graph remains usable without the star field. */ }
  }

  let moved = false, fitted = false;
  ['mousedown', 'wheel', 'touchstart'].forEach(ev =>
    document.getElementById('graph').addEventListener(ev, () => { moved = true; }));
  Graph.onEngineStop(() => {
    if (fitted) return;
    fitted = true;
    Graph.zoomToFit(900, 40);
    setTimeout(startOrbit, 1100);
  });
  setTimeout(() => {
    if (!fitted) {
      fitted = true;
      Graph.zoomToFit(900, 40);
      setTimeout(startOrbit, 1100);
    }
  }, 4000);

  function startOrbit() {
    const cam = Graph.camera();
    const dist = Math.hypot(cam.position.x, cam.position.y, cam.position.z) || 600;
    let angle = Math.atan2(cam.position.x, cam.position.z);
    const yLevel = cam.position.y;
    (function tick() {
      if (!moved) {
        angle += 0.0009;
        Graph.cameraPosition({ x: dist * Math.sin(angle), y: yLevel, z: dist * Math.cos(angle) });
      }
      requestAnimationFrame(tick);
    })();
  }
}).catch(err => { info.textContent = 'errore fetch: ' + err.message; });

function fitSize() {
  const w = elGraph.clientWidth || window.innerWidth;
  const h = elGraph.clientHeight || window.innerHeight;
  Graph.width(w).height(h);
}
window.addEventListener('resize', fitSize);
if (window.ResizeObserver) new ResizeObserver(fitSize).observe(elGraph);
setTimeout(fitSize, 200);

document.getElementById('search').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  const q = e.target.value.toLowerCase().trim(); if (!q) return;
  const hit = Graph.graphData().nodes.find(n => (n.label || '').toLowerCase().includes(q));
  if (hit) {
    const r = 1 + 90 / Math.hypot(hit.x, hit.y, hit.z);
    Graph.cameraPosition({ x: hit.x * r, y: hit.y * r, z: hit.z * r }, hit, 1200);
  }
});
