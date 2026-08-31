"""
translation_panel.py  —  Panel TP (Traducción Página)
======================================================
Ventana flotante con dos columnas editables en paralelo:
  - Original    → QPlainTextEdit (editable, una línea por globo)
  - Traducción  → QPlainTextEdit (editable, una línea por globo)

Flujo de trabajo:
  1. Abre el panel  → se carga la página activa
  2. Copia la columna que quieras → pégala en traductor externo
  3. Pega el resultado de vuelta → cada línea vuelve a su globo
  4. Guardar → aplica Original y Traducción al canvas y al JSON

Navegación de página: botones ◀ Anterior / Siguiente ▶
"""

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QSizePolicy, QShortcut, QSplitter, QFrame,
    QTextEdit
)
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QKeySequence, QFont, QColor, QTextCursor, QTextFormat


# Paleta de colores suaves para diferenciar cada línea/globo.
# Se cicla si hay más líneas que colores.
LINE_PALETTE = [
    QColor(255, 225, 180, 110),   # melocotón
    QColor(190, 225, 255, 110),   # celeste
    QColor(200, 255, 195, 110),   # verde claro
    QColor(255, 200, 235, 110),   # rosa
    QColor(220, 200, 255, 110),   # lila
    QColor(255, 250, 180, 110),   # amarillo suave
    QColor(200, 245, 245, 110),   # turquesa claro
]


class TranslationPagePanel(QDialog):
    """
    Panel flotante TP — dos QPlainTextEdit en paralelo.
    Original (izquierda) | Traducción (derecha)
    Cada línea = un globo.
    """

    translations_saved = Signal(list)
    page_prev_requested = Signal()
    page_next_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("TP — Traducción de Página"))
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(960, 640)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._blkitems    = []
        self._pairwidgets = []

        self._build_ui()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Cabecera: nombre de página + conteo de globos ──────────────────
        hdr = QHBoxLayout()
        self.lblPagina = QLabel("")
        font_bold = QFont()
        font_bold.setBold(True)
        self.lblPagina.setFont(font_bold)
        hdr.addWidget(self.lblPagina)
        hdr.addStretch()

        # Botones de navegación de página
        self.btnAnterior = QPushButton(self.tr("◀  Anterior"))
        self.btnAnterior.setToolTip(self.tr("Guardar y pasar a la página anterior"))
        self.btnAnterior.clicked.connect(self._on_anterior)

        self.btnSiguiente = QPushButton(self.tr("Siguiente  ▶"))
        self.btnSiguiente.setToolTip(self.tr("Guardar y pasar a la página siguiente"))
        self.btnSiguiente.clicked.connect(self._on_siguiente)

        hdr.addWidget(self.btnAnterior)
        hdr.addWidget(self.btnSiguiente)
        root.addLayout(hdr)

        # ── Aviso de uso ────────────────────────────────────────────────────
        aviso = QLabel(self.tr(
            "Cada línea = un globo.  "
            "Copia toda la columna, tradúcela externamente y pega el resultado de vuelta."
        ))
        aviso.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(aviso)

        # ── Splitter con las dos columnas ───────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Columna Original
        frameOrig = QFrame()
        frameOrig.setFrameShape(QFrame.Shape.StyledPanel)
        loOrig = QVBoxLayout(frameOrig)
        loOrig.setContentsMargins(4, 4, 4, 4)
        loOrig.setSpacing(3)

        lblOrig = QLabel(self.tr("Original"))
        lblOrig.setFont(font_bold)
        lblOrig.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loOrig.addWidget(lblOrig)

        self.txtOriginal = QPlainTextEdit()
        self.txtOriginal.setPlaceholderText(
            self.tr("Texto original — una línea por globo")
        )
        # Fuente monoespaciada para alinear visualmente las líneas
        fmono = QFont("Courier New", 10)
        self.txtOriginal.setFont(fmono)
        self.txtOriginal.blockCountChanged.connect(self._colorear_lineas)
        loOrig.addWidget(self.txtOriginal)

        # Botón copiar columna original
        self.btnCopiarOrig = QPushButton(self.tr("⎘  Copiar todo"))
        self.btnCopiarOrig.setToolTip(self.tr("Copia el texto original al portapapeles"))
        self.btnCopiarOrig.clicked.connect(
            lambda: self._copiar_columna(self.txtOriginal)
        )
        loOrig.addWidget(self.btnCopiarOrig)

        splitter.addWidget(frameOrig)

        # Columna Traducción
        frameTrad = QFrame()
        frameTrad.setFrameShape(QFrame.Shape.StyledPanel)
        loTrad = QVBoxLayout(frameTrad)
        loTrad.setContentsMargins(4, 4, 4, 4)
        loTrad.setSpacing(3)

        lblTrad = QLabel(self.tr("Traducción"))
        lblTrad.setFont(font_bold)
        lblTrad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loTrad.addWidget(lblTrad)

        self.txtTraduccion = QPlainTextEdit()
        self.txtTraduccion.setPlaceholderText(
            self.tr("Traducción — pega aquí el bloque traducido (una línea por globo)")
        )
        self.txtTraduccion.setFont(fmono)
        self.txtTraduccion.blockCountChanged.connect(self._colorear_lineas)
        loTrad.addWidget(self.txtTraduccion)

        # Botón copiar columna traducción
        self.btnCopiarTrad = QPushButton(self.tr("⎘  Copiar todo"))
        self.btnCopiarTrad.setToolTip(self.tr("Copia la traducción al portapapeles"))
        self.btnCopiarTrad.clicked.connect(
            lambda: self._copiar_columna(self.txtTraduccion)
        )
        loTrad.addWidget(self.btnCopiarTrad)

        splitter.addWidget(frameTrad)
        splitter.setSizes([480, 480])
        root.addWidget(splitter, stretch=1)

        # ── Barra inferior: atajos + botones acción ─────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.lblEstado = QLabel("")
        self.lblEstado.setStyleSheet("color: gray; font-size: 11px;")
        bar.addWidget(self.lblEstado)

        lblAtajos = QLabel(self.tr("Ctrl+S = Guardar  |  Ctrl+R = Recargar"))
        lblAtajos.setStyleSheet("color: gray; font-size: 11px;")
        bar.addWidget(lblAtajos)
        bar.addStretch()

        self.btnRecargar = QPushButton(self.tr("↺  Recargar"))
        self.btnRecargar.setToolTip(self.tr("Descarta cambios y recarga los globos actuales"))
        self.btnRecargar.clicked.connect(self.recargar)

        self.btnGuardar = QPushButton(self.tr("✓  Guardar"))
        self.btnGuardar.setDefault(True)
        self.btnGuardar.setToolTip(self.tr("Aplica los textos al canvas y al panel derecho"))
        self.btnGuardar.clicked.connect(self.guardar)

        self.btnCerrar = QPushButton(self.tr("Cerrar"))
        self.btnCerrar.clicked.connect(self.close)

        bar.addWidget(self.btnRecargar)
        bar.addWidget(self.btnGuardar)
        bar.addWidget(self.btnCerrar)
        root.addLayout(bar)

        # Atajos
        QShortcut(QKeySequence("Ctrl+S"), self, self.guardar)
        QShortcut(QKeySequence("Ctrl+R"), self, self.recargar)

    # ---------------------------------------------------------- carga datos --

    def cargar_pagina(self, blkitems, pairwidgets, nombre_pagina: str = ""):
        """
        Carga los bloques de la página activa en los dos QPlainTextEdit.
        Una línea por globo en cada columna.
        """
        self._blkitems    = list(blkitems)
        self._pairwidgets = list(pairwidgets)
        self._nombre_pagina = nombre_pagina

        n = len(blkitems)
        self.lblPagina.setText(
            self.tr("Página: ") + nombre_pagina +
            self.tr("   |   Globos: ") + str(n)
        )

        lineas_orig = []
        lineas_trad = []

        for blkitem in blkitems:
            # Texto original
            blk = blkitem.blk
            if hasattr(blk, 'get_text'):
                orig = blk.get_text()
            elif isinstance(blk.text, list):
                orig = " ".join(blk.text)
            else:
                orig = str(blk.text)
            lineas_orig.append(orig.replace("\n", " "))  # sin saltos internos

            # Traducción
            trad = blk.translation or ""
            lineas_trad.append(trad.replace("\n", " "))

        self.txtOriginal.setPlainText("\n".join(lineas_orig))
        self.txtTraduccion.setPlainText("\n".join(lineas_trad))
        self._colorear_lineas()
        self._set_estado("")

    def recargar(self):
        """Descarta ediciones y recarga desde los bloques actuales."""
        if self._blkitems:
            self.cargar_pagina(self._blkitems, self._pairwidgets, self._nombre_pagina)

    # ---------------------------------------------------------------- guardar --

    def guardar(self):
        """
        Aplica línea a línea:
          - línea columna izquierda  → blk.text  + canvas
          - línea columna derecha    → blk.translation + panel derecho
        """
        if not self._blkitems:
            return

        lineas_orig = self.txtOriginal.toPlainText().split("\n")
        lineas_trad = self.txtTraduccion.toPlainText().split("\n")

        # Asegurar que ambas listas tienen la misma longitud que los globos
        n = len(self._blkitems)
        while len(lineas_orig) < n:
            lineas_orig.append("")
        while len(lineas_trad) < n:
            lineas_trad.append("")

        cambios = []
        for i, (blkitem, pairw) in enumerate(zip(self._blkitems, self._pairwidgets)):
            nuevo_orig = lineas_orig[i].strip()
            nueva_trad = lineas_trad[i].strip()

            blk = blkitem.blk
            orig_anterior = blkitem.blk.get_text() if hasattr(blk, 'get_text') else str(blk.text)
            trad_anterior = blk.translation or ""

            orig_cambio = nuevo_orig != orig_anterior.replace("\n", " ").strip()
            trad_cambio = nueva_trad != trad_anterior.strip()

            if orig_cambio or trad_cambio:
                # Actualizar original en canvas
                if orig_cambio:
                    try:
                        if isinstance(blk.text, list):
                            blk.text = [nuevo_orig]
                        else:
                            blk.text = nuevo_orig
                        pairw.e_source.setPlainText(nuevo_orig)
                    except Exception:
                        pass

                if trad_cambio:
                    # 1. Actualizar blk.translation
                    blk.translation = nueva_trad
                    # 2. Limpiar SIEMPRE rich_text para que updateTextBlkList()
                    #    no lo sobreescriba con el HTML antiguo del canvas.
                    #    Sin esto, blk_item.toHtml() devuelve el valor viejo
                    #    y machaca nuestra traducción con delimitadores.
                    blk.rich_text = ''
                    # 3. Actualizar el canvas (blkitem) para que toHtml() quede vacío
                    #    y e_trans quede sincronizado con el nuevo texto
                    try:
                        blkitem.setPlainText(nueva_trad)
                    except Exception:
                        pass
                    try:
                        pairw.e_trans.setPlainText(nueva_trad)
                    except Exception:
                        pass

                cambios.append((i, nuevo_orig, nueva_trad))

        if cambios:
            # Notificar cambios sin disparar setWindowModified del título frameless
            self.translations_saved.emit(cambios)
            self._set_estado(self.tr(f"✓  {len(cambios)} globo(s) actualizado(s)."), ok=True)
        else:
            self._set_estado(self.tr("Sin cambios."))

    # ---------------------------------------------------------- navegación --

    def _on_anterior(self):
        """Guarda la página actual y solicita ir a la anterior."""
        self.guardar()
        # Forzar guardado al JSON aunque no haya cambios detectados
        self.translations_saved.emit([('nav', '', '')])
        self.page_prev_requested.emit()

    def _on_siguiente(self):
        """Guarda la página actual y solicita ir a la siguiente."""
        self.guardar()
        # Forzar guardado al JSON aunque no haya cambios detectados
        self.translations_saved.emit([('nav', '', '')])
        self.page_next_requested.emit()

    # ---------------------------------------------------------- utilidades --

    def _colorear_lineas(self):
        """
        Pinta el fondo de cada línea con un color de la paleta, cíclico,
        y usa EL MISMO color para la línea N en ambas columnas — así se ve
        de un vistazo qué traducción pertenece a qué globo, sin tocar el
        texto ni el bloque en sí.
        """
        for editor in (self.txtOriginal, self.txtTraduccion):
            selections = []
            block = editor.document().firstBlock()
            i = 0
            while block.isValid():
                color = LINE_PALETTE[i % len(LINE_PALETTE)]

                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(color)
                # Pinta todo el ancho de la línea, no solo hasta el último carácter.
                sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)

                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.movePosition(
                    QTextCursor.MoveOperation.EndOfBlock,
                    QTextCursor.MoveMode.KeepAnchor
                )
                sel.cursor = cursor

                selections.append(sel)
                block = block.next()
                i += 1

            editor.setExtraSelections(selections)

    def _copiar_columna(self, editor: QPlainTextEdit):
        """Copia todo el contenido del editor al portapapeles."""
        from qtpy.QtWidgets import QApplication
        QApplication.clipboard().setText(editor.toPlainText())
        self._set_estado(self.tr("Copiado al portapapeles."))

    def _set_estado(self, msg: str, ok: bool = False):
        color = "#2a9d2a" if ok else "gray"
        self.lblEstado.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.lblEstado.setText(msg)
        if msg:
            from qtpy.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self.lblEstado.setText(""))