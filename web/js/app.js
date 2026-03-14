// ── Constantes ────────────────────────────────────────────────────────────────
const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const TMP_DIR     = '/tmp/voithos';

// Módulos Python a cargar en el filesystem virtual de Pyodide (orden de dependencias)
const MODULOS_PYTHON = [
  'config.py',
  'util/__init__.py',
  'util/normalizacion.py',
  'util/validacion.py',
  'util/logger.py',
  'util/archivos.py',
  'parsers/__init__.py',
  'parsers/facturas_xml.py',
  'parsers/retenciones_xml.py',
  'parsers/sri_txt.py',
  'loaders/__init__.py',
  'loaders/sistema_excel.py',
  'loaders/ventas_personalizado.py',
  'comparadores/__init__.py',
  'comparadores/comparar_compras.py',
  'comparadores/comparar_retenciones.py',
  'reportes/__init__.py',
  'reportes/generar_excel.py',
  'voithos_web.py',
];

// ── Estado de la aplicación ───────────────────────────────────────────────────
let pyodide   = null;
let archivos  = {
  facturas:    [],   // [{name, bytes}]
  retenciones: [],
  sistema:     null, // {name, bytes}
  txt:         null,
  ventas:      null,
};

// ── Inicialización ────────────────────────────────────────────────────────────
async function iniciar() {
  setProgreso('Cargando intérprete Python (primera vez puede tardar ~20 s)...', 10);

  pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  setProgreso('Cargando librerías de datos...', 35);

  await pyodide.loadPackage(['pandas', 'openpyxl', 'micropip']);
  setProgreso('Instalando módulos auxiliares...', 60);

  await pyodide.runPythonAsync(`
import micropip
await micropip.install('defusedxml')
  `);
  setProgreso('Cargando módulos de VOITHOS...', 75);

  await cargarModulosPython();
  setProgreso('Inicializando entorno Python...', 92);

  // Importar voithos_web y dejar el módulo disponible globalmente
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, '/home/pyodide')
from voithos_web import analizar, limpiar_tmp
  `);

  setProgreso('Listo', 100);
  mostrarApp();
}

function setProgreso(mensaje, pct) {
  document.getElementById('msg-carga').textContent  = mensaje;
  document.getElementById('barra-carga').style.width = `${pct}%`;
}

async function cargarModulosPython() {
  // Crear subdirectorios en el filesystem virtual de Pyodide
  const subdirs = ['parsers', 'loaders', 'comparadores', 'reportes', 'util'];
  for (const d of subdirs) {
    try { pyodide.FS.mkdir(`/home/pyodide/${d}`); } catch (_) {}
  }

  for (const mod of MODULOS_PYTHON) {
    const resp = await fetch(`py/${mod}`);
    if (!resp.ok) throw new Error(`No se pudo cargar módulo Python: py/${mod}`);
    const code = await resp.text();
    pyodide.FS.writeFile(`/home/pyodide/${mod}`, code, { encoding: 'utf8' });
  }
}

function mostrarApp() {
  document.getElementById('pantalla-carga').style.display = 'none';
  document.getElementById('app').hidden = false;
}

// ── Zonas de drag & drop ──────────────────────────────────────────────────────
function configurarZona(idZona, idInput, tipoArchivo) {
  const zona  = document.getElementById(idZona);
  const input = document.getElementById(idInput);

  // Click para abrir selector de archivos
  zona.addEventListener('click', () => input.click());

  // Drag & drop
  zona.addEventListener('dragover', e => {
    e.preventDefault();
    zona.classList.add('drag-over');
  });
  zona.addEventListener('dragleave', () => zona.classList.remove('drag-over'));
  zona.addEventListener('drop', e => {
    e.preventDefault();
    zona.classList.remove('drag-over');
    procesarArchivosZona(e.dataTransfer.files, tipoArchivo);
  });

  // Selector de archivos
  input.addEventListener('change', () => {
    procesarArchivosZona(input.files, tipoArchivo);
    input.value = '';  // reset para permitir re-selección del mismo archivo
  });
}

async function procesarArchivosZona(fileList, tipo) {
  if (!fileList || fileList.length === 0) return;

  const archivosLeidos = [];
  for (const file of fileList) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    archivosLeidos.push({ name: file.name, bytes });
  }

  const zona = document.getElementById(`zona-${tipo}`);
  const estadoEl = zona.querySelector('.zona-estado');

  switch (tipo) {
    case 'facturas':
      archivos.facturas = archivosLeidos;
      estadoEl.textContent = resumenArchivos(archivosLeidos, 'xml', 'zip');
      break;
    case 'retenciones':
      archivos.retenciones = archivosLeidos;
      estadoEl.textContent = resumenArchivos(archivosLeidos, 'xml', 'zip');
      break;
    case 'sistema':
      archivos.sistema = archivosLeidos[0];
      estadoEl.textContent = archivosLeidos[0].name;
      break;
    case 'txt':
      archivos.txt = archivosLeidos[0];
      estadoEl.textContent = archivosLeidos[0].name;
      break;
    case 'ventas':
      archivos.ventas = archivosLeidos[0];
      estadoEl.textContent = archivosLeidos[0].name;
      break;
  }

  zona.classList.add('tiene-archivo');
  actualizarBoton();
}

function resumenArchivos(lista, ...exts) {
  const xmls = lista.filter(f => exts.some(e => f.name.toLowerCase().endsWith(e)));
  if (xmls.length === 1 && xmls[0].name.toLowerCase().endsWith('.zip')) {
    return `ZIP: ${xmls[0].name}`;
  }
  return `${lista.length} archivo${lista.length !== 1 ? 's' : ''}`;
}

function actualizarBoton() {
  const listo = archivos.facturas.length > 0 && archivos.sistema !== null;
  document.getElementById('btn-analizar').disabled = !listo;
}

// ── Análisis ──────────────────────────────────────────────────────────────────
async function ejecutarAnalisis() {
  ocultarError();
  ocultarResultados();
  mostrarProcesando(true);

  try {
    // Limpiar directorio temporal anterior
    await pyodide.runPythonAsync(`
import os, shutil
shutil.rmtree('/tmp/voithos', ignore_errors=True)
os.makedirs('/tmp/voithos', exist_ok=True)
    `);

    // Escribir facturas en el filesystem virtual
    await escribirXmls(archivos.facturas, 'facturas');

    // Escribir retenciones
    await escribirXmls(archivos.retenciones, 'retenciones');

    // Escribir sistema contable
    if (archivos.sistema) {
      pyodide.FS.writeFile(`${TMP_DIR}/sistema.xlsx`, archivos.sistema.bytes);
    }

    // Escribir TXT SRI
    if (archivos.txt) {
      pyodide.FS.writeFile(`${TMP_DIR}/comprobantes.txt`, archivos.txt.bytes);
    }

    // Escribir Ventas personalizado
    if (archivos.ventas) {
      pyodide.FS.writeFile(`${TMP_DIR}/ventas.xlsx`, archivos.ventas.bytes);
    }

    // Llamar al análisis Python
    const analizar = pyodide.globals.get('analizar');
    const resultado = analizar(
      archivos.facturas.length > 0,
      archivos.retenciones.length > 0,
      archivos.sistema !== null,
      archivos.txt !== null,
      archivos.ventas !== null,
    );

    const excelB64     = resultado.get('excel_b64');
    const statsCompras = resultado.get('stats_compras').toJs();
    const statsRet     = resultado.get('stats_ret').toJs();
    const advertencias = resultado.get('advertencias').toJs();

    resultado.destroy();

    // Mostrar resultados
    mostrarResultados(statsCompras, statsRet, advertencias, excelB64);

  } catch (err) {
    mostrarError(err.message || String(err));
  } finally {
    mostrarProcesando(false);
  }
}

async function escribirXmls(lista, tipo) {
  if (!lista || lista.length === 0) return;

  const esZip = lista.length === 1 && lista[0].name.toLowerCase().endsWith('.zip');

  if (esZip) {
    pyodide.FS.writeFile(`${TMP_DIR}/${tipo}.zip`, lista[0].bytes);
  } else {
    try {
      pyodide.FS.mkdir(`${TMP_DIR}/${tipo}`);
    } catch (_) {}
    for (const { name, bytes } of lista) {
      if (name.toLowerCase().endsWith('.xml')) {
        pyodide.FS.writeFile(`${TMP_DIR}/${tipo}/${name}`, bytes);
      }
    }
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function mostrarProcesando(activo) {
  document.getElementById('procesando').style.display      = activo ? 'flex' : 'none';
  document.getElementById('btn-analizar').style.display    = activo ? 'none' : '';
}

function mostrarError(msg) {
  const el = document.getElementById('panel-error');
  el.textContent = `Error: ${msg}`;
  el.style.display = 'block';
}

function ocultarError() {
  document.getElementById('panel-error').style.display = 'none';
}

function ocultarResultados() {
  document.getElementById('resultados').style.display = 'none';
}

function mostrarResultados(statsC, statsR, advertencias, excelB64) {
  // Stats de compras
  const sc = estadoCompras => document.getElementById(estadoCompras);

  setValue('sc-xml',      statsC.get?.('xml')             ?? statsC['xml']             ?? 0, 'normal');
  setValue('sc-sistema',  statsC.get?.('sistema')         ?? statsC['sistema']         ?? 0, 'normal');
  setValue('sc-txt',      statsC.get?.('txt')             ?? statsC['txt']             ?? 0, 'normal');
  setValue('sc-todos',    statsC.get?.('en_todos')        ?? statsC['en_todos']        ?? 0, 'ok');
  setValue('sc-falta',    statsC.get?.('no_en_sistema')   ?? statsC['no_en_sistema']   ?? 0, 'alerta');
  setValue('sc-extra',    statsC.get?.('solo_en_sistema') ?? statsC['solo_en_sistema'] ?? 0, 'alerta');

  // Stats de retenciones
  setValue('sr-xml',      statsR.get?.('ret_xml')    ?? statsR['ret_xml']    ?? 0, 'normal');
  setValue('sr-vp',       statsR.get?.('vp_con_ret') ?? statsR['vp_con_ret'] ?? 0, 'normal');
  setValue('sr-todos',    statsR.get?.('en_ambos')   ?? statsR['en_ambos']   ?? 0, 'ok');
  setValue('sr-falta',    statsR.get?.('sin_sistema')?? statsR['sin_sistema']?? 0, 'alerta');
  setValue('sr-extra',    statsR.get?.('sin_xml')    ?? statsR['sin_xml']    ?? 0, 'alerta');

  // Advertencias
  const panelAdv = document.getElementById('advertencias');
  if (advertencias && advertencias.length > 0) {
    const ul = panelAdv.querySelector('ul');
    ul.innerHTML = '';
    for (const adv of advertencias) {
      const li = document.createElement('li');
      li.textContent = adv;
      ul.appendChild(li);
    }
    panelAdv.style.display = 'block';
  } else {
    panelAdv.style.display = 'none';
  }

  // Botón de descarga
  document.getElementById('btn-descargar').onclick = () => descargarExcel(excelB64);

  document.getElementById('resultados').style.display = 'block';
  document.getElementById('resultados').scrollIntoView({ behavior: 'smooth' });
}

function setValue(id, valor, clase) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = valor;
  el.className   = `stat-valor ${valor > 0 && clase === 'alerta' ? 'alerta' : clase}`;
}

function descargarExcel(b64) {
  const bytes   = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const blob    = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const url     = URL.createObjectURL(blob);
  const a       = document.createElement('a');
  const fecha   = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  a.href        = url;
  a.download    = `AUDITORIA_VOITHOS_${fecha}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Configurar zonas de drop
  configurarZona('zona-facturas',    'input-facturas',    'facturas');
  configurarZona('zona-retenciones', 'input-retenciones', 'retenciones');
  configurarZona('zona-sistema',     'input-sistema',     'sistema');
  configurarZona('zona-txt',         'input-txt',         'txt');
  configurarZona('zona-ventas',      'input-ventas',      'ventas');

  // Botón analizar
  document.getElementById('btn-analizar').addEventListener('click', ejecutarAnalisis);

  // Iniciar Pyodide
  iniciar().catch(err => {
    document.getElementById('msg-carga').textContent =
      `Error al cargar: ${err.message}. Recarga la página.`;
    document.getElementById('spinner-carga').style.borderTopColor = '#f38ba8';
  });
});
