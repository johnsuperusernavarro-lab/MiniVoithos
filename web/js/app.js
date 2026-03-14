// ── Constantes ────────────────────────────────────────────────────────────────
const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const TMP         = '/tmp/voithos';

// Módulos Python empaquetados en un JSON único (evita bloqueos de .py en itch.io)
const BUNDLE_URL = 'py_bundle.json';

// ── Estado por herramienta ────────────────────────────────────────────────────
const archivos = {
  auditoria:   { facturas: [], retenciones: [], sistema: null, txt: null, ventas: null },
  compras:     { facturas: [], sistema: null, txt: null },
  retenciones: { retenciones: [], ventas: null },
  pdfs:        { facturas: [], retenciones: [] },
};

// Qué campos son obligatorios para habilitar el botón de cada herramienta
const REQUERIDOS = {
  auditoria:   a => a.facturas.length > 0 && a.sistema !== null,
  compras:     a => a.facturas.length > 0 && a.sistema !== null,
  retenciones: a => a.retenciones.length > 0 && a.ventas !== null,
  pdfs:        a => a.facturas.length > 0 || a.retenciones.length > 0,
};

let pyodide = null;

// ── Inicialización ────────────────────────────────────────────────────────────
async function iniciar() {
  setProgreso('Cargando intérprete Python…', 10);
  pyodide = await loadPyodide({ indexURL: PYODIDE_URL });

  setProgreso('Cargando pandas…', 35);
  await pyodide.loadPackage(['pandas', 'micropip']);

  setProgreso('Instalando openpyxl y defusedxml…', 60);
  await pyodide.runPythonAsync(`
import micropip
await micropip.install(['openpyxl', 'defusedxml'])
  `);

  setProgreso('Cargando módulos VOITHOS…', 78);
  await cargarModulosPython();

  setProgreso('Inicializando…', 94);
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, '/home/pyodide')
from voithos_web import analizar, analizar_compras, analizar_retenciones, organizar_pdfs, limpiar_tmp
  `);

  setProgreso('Listo', 100);
  setTimeout(mostrarApp, 300);
}

function setProgreso(msg, pct) {
  document.getElementById('msg-carga').textContent   = msg;
  document.getElementById('barra-carga').style.width = `${pct}%`;
}

async function cargarModulosPython() {
  const resp = await fetch(BUNDLE_URL);
  if (!resp.ok) throw new Error(`No se pudo cargar ${BUNDLE_URL} (${resp.status})`);
  const bundle = await resp.json();

  const subdirs = ['parsers', 'loaders', 'comparadores', 'reportes', 'util'];
  for (const d of subdirs) {
    try { pyodide.FS.mkdir(`/home/pyodide/${d}`); } catch (_) {}
  }
  for (const [ruta, contenido] of Object.entries(bundle)) {
    pyodide.FS.writeFile(`/home/pyodide/${ruta}`, contenido, { encoding: 'utf8' });
  }
}

function mostrarApp() {
  document.getElementById('pantalla-carga').style.display = 'none';
  document.getElementById('app').hidden = false;
}

// ── Navegación ────────────────────────────────────────────────────────────────
function navegar(panel) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`panel-${panel}`).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll(`[data-panel="${panel}"]`).forEach(b => b.classList.add('active'));
}

// ── Zonas de drop ─────────────────────────────────────────────────────────────
function configurarZonas() {
  document.querySelectorAll('.zona-drop').forEach(zona => {
    const tool = zona.dataset.tool;
    const tipo = zona.dataset.tipo;
    const inputId = zona.querySelector('input[type="file"]').id;
    const input   = document.getElementById(inputId);

    zona.addEventListener('click', () => input.click());

    zona.addEventListener('dragover', e => { e.preventDefault(); zona.classList.add('drag-over'); });
    zona.addEventListener('dragleave', () => zona.classList.remove('drag-over'));
    zona.addEventListener('drop', e => {
      e.preventDefault();
      zona.classList.remove('drag-over');
      manejarArchivos(e.dataTransfer.files, tool, tipo, zona);
    });

    input.addEventListener('change', () => {
      manejarArchivos(input.files, tool, tipo, zona);
      input.value = '';
    });
  });
}

async function manejarArchivos(fileList, tool, tipo, zona) {
  if (!fileList || fileList.length === 0) return;

  const leidos = [];
  for (const file of fileList) {
    leidos.push({ name: file.name, bytes: new Uint8Array(await file.arrayBuffer()) });
  }

  const estado = zona.querySelector('.zona-estado');

  // Tipos múltiples (XMLs/ZIPs)
  if (tipo === 'facturas' || tipo === 'retenciones') {
    archivos[tool][tipo] = leidos;
    estado.textContent = leidos.length === 1 && leidos[0].name.endsWith('.zip')
      ? `ZIP: ${leidos[0].name}`
      : `${leidos.length} archivo${leidos.length !== 1 ? 's' : ''}`;
  } else {
    // Archivo único
    archivos[tool][tipo] = leidos[0];
    estado.textContent   = leidos[0].name;
  }

  zona.classList.add('tiene-archivo');
  actualizarBoton(tool);
}

function actualizarBoton(tool) {
  const btn = document.getElementById(`btn-${tool}`);
  if (btn) btn.disabled = !REQUERIDOS[tool](archivos[tool]);
}

// ── Escritura al filesystem virtual de Pyodide ────────────────────────────────
async function prepararTmp() {
  await pyodide.runPythonAsync(`
import os, shutil
shutil.rmtree('${TMP}', ignore_errors=True)
os.makedirs('${TMP}', exist_ok=True)
  `);
}

function escribirXmls(lista, tipo) {
  if (!lista || lista.length === 0) return;
  const esZip = lista.length === 1 && lista[0].name.toLowerCase().endsWith('.zip');
  if (esZip) {
    pyodide.FS.writeFile(`${TMP}/${tipo}.zip`, lista[0].bytes);
  } else {
    try { pyodide.FS.mkdir(`${TMP}/${tipo}`); } catch (_) {}
    for (const { name, bytes } of lista) {
      if (name.toLowerCase().endsWith('.xml')) {
        pyodide.FS.writeFile(`${TMP}/${tipo}/${name}`, bytes);
      }
    }
  }
}

function escribirArchivo(obj, nombre) {
  if (obj) pyodide.FS.writeFile(`${TMP}/${nombre}`, obj.bytes);
}

// ── Helpers de UI ─────────────────────────────────────────────────────────────
function mostrarProcesando(tool, activo) {
  document.getElementById(`proc-${tool}`).style.display = activo ? 'flex' : 'none';
  document.getElementById(`btn-${tool}`).style.display  = activo ? 'none' : '';
}

function mostrarError(tool, msg) {
  const el = document.getElementById(`err-${tool}`);
  el.textContent    = `Error: ${msg}`;
  el.style.display  = 'block';
  document.getElementById(`res-${tool}`).style.display = 'none';
}

function ocultarError(tool) {
  document.getElementById(`err-${tool}`).style.display = 'none';
}

function mostrarAdvertencias(tool, lista) {
  const el = document.getElementById(`adv-${tool}`);
  if (!lista || lista.length === 0) { el.style.display = 'none'; return; }
  const ul = el.querySelector('ul');
  ul.innerHTML = '';
  lista.forEach(adv => { const li = document.createElement('li'); li.textContent = adv; ul.appendChild(li); });
  el.style.display = 'block';
}

function statsCard(titulo, filas) {
  const card = document.createElement('div');
  card.className = 'stats-card';
  card.innerHTML = `<h4>${titulo}</h4>` + filas.map(([lbl, val, cls]) =>
    `<div class="stat-linea"><span>${lbl}</span>
     <span class="stat-val ${val > 0 && cls === 'alerta' ? 'alerta' : cls}">${val ?? 0}</span></div>`
  ).join('');
  return card;
}

function renderStats(containerId, statsC, statsR) {
  const cont = document.getElementById(containerId);
  cont.innerHTML = '';

  if (statsC && Object.keys(statsC).length > 0) {
    cont.appendChild(statsCard('Compras', [
      ['XMLs descargados',          statsC.xml             ?? 0, 'normal'],
      ['En Sistema',                statsC.sistema         ?? 0, 'normal'],
      ['En TXT SRI',                statsC.txt             ?? 0, 'normal'],
      ['Coinciden en los 3',        statsC.en_todos        ?? 0, 'ok'],
      ['En SRI pero NO en Sistema', statsC.no_en_sistema   ?? 0, 'alerta'],
      ['Solo en Sistema',           statsC.solo_en_sistema ?? 0, 'alerta'],
    ]));
  }

  if (statsR && Object.keys(statsR).length > 0) {
    cont.appendChild(statsCard('Retenciones', [
      ['XMLs de retención',            statsR.ret_xml    ?? 0, 'normal'],
      ['Ventas con retención en Sist.', statsR.vp_con_ret ?? 0, 'normal'],
      ['Coinciden',                    statsR.en_ambos   ?? 0, 'ok'],
      ['XML sin registro en Sistema',  statsR.sin_sistema ?? 0, 'alerta'],
      ['Sistema sin XML de respaldo',  statsR.sin_xml    ?? 0, 'alerta'],
    ]));
  }
}

function pyDictToJs(proxy) {
  // Convierte PyProxy de dict a objeto JS plano
  const obj = {};
  try {
    proxy.toJs().forEach((v, k) => { obj[k] = (v && typeof v.toJs === 'function') ? Object.fromEntries(v.toJs()) : v; });
  } catch (_) {}
  return obj;
}

function pyListToJs(proxy) {
  try { return [...proxy.toJs()]; } catch (_) { return []; }
}

function descargarExcel(b64, nombre) {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const blob  = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const url   = URL.createObjectURL(blob);
  const a     = document.createElement('a');
  a.href = url; a.download = nombre; a.click();
  URL.revokeObjectURL(url);
}

function descargarZip(b64, nombre) {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const blob  = new Blob([bytes], { type: 'application/zip' });
  const url   = URL.createObjectURL(blob);
  const a     = document.createElement('a');
  a.href = url; a.download = nombre; a.click();
  URL.revokeObjectURL(url);
}

function fechaHoy() {
  return new Date().toISOString().slice(0,10).replace(/-/g,'');
}

// ── Descargar macro UI.Vision ─────────────────────────────────────────────────
async function descargarMacro() {
  const resp = await fetch('macros/descargar_sri.json');
  if (!resp.ok) { alert('No se pudo cargar el macro.'); return; }
  const blob = await resp.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'descargar_sri.json'; a.click();
  URL.revokeObjectURL(url);
}

// ── Auditoría Mensual ─────────────────────────────────────────────────────────
async function ejecutarAuditoria() {
  const a = archivos.auditoria;
  ocultarError('auditoria');
  mostrarProcesando('auditoria', true);

  try {
    await prepararTmp();
    escribirXmls(a.facturas,    'facturas');
    escribirXmls(a.retenciones, 'retenciones');
    escribirArchivo(a.sistema,  'sistema.xlsx');
    escribirArchivo(a.txt,      'comprobantes.txt');
    escribirArchivo(a.ventas,   'ventas.xlsx');

    const fn = pyodide.globals.get('analizar');
    const r  = fn(a.facturas.length > 0, a.retenciones.length > 0,
                  a.sistema !== null, a.txt !== null, a.ventas !== null);

    const b64  = r.get('excel_b64');
    const sc   = pyDictToJs(r.get('stats_compras'));
    const sr   = pyDictToJs(r.get('stats_ret'));
    const adv  = pyListToJs(r.get('advertencias'));
    r.destroy();

    renderStats('stats-auditoria', sc, sr);
    mostrarAdvertencias('auditoria', adv);
    document.getElementById('desc-auditoria').onclick = () =>
      descargarExcel(b64, `AUDITORIA_VOITHOS_${fechaHoy()}.xlsx`);
    document.getElementById('res-auditoria').style.display = 'block';

  } catch (e) {
    mostrarError('auditoria', e.message || String(e));
  } finally {
    mostrarProcesando('auditoria', false);
  }
}

// ── Solo Compras ──────────────────────────────────────────────────────────────
async function ejecutarCompras() {
  const a = archivos.compras;
  ocultarError('compras');
  mostrarProcesando('compras', true);

  try {
    await prepararTmp();
    escribirXmls(a.facturas,   'facturas');
    escribirArchivo(a.sistema, 'sistema.xlsx');
    escribirArchivo(a.txt,     'comprobantes.txt');

    const fn = pyodide.globals.get('analizar_compras');
    const r  = fn(a.facturas.length > 0, a.sistema !== null, a.txt !== null);

    const b64 = r.get('excel_b64');
    const sc  = pyDictToJs(r.get('stats_compras'));
    const adv = pyListToJs(r.get('advertencias'));
    r.destroy();

    renderStats('stats-compras', sc, null);
    mostrarAdvertencias('compras', adv);
    document.getElementById('desc-compras').onclick = () =>
      descargarExcel(b64, `COMPRAS_VOITHOS_${fechaHoy()}.xlsx`);
    document.getElementById('res-compras').style.display = 'block';

  } catch (e) {
    mostrarError('compras', e.message || String(e));
  } finally {
    mostrarProcesando('compras', false);
  }
}

// ── Solo Retenciones ──────────────────────────────────────────────────────────
async function ejecutarRetenciones() {
  const a = archivos.retenciones;
  ocultarError('retenciones');
  mostrarProcesando('retenciones', true);

  try {
    await prepararTmp();
    escribirXmls(a.retenciones, 'retenciones');
    escribirArchivo(a.ventas,   'ventas.xlsx');

    const fn = pyodide.globals.get('analizar_retenciones');
    const r  = fn(a.retenciones.length > 0, a.ventas !== null);

    const b64 = r.get('excel_b64');
    const sr  = pyDictToJs(r.get('stats_ret'));
    const adv = pyListToJs(r.get('advertencias'));
    r.destroy();

    renderStats('stats-retenciones', null, sr);
    mostrarAdvertencias('retenciones', adv);
    document.getElementById('desc-retenciones').onclick = () =>
      descargarExcel(b64, `RETENCIONES_VOITHOS_${fechaHoy()}.xlsx`);
    document.getElementById('res-retenciones').style.display = 'block';

  } catch (e) {
    mostrarError('retenciones', e.message || String(e));
  } finally {
    mostrarProcesando('retenciones', false);
  }
}

// ── Organizar PDFs ────────────────────────────────────────────────────────────
async function ejecutarPDFs() {
  const a = archivos.pdfs;
  ocultarError('pdfs');
  mostrarProcesando('pdfs', true);

  try {
    await prepararTmp();
    escribirXmls(a.facturas,    'facturas');
    escribirXmls(a.retenciones, 'retenciones');

    const fn = pyodide.globals.get('organizar_pdfs');
    const r  = fn(a.facturas.length > 0, a.retenciones.length > 0);

    const facZip = r.get('facturas_zip_b64');
    const retZip = r.get('retenciones_zip_b64');
    const stats  = pyDictToJs(r.get('stats'));
    const adv    = pyListToJs(r.get('advertencias'));
    r.destroy();

    // Mostrar botones de descarga
    const cont = document.getElementById('pdf-descargas');
    cont.innerHTML = '';

    if (facZip) {
      const card = document.createElement('div');
      card.className = 'pdf-stat-card';
      const sf = stats.facturas || {};
      card.innerHTML = `<h4>Facturas</h4>
        <p>✓ ${sf.copiados ?? 0} renombrados · ${sf.sin_pdf ?? 0} sin PDF · ${sf.errores ?? 0} errores</p>`;
      const btn = document.createElement('button');
      btn.className = 'btn-descarga';
      btn.textContent = '⬇ Descargar ZIP Facturas';
      btn.onclick = () => descargarZip(facZip, `PDFs_Facturas_${fechaHoy()}.zip`);
      card.appendChild(btn);
      cont.appendChild(card);
    }

    if (retZip) {
      const card = document.createElement('div');
      card.className = 'pdf-stat-card';
      const sr = stats.retenciones || {};
      card.innerHTML = `<h4>Retenciones</h4>
        <p>✓ ${sr.copiados ?? 0} renombrados · ${sr.sin_pdf ?? 0} sin PDF · ${sr.errores ?? 0} errores</p>`;
      const btn = document.createElement('button');
      btn.className = 'btn-descarga';
      btn.textContent = '⬇ Descargar ZIP Retenciones';
      btn.onclick = () => descargarZip(retZip, `PDFs_Retenciones_${fechaHoy()}.zip`);
      card.appendChild(btn);
      cont.appendChild(card);
    }

    mostrarAdvertencias('pdfs', adv);
    document.getElementById('res-pdfs').style.display = 'block';

  } catch (e) {
    mostrarError('pdfs', e.message || String(e));
  } finally {
    mostrarProcesando('pdfs', false);
  }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
function mostrarErrorCarga(msg) {
  document.getElementById('msg-carga').textContent = msg;
  document.getElementById('spinner-carga').style.borderTopColor = '#f38ba8';
}

document.addEventListener('DOMContentLoaded', () => {
  try {
    // Navegación: sidebar + tarjetas del inicio
    document.querySelectorAll('[data-panel]').forEach(btn => {
      btn.addEventListener('click', () => navegar(btn.dataset.panel));
    });

    // Configurar todas las zonas de drop
    configurarZonas();

    // Botones de acción
    document.getElementById('btn-auditoria').addEventListener('click',   ejecutarAuditoria);
    document.getElementById('btn-compras').addEventListener('click',     ejecutarCompras);
    document.getElementById('btn-retenciones').addEventListener('click', ejecutarRetenciones);
    document.getElementById('btn-pdfs').addEventListener('click',        ejecutarPDFs);
    document.getElementById('btn-dl-macro').addEventListener('click',    descargarMacro);

  } catch (err) {
    mostrarErrorCarga(`Error al inicializar UI: ${err.message}`);
    return;
  }

  // Iniciar Pyodide
  iniciar().catch(err => mostrarErrorCarga(`Error al cargar: ${err.message}. Recarga la página.`));
});
