"""
glosario_panel.py

Panel de Glosario de nombres propios (personajes, parajes, elementos...)
compartido entre todos los tomos de una serie.

Flujo de trabajo:
    1. El usuario (fuera de la app, vía chat con IA) genera un fichero
       "glosario_TomoXX_import.json" con la estructura:
           { "tomo": "Tomo11", "entradas": [ {...}, {...} ] }
       donde cada entrada tiene: nombre, tipo, tomo, pagina, globo, nota.
    2. Desde este panel, botón "Importar tomo...", se selecciona ese
       fichero y sus entradas se fusionan en el glosario global
       (glosario.json), evitando duplicados exactos.
    3. El glosario global se puede además editar a mano (añadir, editar,
       eliminar), filtrar por nombre/tipo/tomo simultáneamente, y
       exportar como TXT para compartir.
    4. Las entradas de tipo "Error" (incidencias de traducción a revisar,
       nombres inconsistentes, etc.) se resaltan en negrita en la tabla,
       y en el TXT exportado usan el delimitador PS "++negrita++".

El glosario.json vive en una carpeta elegida por el usuario (normalmente
la carpeta raíz de la serie, compartida por todos los TomoXX), y la ruta
se recuerda en pcfg.glosario_path.
"""

import os
import os.path as osp
import json
import uuid
from datetime import datetime

from qtpy.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QComboBox,
    QLabel, QMessageBox, QFileDialog, QHeaderView, QAbstractItemView,
    QSplitter, QTextEdit, QToolButton, QListWidget
)
from qtpy.QtCore import Qt, Signal
from functools import partial

from ballontranslator.utils.config import pcfg, save_config


ID_ROLE = Qt.UserRole + 1

TIPOS_GLOSARIO = ['Personaje', 'Paraje', 'Elemento', 'Error', 'Otro']

# Columna 0 (Nombre) y columna 1 (botón de Apariciones) se gestionan aparte;
# el resto son columnas de datos "normales".
COL_NOMBRE = 0
COL_APARICIONES = 1
COLUMNAS_DATOS = [
    ('tipo',   'Tipo'),
    ('tomo',   'Tomo'),
    ('pagina', 'Página'),
    ('globo',  'Globo'),
    ('nota',   'Nota'),
]
CABECERAS_TABLA = ['Nombre', 'Apariciones'] + [c[1] for c in COLUMNAS_DATOS]
N_COLUMNAS = len(CABECERAS_TABLA)


# --------------------------------------------------------------------------
#  Capa de datos
# --------------------------------------------------------------------------

class GlosarioManager:
    """Carga, guarda y fusiona el glosario.json global."""

    def __init__(self, path: str = None):
        self.path = path
        self.entradas = []   # lista de dicts con 'id' + campos de COLUMNAS
        if path and osp.exists(path):
            self.load(path)

    # -- io -----------------------------------------------------------
    def load(self, path: str):
        self.path = path
        try:
            with open(path, 'r', encoding='utf8') as f:
                data = json.load(f)
            self.entradas = data.get('entradas', [])
            # asegurar que todas las entradas tienen id (compatibilidad)
            dirty = False
            for e in self.entradas:
                if 'id' not in e:
                    e['id'] = str(uuid.uuid4())
                    dirty = True
            if dirty:
                self.save()
        except Exception:
            self.entradas = []

    def save(self):
        if not self.path:
            return
        os.makedirs(osp.dirname(self.path) or '.', exist_ok=True)
        # copia de seguridad de la versión anterior antes de sobrescribir
        if osp.exists(self.path):
            try:
                import shutil
                shutil.copyfile(self.path, self.path + '.bak')
            except Exception:
                pass
        data = {
            'actualizado': datetime.now().isoformat(timespec='seconds'),
            'entradas': self.entradas,
        }
        with open(self.path, 'w', encoding='utf8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # -- crud -----------------------------------------------------------
    def add_entry(self, entry: dict) -> str:
        entry = dict(entry)
        entry['id'] = entry.get('id') or str(uuid.uuid4())
        self.entradas.append(entry)
        self.save()
        return entry['id']

    def update_entry(self, entry_id: str, entry: dict):
        for i, e in enumerate(self.entradas):
            if e.get('id') == entry_id:
                entry = dict(entry)
                entry['id'] = entry_id
                self.entradas[i] = entry
                self.save()
                return True
        return False

    def delete_entry(self, entry_id: str):
        before = len(self.entradas)
        self.entradas = [e for e in self.entradas if e.get('id') != entry_id]
        if len(self.entradas) != before:
            self.save()
            return True
        return False

    def delete_entries(self, entry_ids):
        """Borra varias entradas de golpe, guardando una sola vez."""
        ids = set(entry_ids)
        before = len(self.entradas)
        self.entradas = [e for e in self.entradas if e.get('id') not in ids]
        borradas = before - len(self.entradas)
        if borradas:
            self.save()
        return borradas

    def get_entry(self, entry_id: str):
        for e in self.entradas:
            if e.get('id') == entry_id:
                return e
        return None

    # -- importar tomo -----------------------------------------------------------
    def import_tomo_file(self, import_path: str):
        """Fusiona las entradas de un glosario_TomoXX_import.json.
        Devuelve (num_añadidas, num_duplicadas_omitidas, conflictos), donde
        `conflictos` es una lista de claves (tomo, página, globo) que, tras
        la importación, tienen más de un nombre distinto asociado — no se
        borra ni sustituye nada automáticamente (podría ser una corrección
        real, p. ej. "Lord Heron" -> "Lord Sobold", o dos personajes que
        legítimamente comparten globo, p. ej. un anuncio de boda). Se deja
        a criterio del usuario revisarlas y borrar la que sobre con la
        selección múltiple de la tabla.
        """
        with open(import_path, 'r', encoding='utf8') as f:
            data = json.load(f)
        nuevas = data.get('entradas', [])
        tomo_defecto = data.get('tomo', '')

        def clave_exacta(e):
            return (
                e.get('nombre', '').strip().lower(),
                e.get('tomo', tomo_defecto).strip().lower(),
                str(e.get('pagina', '')).strip(),
                str(e.get('globo', '')).strip(),
            )

        def clave_evento(e):
            return (
                e.get('tomo', tomo_defecto).strip().lower(),
                str(e.get('pagina', '')).strip(),
                str(e.get('globo', '')).strip(),
            )

        existentes_exactas = {clave_exacta(e) for e in self.entradas}

        añadidas = 0
        omitidas = 0
        for e in nuevas:
            entry = {
                'nombre': e.get('nombre', '').strip(),
                'tipo': e.get('tipo', '').strip() or 'Otro',
                'tomo': e.get('tomo', tomo_defecto).strip(),
                'pagina': str(e.get('pagina', '')).strip(),
                'globo': str(e.get('globo', '')).strip(),
                'nota': e.get('nota', '').strip(),
            }
            if e.get('apariciones'):
                entry['apariciones'] = e['apariciones']
            if not entry['nombre']:
                continue

            k_exacta = clave_exacta(entry)
            if k_exacta in existentes_exactas:
                omitidas += 1
                continue

            existentes_exactas.add(k_exacta)
            entry['id'] = str(uuid.uuid4())
            self.entradas.append(entry)
            añadidas += 1

        # tras fusionar, se detectan (sin tocar nada) los huecos con más de
        # un nombre distinto dentro del tomo que se acaba de importar
        conflictos = []
        por_evento = {}
        for e in self.entradas:
            if e.get('tomo', '').strip().lower() != tomo_defecto.strip().lower():
                continue
            k = clave_evento(e)
            por_evento.setdefault(k, set()).add(e.get('nombre', ''))
        for (tomo, pagina, globo), nombres in por_evento.items():
            if len(nombres) > 1:
                conflictos.append((tomo, pagina, globo, sorted(nombres)))
        conflictos.sort(key=lambda c: (c[1], c[2]))

        if añadidas:
            self.save()
        return añadidas, omitidas, conflictos

    # -- consulta -----------------------------------------------------------
    def tomos(self):
        return sorted({e.get('tomo', '') for e in self.entradas if e.get('tomo')})

    def filtrar(self, nombre_substr='', tipo='', tomo=''):
        nombre_substr = (nombre_substr or '').strip().lower()
        out = []
        for e in self.entradas:
            if nombre_substr and nombre_substr not in e.get('nombre', '').lower():
                continue
            if tipo and tipo != 'Todos' and e.get('tipo', '') != tipo:
                continue
            if tomo and tomo != 'Todos' and e.get('tomo', '') != tomo:
                continue
            out.append(e)
        out.sort(key=lambda e: (e.get('nombre', '').lower(), e.get('tomo', ''), e.get('pagina', '')))
        return out


# --------------------------------------------------------------------------
#  UI
# --------------------------------------------------------------------------

class GlosarioPanel(QDialog):

    glosario_actualizado = Signal()

    def __init__(self, mainwindow, *args, **kwargs):
        super().__init__(mainwindow, *args, **kwargs)
        self.mainwindow = mainwindow
        self.setWindowTitle(self.tr('Glosario de la serie'))
        self.resize(920, 620)
        # Modal: bloquea el resto del programa mientras está abierto.
        self.setModal(True)
        # Botones de minimizar/maximizar en la barra de título, para poder
        # maximizar con doble clic (comportamiento estándar de Windows).
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowMinimizeButtonHint
        )

        self.mgr = GlosarioManager()
        self._entry_actual_id = None   # id de la entrada cargada en el formulario (None = nueva)
        self._sort_col = None          # columna por la que se ordena (None = orden por defecto)
        self._sort_asc = True          # ascendente/descendente
        self._apariciones_pendientes = None  # lista a adjuntar a la próxima entrada nueva guardada

        self._setup_ui()
        self._resolver_ruta_glosario(preguntar_si_falta=False)
        self._refrescar_todo()

    # ------------------------------------------------------------------
    #  Construcción UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)

        # -- cabecera: ruta del glosario + abrir otro / cambiar carpeta de guardado
        cab = QHBoxLayout()
        self.lbl_ruta = QLabel('')
        self.lbl_ruta.setStyleSheet('color: gray;')
        btn_abrir_glosario = QPushButton(self.tr('Abrir glosario...'))
        btn_abrir_glosario.setToolTip(
            self.tr('Selecciona directamente el glosario.json de otra serie para visualizarlo/editarlo'))
        btn_abrir_glosario.clicked.connect(self.on_abrir_glosario)
        btn_cambiar_ruta = QPushButton(self.tr('Cambiar carpeta...'))
        btn_cambiar_ruta.setToolTip(
            self.tr('Elige (o crea) la carpeta donde se guardará el glosario.json de la serie actual'))
        btn_cambiar_ruta.clicked.connect(self.on_cambiar_ruta)
        cab.addWidget(QLabel(self.tr('Glosario:')))
        cab.addWidget(self.lbl_ruta, 1)
        cab.addWidget(btn_abrir_glosario)
        cab.addWidget(btn_cambiar_ruta)
        root.addLayout(cab)

        # -- filtros
        filtros = QHBoxLayout()
        self.ed_filtro_nombre = QLineEdit()
        self.ed_filtro_nombre.setPlaceholderText(self.tr('Filtrar por nombre...'))
        self.ed_filtro_nombre.textChanged.connect(self._refrescar_tabla)

        self.cb_filtro_tipo = QComboBox()
        self.cb_filtro_tipo.addItem('Todos')
        self.cb_filtro_tipo.addItems(TIPOS_GLOSARIO)
        self.cb_filtro_tipo.currentIndexChanged.connect(self._refrescar_tabla)

        self.cb_filtro_tomo = QComboBox()
        self.cb_filtro_tomo.addItem('Todos')
        self.cb_filtro_tomo.currentIndexChanged.connect(self._refrescar_tabla)

        filtros.addWidget(QLabel(self.tr('Nombre:')))
        filtros.addWidget(self.ed_filtro_nombre, 2)
        filtros.addWidget(QLabel(self.tr('Tipo:')))
        filtros.addWidget(self.cb_filtro_tipo, 1)
        filtros.addWidget(QLabel(self.tr('Tomo:')))
        filtros.addWidget(self.cb_filtro_tomo, 1)
        root.addLayout(filtros)

        # -- splitter: tabla arriba, formulario abajo
        splitter = QSplitter(Qt.Vertical)

        self.tabla = QTableWidget(0, N_COLUMNAS)
        self.tabla.setHorizontalHeaderLabels(CABECERAS_TABLA)
        self.tabla.horizontalHeader().setSectionResizeMode(COL_NOMBRE, QHeaderView.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(COL_APARICIONES, QHeaderView.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(N_COLUMNAS - 1, QHeaderView.Stretch)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # El ordenado automático de Qt (setSortingEnabled) no es compatible con los
        # botones incrustados de la columna "Apariciones" (Qt no los reubica al
        # reordenar filas). En su lugar, ordenamos nosotros mismos la lista de
        # entradas antes de repintar la tabla; así el clic en cabecera sigue
        # funcionando, ascendente/descendente, en todas las columnas.
        self.tabla.setSortingEnabled(False)
        self.tabla.horizontalHeader().setSortIndicatorShown(True)
        self.tabla.horizontalHeader().sectionClicked.connect(self.on_cabecera_clicada)
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_tabla)
        splitter.addWidget(self.tabla)

        # -- barra de acciones sobre la selección (multi-línea / por tomo)
        sel_bar = QHBoxLayout()
        self.lbl_seleccion = QLabel(self.tr('0 seleccionadas'))
        self.lbl_seleccion.setStyleSheet('color: gray;')
        btn_sel_todo_visible = QPushButton(self.tr('Seleccionar todo lo filtrado'))
        btn_sel_todo_visible.setToolTip(
            self.tr('Filtra por Tomo (o Nombre/Tipo) y pulsa aquí para seleccionar todas las filas visibles'))
        btn_sel_todo_visible.clicked.connect(self.on_seleccionar_todo_filtrado)
        btn_sel_ninguno = QPushButton(self.tr('Deseleccionar'))
        btn_sel_ninguno.clicked.connect(self.tabla.clearSelection)
        self.btn_eliminar_seleccion = QPushButton(self.tr('Eliminar seleccionadas'))
        self.btn_eliminar_seleccion.clicked.connect(self.on_eliminar_entrada)
        self.btn_eliminar_seleccion.setEnabled(False)
        sel_bar.addWidget(self.lbl_seleccion)
        sel_bar.addStretch(1)
        sel_bar.addWidget(btn_sel_todo_visible)
        sel_bar.addWidget(btn_sel_ninguno)
        sel_bar.addWidget(self.btn_eliminar_seleccion)
        root.addLayout(sel_bar)

        # -- formulario de edición integrado
        form_box = QGroupBox(self.tr('Entrada'))
        form_layout = QFormLayout(form_box)

        self.ed_nombre = QLineEdit()
        self.cb_tipo = QComboBox()
        self.cb_tipo.setEditable(True)
        self.cb_tipo.addItems(TIPOS_GLOSARIO)
        self.ed_tomo = QLineEdit()
        self.ed_pagina = QLineEdit()
        self.ed_globo = QLineEdit()
        self.ed_nota = QLineEdit()

        form_layout.addRow(self.tr('Nombre:'), self.ed_nombre)
        form_layout.addRow(self.tr('Tipo:'), self.cb_tipo)
        form_layout.addRow(self.tr('Tomo:'), self.ed_tomo)
        form_layout.addRow(self.tr('Página:'), self.ed_pagina)
        form_layout.addRow(self.tr('Globo:'), self.ed_globo)
        form_layout.addRow(self.tr('Nota:'), self.ed_nota)

        self.lbl_pendientes = QLabel('')
        self.lbl_pendientes.setStyleSheet('color: gray; font-size: 11px;')
        self.lbl_pendientes.setWordWrap(True)
        form_layout.addRow('', self.lbl_pendientes)

        botones_form = QHBoxLayout()
        self.btn_nueva = QPushButton(self.tr('Nueva entrada'))
        self.btn_nueva.clicked.connect(self.on_nueva_entrada)
        self.btn_guardar_entrada = QPushButton(self.tr('Guardar entrada'))
        self.btn_guardar_entrada.clicked.connect(self.on_guardar_entrada)
        self.btn_anadir_aparicion = QPushButton(self.tr('Añadir aparición'))
        self.btn_anadir_aparicion.setToolTip(
            self.tr('Añade a mano una página/globo a la lista de apariciones de esta entrada '
                    '(para ver la lista completa, usa el botón de la columna "Apariciones")'))
        self.btn_anadir_aparicion.clicked.connect(self.on_anadir_aparicion)
        self.btn_anadir_aparicion.setEnabled(False)
        botones_form.addWidget(self.btn_nueva)
        botones_form.addWidget(self.btn_guardar_entrada)
        botones_form.addWidget(self.btn_anadir_aparicion)
        form_layout.addRow(botones_form)

        splitter.addWidget(form_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        # -- pie: importar / exportar
        pie = QHBoxLayout()
        btn_importar = QPushButton(self.tr('Importar tomo...'))
        btn_importar.setToolTip(self.tr('Importar un glosario_TomoXX_import.json generado con IA'))
        btn_importar.clicked.connect(self.on_importar_tomo)
        btn_export_json = QPushButton(self.tr('Exportar JSON (import)'))
        btn_export_json.setToolTip(
            self.tr('Regenera un glosario_TomoXX_import.json (o glosario_Serie_import.json) '
                    'a partir de lo que tengas filtrado, útil tras editar entradas a mano'))
        btn_export_json.clicked.connect(self.on_exportar_json_import)
        btn_export_txt = QPushButton(self.tr('Exportar TXT'))
        btn_export_txt.clicked.connect(self.on_exportar_txt)
        btn_cerrar = QPushButton(self.tr('Cerrar'))
        btn_cerrar.clicked.connect(self.close)

        pie.addWidget(btn_importar)
        pie.addStretch(1)
        pie.addWidget(btn_export_json)
        pie.addWidget(btn_export_txt)
        pie.addWidget(btn_cerrar)
        root.addLayout(pie)

    # ------------------------------------------------------------------
    #  Ruta del glosario.json (compartida entre tomos)
    # ------------------------------------------------------------------
    def _resolver_ruta_glosario(self, preguntar_si_falta=True):
        ruta = getattr(pcfg, 'glosario_path', '') or ''
        if ruta and osp.exists(osp.dirname(ruta) or '.'):
            self.mgr.load(ruta)
            self.lbl_ruta.setText(ruta)
            return
        if preguntar_si_falta:
            self.on_cambiar_ruta()
        else:
            self.lbl_ruta.setText(self.tr('(sin configurar — usa "Cambiar carpeta...")'))

    def on_abrir_glosario(self):
        """Selecciona directamente un glosario.json existente (de cualquier
        serie) para visualizarlo/editarlo, sin forzar carpeta ni nombre."""
        carpeta_inicial = ''
        if getattr(pcfg, 'glosario_path', ''):
            carpeta_inicial = osp.dirname(pcfg.glosario_path)
        ruta, _ = QFileDialog.getOpenFileName(
            self, self.tr('Abrir glosario existente'), carpeta_inicial, 'JSON (*.json)')
        if not ruta:
            return
        pcfg.glosario_path = ruta
        try:
            save_config()
        except Exception:
            pass
        self.mgr.load(ruta)
        self.lbl_ruta.setText(ruta)
        self._refrescar_todo()

    def on_cambiar_ruta(self):
        carpeta_inicial = ''
        if getattr(pcfg, 'glosario_path', ''):
            carpeta_inicial = osp.dirname(pcfg.glosario_path)
        elif getattr(self.mainwindow, 'imgtrans_proj', None) and self.mainwindow.imgtrans_proj.proj_path:
            # por defecto, un nivel por encima de la carpeta del tomo actual
            carpeta_inicial = osp.dirname(self.mainwindow.imgtrans_proj.proj_path)

        carpeta = QFileDialog.getExistingDirectory(
            self, self.tr('Selecciona la carpeta de la serie para el glosario'), carpeta_inicial)
        if not carpeta:
            return
        ruta = osp.join(carpeta, 'glosario.json')
        pcfg.glosario_path = ruta
        try:
            save_config()
        except Exception:
            pass
        self.mgr.load(ruta)
        self.lbl_ruta.setText(ruta)
        self._refrescar_todo()

    # ------------------------------------------------------------------
    #  Tabla / filtros
    # ------------------------------------------------------------------
    def _refrescar_todo(self):
        # repoblar combo de tomos sin perder selección
        tomo_actual = self.cb_filtro_tomo.currentText()
        self.cb_filtro_tomo.blockSignals(True)
        self.cb_filtro_tomo.clear()
        self.cb_filtro_tomo.addItem('Todos')
        self.cb_filtro_tomo.addItems(self.mgr.tomos())
        idx = self.cb_filtro_tomo.findText(tomo_actual)
        self.cb_filtro_tomo.setCurrentIndex(idx if idx >= 0 else 0)
        self.cb_filtro_tomo.blockSignals(False)
        self._refrescar_tabla()

    def on_cabecera_clicada(self, col: int):
        if col == self._sort_col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.tabla.horizontalHeader().setSortIndicator(
            col, Qt.AscendingOrder if self._sort_asc else Qt.DescendingOrder)
        self._refrescar_tabla()

    def _ordenar_entradas(self, entradas):
        """Ordena a mano (no con QTableWidget.setSortingEnabled, incompatible
        con los botones incrustados de la columna Apariciones)."""
        if self._sort_col is None:
            return entradas

        def valor(e):
            if self._sort_col == COL_NOMBRE:
                return e.get('nombre', '')
            if self._sort_col == COL_APARICIONES:
                return len(e.get('apariciones', []) or [])
            key = COLUMNAS_DATOS[self._sort_col - 2][0]
            v = e.get(key, '')
            if key in ('pagina', 'globo'):
                try:
                    return int(v)
                except (ValueError, TypeError):
                    pass
            return v

        def clave_comparable(e):
            v = valor(e)
            if isinstance(v, (int, float)):
                return (0, v, '')
            return (1, 0, str(v).lower())

        return sorted(entradas, key=clave_comparable, reverse=not self._sort_asc)

    def _refrescar_tabla(self):
        entradas = self.mgr.filtrar(
            nombre_substr=self.ed_filtro_nombre.text(),
            tipo=self.cb_filtro_tipo.currentText(),
            tomo=self.cb_filtro_tomo.currentText(),
        )
        entradas = self._ordenar_entradas(entradas)
        self.tabla.setRowCount(len(entradas))
        for row, e in enumerate(entradas):
            es_error = e.get('tipo', '') == 'Error'
            entry_id = e.get('id')

            item_nombre = QTableWidgetItem(str(e.get('nombre', '')))
            item_nombre.setData(ID_ROLE, entry_id)
            if es_error:
                f = item_nombre.font()
                f.setBold(True)
                item_nombre.setFont(f)
            self.tabla.setItem(row, COL_NOMBRE, item_nombre)

            n_apariciones = len(e.get('apariciones', []) or [])
            btn = QPushButton(str(n_apariciones) if n_apariciones else '—')
            btn.setToolTip(
                self.tr('Ver las {0} apariciones de "{1}"').format(n_apariciones, e.get('nombre', ''))
                if n_apariciones else
                self.tr('Sin lista de apariciones calculada para esta entrada'))
            btn.setEnabled(n_apariciones > 0)
            btn.setFlat(True)
            btn.setCursor(Qt.PointingHandCursor if n_apariciones else Qt.ArrowCursor)
            btn.clicked.connect(partial(self.on_ver_apariciones_fila, entry_id))
            self.tabla.setCellWidget(row, COL_APARICIONES, btn)

            for offset, (key, _) in enumerate(COLUMNAS_DATOS):
                col = 2 + offset
                item = QTableWidgetItem(str(e.get(key, '')))
                if es_error:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                self.tabla.setItem(row, col, item)

    def on_ver_apariciones_fila(self, entry_id):
        entry = self.mgr.get_entry(entry_id)
        if entry:
            self._mostrar_dialogo_apariciones(entry)

    def _mostrar_dialogo_apariciones(self, entry: dict):
        """Diálogo propio (más grande y con el nombre bien visible en el
        cuerpo, no solo en la barra de título) con la lista de apariciones."""
        apariciones = entry.get('apariciones', []) or []
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr('Apariciones'))
        dlg.resize(480, 600)
        lay = QVBoxLayout(dlg)

        titulo = QLabel(f"<b style='font-size:15px'>{entry.get('nombre', '')}</b>")
        titulo.setWordWrap(True)
        subtitulo = QLabel(self.tr('{0} apariciones en {1}').format(
            len(apariciones), entry.get('tomo', '')))
        subtitulo.setStyleSheet('color: gray;')
        lay.addWidget(titulo)
        lay.addWidget(subtitulo)

        if not apariciones:
            aviso = QLabel(self.tr(
                'Esta entrada no tiene lista de apariciones calculada '
                '(se creó a mano o se generó antes de esta función).'))
            aviso.setWordWrap(True)
            lay.addWidget(aviso)
        else:
            lista = QListWidget()
            for a in apariciones:
                pg, gl = a.split('|', 1)
                lista.addItem(self.tr('Página {0}   ·   Globo {1}').format(pg, gl))
            lay.addWidget(lista, 1)

            ayuda = QLabel(self.tr(
                'Selecciona una aparición y pulsa "Usar como nueva entrada" para crear '
                'una entrada nueva en esa página/globo, con el mismo nombre/tipo/tomo y '
                'conservando esta misma lista de apariciones (útil para corregir dónde '
                'apunta un evento sin perder la lista ya calculada).'))
            ayuda.setWordWrap(True)
            ayuda.setStyleSheet('color: gray; font-size: 11px;')
            lay.addWidget(ayuda)

            fila_clonar = QHBoxLayout()
            btn_usar = QPushButton(self.tr('Usar como nueva entrada'))
            btn_usar.setEnabled(False)
            lista.itemSelectionChanged.connect(
                lambda: btn_usar.setEnabled(bool(lista.selectedItems())))

            def _clonar():
                fila = lista.currentRow()
                if fila < 0:
                    return
                pg, gl = apariciones[fila].split('|', 1)
                self._preparar_nueva_entrada_desde(entry, pg, gl)
                dlg.accept()

            btn_usar.clicked.connect(_clonar)
            fila_clonar.addStretch(1)
            fila_clonar.addWidget(btn_usar)
            lay.addLayout(fila_clonar)

        fila_botones = QHBoxLayout()
        fila_botones.addStretch(1)
        btn_ok = QPushButton(self.tr('Cerrar'))
        btn_ok.clicked.connect(dlg.accept)
        fila_botones.addWidget(btn_ok)
        lay.addLayout(fila_botones)

        dlg.exec()

    def _on_seleccion_tabla(self):
        filas = self.tabla.selectionModel().selectedRows()
        n = len(filas)
        self.lbl_seleccion.setText(self.tr('{0} seleccionadas').format(n))
        self.btn_eliminar_seleccion.setEnabled(n > 0)
        if n == 1:
            entry_id = self.tabla.item(filas[0].row(), COL_NOMBRE).data(ID_ROLE)
            entry = self.mgr.get_entry(entry_id)
            if entry:
                self._cargar_formulario(entry)
        else:
            # varias filas (o ninguna) seleccionadas: el formulario de edición
            # individual no aplica, solo queda disponible "Eliminar seleccionadas"
            self._entry_actual_id = None

    def on_seleccionar_todo_filtrado(self):
        self.tabla.selectAll()

    # ------------------------------------------------------------------
    #  Formulario
    # ------------------------------------------------------------------
    def _cargar_formulario(self, entry: dict):
        self._entry_actual_id = entry.get('id')
        self._apariciones_pendientes = None
        self.lbl_pendientes.setText('')
        self.ed_nombre.setText(entry.get('nombre', ''))
        self.cb_tipo.setCurrentText(entry.get('tipo', ''))
        self.ed_tomo.setText(entry.get('tomo', ''))
        self.ed_pagina.setText(entry.get('pagina', ''))
        self.ed_globo.setText(entry.get('globo', ''))
        self.ed_nota.setText(entry.get('nota', ''))
        self.btn_anadir_aparicion.setEnabled(True)

    def _limpiar_formulario(self):
        self._entry_actual_id = None
        self._apariciones_pendientes = None
        self.lbl_pendientes.setText('')
        self.ed_nombre.clear()
        self.cb_tipo.setCurrentIndex(0)
        # el tomo por defecto es el tomo activo en el proyecto, si existe
        tomo_defecto = ''
        proj = getattr(self.mainwindow, 'imgtrans_proj', None)
        if proj and proj.proj_path:
            tomo_defecto = osp.basename(proj.proj_path.rstrip('/\\'))
        self.ed_tomo.setText(tomo_defecto)
        self.ed_pagina.clear()
        self.ed_globo.clear()
        self.ed_nota.clear()
        self.btn_anadir_aparicion.setEnabled(False)
        self.tabla.clearSelection()

    def on_nueva_entrada(self):
        self._limpiar_formulario()
        self.ed_nombre.setFocus()

    def _preparar_nueva_entrada_desde(self, entry: dict, pagina: str, globo: str):
        """Rellena el formulario para crear una entrada nueva en (pagina, globo),
        con el mismo nombre/tipo/tomo que `entry` y conservando su lista de
        apariciones (se adjunta al guardar). La nota se deja vacía a propósito."""
        self._entry_actual_id = None
        self._apariciones_pendientes = list(entry.get('apariciones', []) or [])
        self.ed_nombre.setText(entry.get('nombre', ''))
        self.cb_tipo.setCurrentText(entry.get('tipo', ''))
        self.ed_tomo.setText(entry.get('tomo', ''))
        self.ed_pagina.setText(pagina)
        self.ed_globo.setText(globo)
        self.ed_nota.clear()
        self.ed_nota.setFocus()
        self.btn_anadir_aparicion.setEnabled(False)
        if self._apariciones_pendientes:
            self.lbl_pendientes.setText(
                self.tr('Se guardará como entrada nueva; se le adjuntará la misma lista '
                        'de {0} apariciones al pulsar "Guardar entrada".').format(
                    len(self._apariciones_pendientes)))
        else:
            self.lbl_pendientes.setText('')
        self.tabla.clearSelection()

    def on_anadir_aparicion(self):
        if not self._entry_actual_id:
            QMessageBox.warning(
                self, self.tr('Aviso'),
                self.tr('Primero selecciona (o guarda) una entrada existente.'))
            return
        entry = self.mgr.get_entry(self._entry_actual_id)
        if not entry:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr('Añadir aparición manual'))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"<b>{entry.get('nombre', '')}</b>"))
        form = QFormLayout()
        ed_pagina = QLineEdit()
        ed_globo = QLineEdit()
        form.addRow(self.tr('Página:'), ed_pagina)
        form.addRow(self.tr('Globo:'), ed_globo)
        lay.addLayout(form)
        fila_botones = QHBoxLayout()
        btn_cancelar = QPushButton(self.tr('Cancelar'))
        btn_cancelar.clicked.connect(dlg.reject)
        btn_anadir = QPushButton(self.tr('Añadir'))
        btn_anadir.setDefault(True)
        btn_anadir.clicked.connect(dlg.accept)
        fila_botones.addStretch(1)
        fila_botones.addWidget(btn_cancelar)
        fila_botones.addWidget(btn_anadir)
        lay.addLayout(fila_botones)
        ed_pagina.setFocus()

        if dlg.exec() != QDialog.Accepted:
            return

        pagina = ed_pagina.text().strip()
        globo = ed_globo.text().strip()
        if not pagina or not globo:
            QMessageBox.warning(self, self.tr('Aviso'), self.tr('Indica página y globo.'))
            return

        nueva = f'{pagina}|{globo}'
        apariciones = list(entry.get('apariciones', []) or [])
        if nueva in apariciones:
            QMessageBox.information(
                self, self.tr('Ya existe'),
                self.tr('Esa página/globo ya estaba en la lista de apariciones.'))
            return
        apariciones.append(nueva)

        def _clave_orden(a):
            p, g = a.split('|', 1)
            try:
                return (int(p), int(g))
            except ValueError:
                return (p, g)
        apariciones.sort(key=_clave_orden)

        entry_actualizada = dict(entry)
        entry_actualizada['apariciones'] = apariciones
        self.mgr.update_entry(self._entry_actual_id, entry_actualizada)
        self._refrescar_todo()
        QMessageBox.information(
            self, self.tr('Añadida'),
            self.tr('Aparición añadida. Ahora hay {0} en total.').format(len(apariciones)))

    def on_guardar_entrada(self):
        nombre = self.ed_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, self.tr('Aviso'), self.tr('El nombre no puede estar vacío.'))
            return
        entry = {
            'nombre': nombre,
            'tipo': self.cb_tipo.currentText().strip() or 'Otro',
            'tomo': self.ed_tomo.text().strip(),
            'pagina': self.ed_pagina.text().strip(),
            'globo': self.ed_globo.text().strip(),
            'nota': self.ed_nota.text().strip(),
        }
        # si ya existía y tenía lista de apariciones calculada, la conservamos
        # (el formulario de edición manual no la toca)
        if self._entry_actual_id:
            previa = self.mgr.get_entry(self._entry_actual_id)
            if previa and previa.get('apariciones'):
                entry['apariciones'] = previa['apariciones']
            self.mgr.update_entry(self._entry_actual_id, entry)
        else:
            # entrada nueva: si viene de "Usar como nueva entrada" en el
            # diálogo de apariciones, se le adjunta esa misma lista
            if self._apariciones_pendientes:
                entry['apariciones'] = self._apariciones_pendientes
            self._entry_actual_id = self.mgr.add_entry(entry)
        self._apariciones_pendientes = None
        self.lbl_pendientes.setText('')
        self._refrescar_todo()
        self.glosario_actualizado.emit()

    def on_eliminar_entrada(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return
        ids = [self.tabla.item(f.row(), COL_NOMBRE).data(ID_ROLE) for f in filas]
        n = len(ids)
        texto = (self.tr('¿Eliminar esta entrada del glosario?') if n == 1 else
                 self.tr('¿Eliminar estas {0} entradas del glosario?').format(n))
        resp = QMessageBox.question(self, self.tr('Confirmar'), texto)
        if resp != QMessageBox.Yes:
            return
        self.mgr.delete_entries(ids)
        self._limpiar_formulario()
        self._refrescar_todo()
        self.glosario_actualizado.emit()

    # ------------------------------------------------------------------
    #  Importar tomo
    # ------------------------------------------------------------------
    def on_importar_tomo(self):
        if not self.mgr.path:
            QMessageBox.warning(self, self.tr('Aviso'),
                                 self.tr('Configura antes la carpeta del glosario ("Cambiar carpeta...").'))
            return
        ruta, _ = QFileDialog.getOpenFileName(
            self, self.tr('Selecciona glosario_TomoXX_import.json'), '', 'JSON (*.json)')
        if not ruta:
            return
        try:
            añadidas, omitidas, conflictos = self.mgr.import_tomo_file(ruta)
        except Exception as e:
            QMessageBox.critical(self, self.tr('Error'), self.tr('No se pudo importar: ') + str(e))
            return

        mensaje = self.tr('Entradas añadidas: {0}\nDuplicadas omitidas: {1}').format(añadidas, omitidas)
        if conflictos:
            mensaje += '\n\n' + self.tr(
                '⚠ {0} página(s)/globo(s) con más de un nombre distinto — '
                'puede ser una corrección pendiente de limpiar (p. ej. un nombre '
                'reemplazado por otro) o dos personajes que comparten legítimamente '
                'el mismo globo. Revísalas y borra la que sobre si hace falta:'
            ).format(len(conflictos))
            for tomo, pagina, globo, nombres in conflictos[:15]:
                mensaje += f"\n  · pág.{pagina} · globo {globo}: {', '.join(nombres)}"
            if len(conflictos) > 15:
                mensaje += self.tr('\n  · ... y {0} más').format(len(conflictos) - 15)

        QMessageBox.information(self, self.tr('Importación completada'), mensaje)
        self._refrescar_todo()
        self.glosario_actualizado.emit()

    # ------------------------------------------------------------------
    #  Exportar
    # ------------------------------------------------------------------
    def _entradas_para_exportar(self):
        # exporta según el filtro activo, para permitir exportar solo un tomo/tipo si se desea
        return self.mgr.filtrar(
            nombre_substr=self.ed_filtro_nombre.text(),
            tipo=self.cb_filtro_tipo.currentText(),
            tomo=self.cb_filtro_tomo.currentText(),
        )

    def on_exportar_json_import(self):
        """Regenera un fichero en el mismo formato que se usa para importar
        (glosario_TomoXX_import.json / glosario_Serie_import.json), a partir
        de las entradas actualmente filtradas. Útil para volver a compartir
        el glosario tras editarlo a mano dentro del panel.

        De momento solo hay dos modalidades, según el filtro de Tomo activo:
          - un tomo concreto  -> glosario_<Tomo>_import.json
          - "Todos"           -> glosario_Serie_import.json
        """
        tomo_sel = self.cb_filtro_tomo.currentText()
        if tomo_sel and tomo_sel != 'Todos':
            nombre_sugerido = f'glosario_{tomo_sel}_import.json'
            valor_tomo = tomo_sel
            mensaje = self.tr(
                "Vas a exportar solo el tomo '{0}' en formato de importación "
                "({1}).\n\n¿Continuar?").format(tomo_sel, nombre_sugerido)
        else:
            nombre_sugerido = 'glosario_Serie_import.json'
            valor_tomo = 'Serie'
            mensaje = self.tr(
                "No hay un tomo concreto filtrado, así que se exportará TODA "
                "la serie en formato de importación ({0}).\n\n¿Continuar?").format(nombre_sugerido)

        resp = QMessageBox.question(self, self.tr('Confirmar exportación'), mensaje)
        if resp != QMessageBox.Yes:
            return

        ruta, _ = QFileDialog.getSaveFileName(
            self, self.tr('Exportar glosario (formato import)'), nombre_sugerido, 'JSON (*.json)')
        if not ruta:
            return

        entradas = self._entradas_para_exportar()
        campos = ('nombre', 'tipo', 'tomo', 'pagina', 'globo', 'nota')
        def _a_dict(e):
            d = {k: e.get(k, '') for k in campos}
            if e.get('apariciones'):
                d['apariciones'] = e['apariciones']
            return d
        payload = {
            'tomo': valor_tomo,
            'entradas': [_a_dict(e) for e in entradas],
        }
        with open(ruta, 'w', encoding='utf8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        QMessageBox.information(
            self, self.tr('Listo'),
            self.tr('Glosario exportado: {0} entradas.').format(len(entradas)))

    def on_exportar_txt(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, self.tr('Exportar glosario a TXT'), 'glosario.txt', 'Texto (*.txt)')
        if not ruta:
            return
        entradas = self._entradas_para_exportar()
        lineas = [self.tr('GLOSARIO DE LA SERIE'), '=' * 40, '']
        actual_tipo = None
        for e in entradas:
            if e.get('tipo') != actual_tipo:
                actual_tipo = e.get('tipo')
                lineas.append('')
                lineas.append(f"-- {actual_tipo} --")
            nota = f" ({e.get('nota')})" if e.get('nota') else ''
            linea = (f"{e.get('nombre')}  [{e.get('tomo')} · pág.{e.get('pagina')} · "
                      f"globo {e.get('globo')}]{nota}")
            if e.get('tipo') == 'Error':
                linea = f"++{linea}++"
            lineas.append(linea)
        with open(ruta, 'w', encoding='utf8') as f:
            f.write('\n'.join(lineas))
        QMessageBox.information(self, self.tr('Listo'), self.tr('Glosario exportado a TXT.'))
