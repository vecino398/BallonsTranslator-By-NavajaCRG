"""
exportacion_panel.py — Panel PS Exportar / Importar
=====================================================
Diálogo integrado con dos pestañas:

  EXPORTAR  BT → TXT
    • Página activa / Todas
    • Qué: Traducción (Tradu.txt) / OCR (OCRTradu.txt) / Ambos
    • Página activa → panel de verificación integrado antes de confirmar
    • Todas         → operación silenciosa (mensaje OK o error detallado)

  IMPORTAR  TXT → BT
    • Página activa / Todas
    • Qué: Traducción (Tradu.txt) / OCR (OCRTradu.txt) / Ambos
    • Página activa → panel de verificación integrado antes de confirmar
    • Todas         → operación silenciosa

Correspondencia de columnas:
    BT-Español  ↔  Tradu.txt
    BT-Francés  ↔  OCRTradu.txt

Panel de verificación (modo página activa):
    • Columna izquierda  = ORIGEN  (fuente de la operación)
    • Columna derecha    = DESTINO (donde va a acabar el dato)
    • Numeración de globos: 01, 02, 03 …
    • Solo lectura — el usuario revisa, luego Confirmar o Cancelar
    • Navegación ◀ Anterior / Siguiente ▶ entre páginas (solo verificación)
"""

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QSizePolicy, QTabWidget,
    QWidget, QFrame, QSplitter, QScrollArea, QGridLayout,
    QStackedWidget, QMessageBox
)
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QFont


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _separador():
    """Línea horizontal de separación."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFrameShadow(QFrame.Shadow.Sunken)
    return f


def _label_gris(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet("color: gray; font-size: 11px;")
    lbl.setWordWrap(True)
    return lbl


def _label_bold(texto: str) -> QLabel:
    lbl = QLabel(texto)
    f = QFont(); f.setBold(True)
    lbl.setFont(f)
    return lbl


# ══════════════════════════════════════════════════════════════════════════════
#  Panel de verificación (vista integrada, columnas solo-lectura)
# ══════════════════════════════════════════════════════════════════════════════

class _VerificacionWidget(QWidget):
    """
    Vista de dos columnas (solo lectura) para revisar lo que va a ocurrir
    antes de confirmar la operación en modo 'página activa'.

    Señales:
        confirmado()  — el usuario pulsó Confirmar
        cancelado()   — el usuario pulsó Cancelar / Volver
        pag_anterior() / pag_siguiente() — navegar a otra página
    """

    confirmado   = Signal()
    cancelado    = Signal()
    pag_anterior = Signal()
    pag_siguiente = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # Cabecera
        hdr = QHBoxLayout()
        self.lblTitulo = _label_bold("")
        hdr.addWidget(self.lblTitulo)
        hdr.addStretch()
        self.lblPagina = QLabel("")
        self.lblPagina.setStyleSheet("color: gray; font-size: 11px;")
        hdr.addWidget(self.lblPagina)
        root.addLayout(hdr)

        self.lblAviso = _label_gris("")
        root.addWidget(self.lblAviso)

        # Cabeceras de columnas
        col_hdr = QHBoxLayout()
        col_hdr.setContentsMargins(0, 0, 0, 0)
        self.lblColIzq = _label_bold("Origen")
        self.lblColDer = _label_bold("Destino")
        self.lblColIzq.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblColDer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col_hdr.addWidget(self.lblColIzq, 1)
        col_hdr.addWidget(self.lblColDer, 1)
        root.addLayout(col_hdr)

        # Área de globos con scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._contenedor = QWidget()
        self._grid = QGridLayout(self._contenedor)
        self._grid.setSpacing(2)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 1)
        scroll.setWidget(self._contenedor)
        root.addWidget(scroll, stretch=1)

        root.addWidget(_separador())

        # Barra de botones
        bar = QHBoxLayout()
        self.btnAnterior = QPushButton("◀  Anterior")
        self.btnAnterior.setToolTip("Ir a la página anterior")
        self.btnAnterior.clicked.connect(self.pag_anterior)

        self.btnSiguiente = QPushButton("Siguiente  ▶")
        self.btnSiguiente.setToolTip("Ir a la página siguiente")
        self.btnSiguiente.clicked.connect(self.pag_siguiente)

        self.btnCancelar = QPushButton("✕  Cancelar")
        self.btnCancelar.clicked.connect(self.cancelado)

        self.btnConfirmar = QPushButton("✓  Confirmar")
        self.btnConfirmar.setDefault(True)
        self.btnConfirmar.clicked.connect(self.confirmado)

        bar.addWidget(self.btnAnterior)
        bar.addWidget(self.btnSiguiente)
        bar.addStretch()
        bar.addWidget(self.btnCancelar)
        bar.addWidget(self.btnConfirmar)
        root.addLayout(bar)

    def cargar(self, titulo: str, aviso: str,
               col_izq: str, col_der: str,
               filas: list,
               nombre_pagina: str = "",
               btn_anterior: bool = True,
               btn_siguiente: bool = True):
        """
        titulo        — texto en negrita arriba
        aviso         — texto gris descriptivo
        col_izq/der   — etiquetas de columna
        filas         — lista de (num_globo_str, texto_izq, texto_der)
        nombre_pagina — texto en la esquina derecha del header
        btn_anterior/siguiente — habilitar/deshabilitar navegación
        """
        self.lblTitulo.setText(titulo)
        self.lblAviso.setText(aviso)
        self.lblColIzq.setText(col_izq)
        self.lblColDer.setText(col_der)
        self.lblPagina.setText(nombre_pagina)
        self.btnAnterior.setEnabled(btn_anterior)
        self.btnSiguiente.setEnabled(btn_siguiente)

        # Limpiar grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Cabecera de columnas en el grid
        for col, txt in enumerate(["#", col_izq, col_der]):
            lbl = QLabel(f"<b>{txt}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("border-bottom: 1px solid #888; padding: 2px;")
            self._grid.addWidget(lbl, 0, col)

        for fila_idx, (num, izq, der) in enumerate(filas, start=1):
            # Número de globo
            lbl_num = QLabel(f"<b>{num}</b>")
            lbl_num.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            lbl_num.setStyleSheet("color: gray; padding: 3px 4px;")

            # Columna izquierda
            lbl_izq = QLabel(izq or "<i style='color:gray'>[vacío]</i>")
            lbl_izq.setWordWrap(True)
            lbl_izq.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            lbl_izq.setStyleSheet(
                "border: 1px solid #444; border-radius: 3px; padding: 3px 5px; "
                "background: transparent;"
            )

            # Columna derecha
            lbl_der = QLabel(der or "<i style='color:gray'>[vacío]</i>")
            lbl_der.setWordWrap(True)
            lbl_der.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            lbl_der.setStyleSheet(
                "border: 1px solid #444; border-radius: 3px; padding: 3px 5px; "
                "background: transparent;"
            )
            lbl_der.setTextFormat(Qt.TextFormat.RichText)
            lbl_izq.setTextFormat(Qt.TextFormat.RichText)

            self._grid.addWidget(lbl_num, fila_idx, 0)
            self._grid.addWidget(lbl_izq, fila_idx, 1)
            self._grid.addWidget(lbl_der, fila_idx, 2)


# ══════════════════════════════════════════════════════════════════════════════
#  Widget de opciones (compartido entre Exportar e Importar)
# ══════════════════════════════════════════════════════════════════════════════

class _OpcionesWidget(QWidget):
    """Radios de Alcance + Qué + botón Ejecutar / Verificar."""

    accion_solicitada = Signal(str, str)   # (alcance, que)
    # alcance: 'actual' | 'todas'
    # que:     'trad' | 'ocr' | 'ambos'

    def __init__(self, modo: str, parent=None):
        """modo: 'exportar' | 'importar'"""
        super().__init__(parent)
        self._modo = modo
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ── Alcance ──────────────────────────────────────────────────────
        root.addWidget(_label_bold("Alcance"))

        self._grp_alcance = QButtonGroup(self)
        self.radioActual = QRadioButton("Solo la página activa")
        self.radioTodas  = QRadioButton("Todas las páginas del proyecto")
        self.radioActual.setChecked(True)
        self._grp_alcance.addButton(self.radioActual)
        self._grp_alcance.addButton(self.radioTodas)

        if self._modo == 'exportar':
            self.radioActual.setToolTip(
                "Muestra un panel de verificación antes de exportar la página activa."
            )
            self.radioTodas.setToolTip(
                "Exporta todas las páginas directamente sin verificación."
            )
        else:
            self.radioActual.setToolTip(
                "Muestra un panel de verificación antes de importar a la página activa."
            )
            self.radioTodas.setToolTip(
                "Importa todas las páginas directamente sin verificación."
            )

        root.addWidget(self.radioActual)
        root.addWidget(self.radioTodas)

        root.addWidget(_separador())

        # ── Qué ──────────────────────────────────────────────────────────
        if self._modo == 'exportar':
            root.addWidget(_label_bold("Exportar"))
            lbl_trad  = "Traducción   BT-Español  →  Tradu.txt"
            lbl_ocr   = "OCR            BT-Francés  →  OCRTradu.txt"
            lbl_ambos = "Ambos"
        else:
            root.addWidget(_label_bold("Importar"))
            lbl_trad  = "Traducción   Tradu.txt  →  BT-Español"
            lbl_ocr   = "OCR            OCRTradu.txt  →  BT-Francés"
            lbl_ambos = "Ambos"

        self._grp_que = QButtonGroup(self)
        self.radioTrad  = QRadioButton(lbl_trad)
        self.radioOCR   = QRadioButton(lbl_ocr)
        self.radioAmbos = QRadioButton(lbl_ambos)
        self.radioTrad.setChecked(True)
        for r in (self.radioTrad, self.radioOCR, self.radioAmbos):
            self._grp_que.addButton(r)
            root.addWidget(r)

        root.addWidget(_separador())

        # ── Aviso ─────────────────────────────────────────────────────────
        if self._modo == 'exportar':
            aviso = (
                "Página activa: abre panel de verificación.\n"
                "Todas las páginas: exporta directamente (OK o error detallado)."
            )
        else:
            aviso = (
                "Página activa: abre panel de verificación.\n"
                "Todas las páginas: importa directamente (OK o error detallado)."
            )
        root.addWidget(_label_gris(aviso))
        root.addStretch()

        # ── Botón principal ───────────────────────────────────────────────
        self.btnEjecutar = QPushButton(
            "🔍  Verificar…" if self._modo == 'exportar' else "🔍  Verificar…"
        )
        self.btnEjecutar.setDefault(True)
        self.btnEjecutar.clicked.connect(self._on_ejecutar)
        root.addWidget(self.btnEjecutar)

        # Actualizar etiqueta del botón según radios
        self.radioActual.toggled.connect(self._actualizar_btn)
        self.radioTodas.toggled.connect(self._actualizar_btn)
        self._actualizar_btn()

    def _actualizar_btn(self):
        if self.radioActual.isChecked():
            self.btnEjecutar.setText(
                "🔍  Verificar página…" if self._modo == 'exportar'
                else "🔍  Verificar página…"
            )
        else:
            self.btnEjecutar.setText(
                "⬆  Exportar todas" if self._modo == 'exportar'
                else "⬇  Importar todas"
            )

    def _on_ejecutar(self):
        alcance = 'actual' if self.radioActual.isChecked() else 'todas'
        if self.radioTrad.isChecked():
            que = 'trad'
        elif self.radioOCR.isChecked():
            que = 'ocr'
        else:
            que = 'ambos'
        self.accion_solicitada.emit(alcance, que)


# ══════════════════════════════════════════════════════════════════════════════
#  Panel principal
# ══════════════════════════════════════════════════════════════════════════════

class ExportacionPanel(QDialog):
    """
    Diálogo PS — Exportar / Importar.

    Señal export_requested(modo) para compatibilidad con mainwindow.py:
      modo = 'actual' | 'todas' | 'importar'   (legado)

    Internamente emite export_ps(alcance, que) e import_ps(alcance, que)
    que mainwindow.py puede conectar para la nueva lógica.
    """

    export_requested = Signal(str)   # compatibilidad legado
    export_ps = Signal(str, str)     # (alcance, que)  exportar
    import_ps = Signal(str, str)     # (alcance, que)  importar

    # Datos para el panel de verificación de la página activa
    # Se rellenan desde mainwindow.py antes de mostrar la verificación
    _datos_verificacion: dict = None   # {'filas': [...], 'pagina': str, ...}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("PS — Exportar / Importar"))
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(680, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Página activa (se actualiza desde mainwindow.py)
        self._nombre_pagina = ""
        self._paginas_lista: list = []   # lista completa de páginas
        self._idx_pag_verif: int  = 0    # índice en _paginas_lista para la verificación

        # Pendiente de confirmar: ('exportar'|'importar', alcance, que)
        self._pendiente = None

        self._build_ui()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # ── Label página activa ───────────────────────────────────────────
        self.lblPaginaActiva = _label_gris("")
        root.addWidget(self.lblPaginaActiva)

        # ── QStackedWidget: 0=opciones, 1=verificación ───────────────────
        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # ── Página 0: pestañas Exportar / Importar ───────────────────────
        self._tabs_widget = QWidget()
        tabs_layout = QVBoxLayout(self._tabs_widget)
        tabs_layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()

        # Pestaña Exportar
        self._wExportar = _OpcionesWidget('exportar')
        self._wExportar.accion_solicitada.connect(
            lambda a, q: self._on_accion('exportar', a, q)
        )
        self._tabs.addTab(self._wExportar, "⬆  Exportar  BT → TXT")

        # Pestaña Importar
        self._wImportar = _OpcionesWidget('importar')
        self._wImportar.accion_solicitada.connect(
            lambda a, q: self._on_accion('importar', a, q)
        )
        self._tabs.addTab(self._wImportar, "⬇  Importar  TXT → BT")

        tabs_layout.addWidget(self._tabs)

        # Botón cerrar en la vista de opciones
        bar_cerrar = QHBoxLayout()
        bar_cerrar.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.close)
        bar_cerrar.addWidget(btn_cerrar)
        tabs_layout.addLayout(bar_cerrar)

        self._stack.addWidget(self._tabs_widget)

        # ── Página 1: verificación ────────────────────────────────────────
        self._wVerif = _VerificacionWidget()
        self._wVerif.confirmado.connect(self._on_confirmar)
        self._wVerif.cancelado.connect(self._volver_a_opciones)
        self._wVerif.pag_anterior.connect(self._verif_pag_anterior)
        self._wVerif.pag_siguiente.connect(self._verif_pag_siguiente)
        self._stack.addWidget(self._wVerif)

    # -------------------------------------------------------- actualización --

    def set_pagina_activa(self, nombre_pagina: str):
        self._nombre_pagina = nombre_pagina
        self.lblPaginaActiva.setText(
            self.tr("Página activa: ") + (nombre_pagina or "—")
        )

    def set_paginas_lista(self, lista: list):
        """Recibe la lista completa de páginas del proyecto."""
        self._paginas_lista = list(lista)

    # -------------------------------------------------------- lógica acciones --

    def _on_accion(self, modo: str, alcance: str, que: str):
        """Dispatcher principal: verificar o ejecutar directo."""
        self._pendiente = (modo, alcance, que)

        if alcance == 'todas':
            # Directo sin verificación
            if modo == 'exportar':
                self.export_ps.emit(alcance, que)
                # Compatibilidad legado
                self.export_requested.emit('todas' if que != 'importar' else 'todas')
            else:
                self.import_ps.emit(alcance, que)
                self.export_requested.emit('importar')
        else:
            # Página activa → pedir datos al padre y mostrar verificación
            self._idx_pag_verif = self._paginas_lista.index(self._nombre_pagina) \
                if self._nombre_pagina in self._paginas_lista else 0
            self._mostrar_verificacion(modo, que, self._nombre_pagina)

    def _mostrar_verificacion(self, modo: str, que: str, pagina: str):
        """Pide al padre los datos de verificación y muestra la vista."""
        # Emitir señal para que mainwindow.py provea los datos
        self.export_ps.emit('verificar_' + modo, que + '|' + pagina)

    def cargar_datos_verificacion(self, titulo: str, aviso: str,
                                   col_izq: str, col_der: str,
                                   filas: list, pagina: str):
        """
        Llamado desde mainwindow.py con los datos calculados para la verificación.
        filas = [(num_str, texto_izq, texto_der), ...]
        """
        # Actualizar _nombre_pagina para que los botones ◀/▶ calculen
        # el índice correcto en _paginas_lista al navegar entre páginas.
        self._nombre_pagina = pagina

        idx = self._paginas_lista.index(pagina) if pagina in self._paginas_lista else 0
        total = len(self._paginas_lista)

        self._wVerif.cargar(
            titulo=titulo, aviso=aviso,
            col_izq=col_izq, col_der=col_der,
            filas=filas, nombre_pagina=pagina,
            btn_anterior=(idx > 0),
            btn_siguiente=(idx < total - 1)
        )
        self._stack.setCurrentIndex(1)

    def _volver_a_opciones(self):
        self._pendiente = None
        self._stack.setCurrentIndex(0)

    def _on_confirmar(self):
        if self._pendiente is None:
            return
        modo, alcance, que = self._pendiente
        self._volver_a_opciones()
        if modo == 'exportar':
            self.export_ps.emit('actual_confirmar', que)
            self.export_requested.emit('actual')
        else:
            self.import_ps.emit('actual_confirmar', que)
            self.export_requested.emit('importar')

    def _verif_pag_anterior(self):
        if not self._pendiente or not self._paginas_lista:
            return
        modo, _, que = self._pendiente
        idx = self._paginas_lista.index(self._nombre_pagina) \
            if self._nombre_pagina in self._paginas_lista else 0
        if idx > 0:
            nueva = self._paginas_lista[idx - 1]
            self._pendiente = (modo, 'actual', que)
            # Pedir al padre que navegue y recargue datos
            self.export_ps.emit('navegar_verif', f'{modo}|{que}|{nueva}')

    def _verif_pag_siguiente(self):
        if not self._pendiente or not self._paginas_lista:
            return
        modo, _, que = self._pendiente
        idx = self._paginas_lista.index(self._nombre_pagina) \
            if self._nombre_pagina in self._paginas_lista else 0
        if idx < len(self._paginas_lista) - 1:
            nueva = self._paginas_lista[idx + 1]
            self._pendiente = (modo, 'actual', que)
            self.export_ps.emit('navegar_verif', f'{modo}|{que}|{nueva}')
