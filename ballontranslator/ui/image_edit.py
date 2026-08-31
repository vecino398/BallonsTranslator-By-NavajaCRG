from typing import Tuple, List, Union
import numpy as np
import cv2

from qtpy.QtCore import QRectF, Qt, QPointF, QSize
from qtpy.QtWidgets import QStyleOptionGraphicsItem, QGraphicsPixmapItem, QWidget, QGraphicsItem
from qtpy.QtGui import QPen, QPainter, QPixmap, QImage, QBrush

from .misc import pixmap2ndarray

SIZE_MAX = 2147483647

class ImageEditMode:
    NONE = 0
    HandTool = 0
    InpaintTool = 1
    PenTool = 2
    RectTool = 3
    LassoTool = 4
    MagicWandTool = 5

class PenShape:
    Circle = 0
    Rectangle = 1
    Triangle = 2

class StrokeImgItem(QGraphicsItem):
    def __init__(self, pen: QPen, point: QPointF, size: QSize, format: QImage.Format = QImage.Format.Format_ARGB32, shape=PenShape.Circle):
        super().__init__()
        self._img = QImage(size, format)
        self._img.fill(Qt.GlobalColor.transparent)
        pen = QPen(pen)
        if shape == PenShape.Rectangle:
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            
        self.pen = pen
        self._d = d = pen.widthF()
        self._d_rect = d // 32
        self._r = d / 2
        self.clipped_rect = None
        self.shape = shape
        self._line_to = [self._line_to_circle, self._line_to_rectangle][shape]

        self.painter = QPainter(self._img)
        self.painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        if shape != PenShape.Circle:
            pen.setWidthF(0)
        self.painter.setPen(pen)
        self.painter.setBrush(pen.color())
        
        self.setBoundingRegionGranularity(0)
        self.cur_point = point
        self._br = QRectF(0, 0, size.width(), size.height())
        self.is_painting = True

        min_x = self.cur_point.x() - self._r
        min_y = self.cur_point.y() - self._r
        if shape == PenShape.Circle:
            self._line_to(self.cur_point, None)
        else:
            self._line_to(self.cur_point, None)
        rect = QRectF(min_x, min_y, self._d, self._d)
        self.init_rect = rect
        self.update(rect)

    def finishPainting(self) -> None:
        if self.painter.isActive():
            self.painter.end()
        self.is_painting = False

    def clip(self, mask_only=False, format=QImage.Format.Format_ARGB32_Premultiplied) -> Tuple[List, np.ndarray, QImage]:
        img_array = pixmap2ndarray(self._img, True)
        ar = cv2.boundingRect(cv2.findNonZero(img_array[..., -1]))
        img_array = img_array[ar[1]: ar[1] + ar[3], ar[0]: ar[0] + ar[2]]
        if not (ar[2] > 0 and ar[3] > 0):
            return None, None, None
        if mask_only:
            img_array = img_array[..., -1]
            img_array[img_array > 0] = 255
        return ar, img_array, self._img.copy(*ar).convertToFormat(format)

    def startNewPoint(self, pos: QPointF):
        self.is_painting = True
        self.painter.begin(self._img)
        self.painter.setPen(self.pen)
        self.painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        self.cur_point = pos
        self.lineTo(pos)

    def boundingRect(self) -> QRectF:
        return self._br

    def _line_to_circle(self, pnt1: QPointF, pnt2: QPointF):
        if pnt2 is not None:
            self.painter.drawLine(pnt1, pnt2)
        else:
            pen = QPen(self.pen)
            pen.setWidthF(0)
            self.painter.setPen(pen)
            self.painter.setBrush(self.pen.color())
            rect = QRectF(pnt1.x() - self._r, pnt1.y() - self._r, self._d, self._d)
            self.painter.drawEllipse(rect)
            self.painter.setPen(self.pen)

    def _line_to_rectangle(self, pnt1: QPointF, pnt2: QPointF):
        shape_rect = QRectF(pnt1.x() - self._r, pnt1.y() - self._r, self._d, self._d)
        self.painter.drawRect(shape_rect)

    def lineTo(self, new_pnt: QPointF, update=True) -> QRectF:
        delta = self.cur_point - new_pnt
        delta_w, delta_h = abs(delta.x()),  abs(delta.y())
        rect = None
        if delta_w + delta_h > 1:
            min_x = min(self.cur_point.x(), new_pnt.x()) - self._r
            min_y = min(self.cur_point.y(), new_pnt.y()) - self._r
            delta_w += self._d
            delta_h += self._d
            rect = QRectF(min_x, min_y, delta_w, delta_h)
            self._line_to(self.cur_point, new_pnt)
            self.cur_point = new_pnt
            if update:
                self.update(rect)
        return rect

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget) -> None:
        painter.drawImage(0, 0, self._img)


class PixmapItem(QGraphicsPixmapItem):
    def __init__(self, border_pen: QPen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_pen = border_pen

    def paint(self, painter: QPainter, option: 'QStyleOptionGraphicsItem', widget: QWidget) -> None:
        pen = painter.pen()
        painter.setPen(self.border_pen)
        painter.drawRect(self.boundingRect())
        painter.setPen(pen)
        return super().paint(painter, option, widget)


class DrawingLayer(QGraphicsPixmapItem):

    def __init__(self):
        super().__init__()
        self.qimg_dict = {}
        self.drawing_items_info = {}
        self.drawed_pixmap = None

    def addQImage(self, x: int, y: int, qimg: QImage, compose_mode, key: str):
        self.qimg_dict[key] = qimg
        self.drawing_items_info[key] = {'pos': [x, y], 'compose': compose_mode}
        self.update()

    def removeQImage(self, key: str):
        if key in self.qimg_dict:
            self.qimg_dict.pop(key)
            self.drawing_items_info.pop(key)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        pixmap = self.pixmap()
        if pixmap.isNull():
            self.drawed_pixmap = None
            return
        p = QPainter()
        p.begin(pixmap)
        for key in self.qimg_dict:
            item = self.qimg_dict[key]
            info = self.drawing_items_info[key]
            if isinstance(item, QImage):
                p.setCompositionMode(info['compose'])
                p.drawImage(info['pos'][0], info['pos'][1], item)
        p.end()
        painter.drawPixmap(self.offset(), pixmap)
        self.drawed_pixmap = pixmap

    def get_drawed_pixmap(self, format=QImage.Format.Format_ARGB32) -> QPixmap:
        pixmap = self.pixmap() if self.drawed_pixmap is None else self.drawed_pixmap
        return pixmap

    def drawed(self) -> bool:
        return len(self.qimg_dict) > 0

    def clearAllDrawings(self):
        self.qimg_dict.clear()
        self.drawing_items_info.clear()


# ============== VARITA MÁGICA: DETECCIÓN DE GLOBOS (fershare) ==============
#
# Algoritmo autocontenido (solo cv2/numpy): bordes Canny + flood-fill con
# cierre morfológico progresivo, para tolerar pequeños cortes en el contorno
# del globo (escaneados imperfectos, líneas desgastadas). Devuelve el
# contorno detectado listo para reutilizar el pipeline de Lazo ya existente
# (mismo mecanismo de combinar/restar selecciones e inpaint automático).

def _balloon_edges(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if img.ndim == 3 and img.shape[2] == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    elif img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    base_edges = cv2.Canny(blurred, 45, 135)
    small_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    return base_edges, small_kernel


def _nearest_free_pixel(edge_map: np.ndarray, origin_x: int, origin_y: int, max_radius: int = 12):
    """Busca un píxel libre (fuera de los bordes) cerca del punto pulsado,
    por si el usuario ha clicado justo sobre una letra o el propio borde."""
    h, w = edge_map.shape[:2]
    if not (0 <= origin_x < w and 0 <= origin_y < h):
        return None
    if edge_map[origin_y, origin_x] == 0:
        return origin_x, origin_y
    for radius in range(1, max_radius + 1):
        y0, y1 = max(0, origin_y - radius), min(h, origin_y + radius + 1)
        x0, x1 = max(0, origin_x - radius), min(w, origin_x + radius + 1)
        region = edge_map[y0:y1, x0:x1]
        free = np.argwhere(region == 0)
        if free.size:
            best_pt, best_dist = None, None
            for fy, fx in free:
                ay, ax = y0 + fy, x0 + fx
                d = (ax - origin_x) ** 2 + (ay - origin_y) ** 2
                if best_dist is None or d < best_dist:
                    best_dist, best_pt = d, (ax, ay)
            return best_pt
    return None


def _flood_fill_closed_region(edge_map: np.ndarray, x: int, y: int):
    h, w = edge_map.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        return None
    flood_source = np.where(edge_map == 0, 0, 255).astype(np.uint8)
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(flood_source, flood_mask, (x, y), 128, flags=4)
    selected = np.where(flood_source == 128, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(selected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    result_mask = np.zeros_like(selected)
    cv2.drawContours(result_mask, [largest], -1, 255, thickness=cv2.FILLED)
    return result_mask, largest


def _is_valid_balloon_region(mask: np.ndarray, image_width: int, image_height: int, max_ratio: float) -> bool:
    area = cv2.countNonZero(mask)
    if area < 16:
        return False
    return (area / (image_width * image_height)) <= max_ratio


def detect_balloon_contour_points(img: np.ndarray, seed_x: int, seed_y: int, erode_px: int = 3) -> Union[np.ndarray, None]:
    """Detecta el contorno del globo bajo (seed_x, seed_y).

    Prueba varios niveles de cierre morfológico progresivo (0, 2, 4, 6, 8 px)
    sobre el mapa de bordes, para que un corte pequeño en el trazo del globo
    no deje que el flood-fill se escape hacia el fondo de la página.

    El flood-fill se detiene justo en el borde/contorno negro del globo, así
    que la región detectada "toca" ese borde. Un trazo de Lazo a mano suele
    quedarse un poco por dentro, dejando la máscara a salvo del contorno; para
    igualar eso, `erode_px` retranquea la máscara detectada hacia dentro esa
    cantidad de píxeles antes de extraer el contorno final — si no, el
    inpainter usa los píxeles oscuros del borde como referencia de fondo y el
    relleno sale con un tono plano en vez de blanco.

    Devuelve un array (N, 2) de puntos (x, y) en coordenadas de imagen listo
    para pasarlo tal cual a un pipeline de selección por polígono (Lazo), o
    None si no se encontró ninguna región válida.
    """
    h, w = img.shape[:2]
    if not (0 <= seed_x < w and 0 <= seed_y < h):
        return None

    base_edges, small_kernel = _balloon_edges(img)
    gap_close_levels = (0, 2, 4, 6, 8)

    erode_kernel = None
    if erode_px > 0:
        erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_px * 2 + 1, erode_px * 2 + 1))

    for close_radius in gap_close_levels:
        if close_radius == 0:
            edges = cv2.morphologyEx(base_edges, cv2.MORPH_CLOSE, small_kernel, iterations=1)
            max_ratio = 0.90
        else:
            size = close_radius * 2 + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
            edges = cv2.morphologyEx(base_edges, cv2.MORPH_CLOSE, kernel, iterations=1)
            max_ratio = 0.60

        edges = cv2.dilate(edges, small_kernel, iterations=1)

        nearest = _nearest_free_pixel(edges, seed_x, seed_y)
        if nearest is None:
            continue
        fx, fy = nearest

        flood_result = _flood_fill_closed_region(edges, fx, fy)
        if flood_result is None:
            continue
        mask, _raw_contour = flood_result

        if not _is_valid_balloon_region(mask, w, h, max_ratio):
            continue

        if erode_kernel is not None:
            eroded = cv2.erode(mask, erode_kernel, iterations=1)
            # Si el globo es muy pequeño/estrecho, el retranqueo podría
            # comerse la región entera: en ese caso mantenemos la máscara
            # original sin retranquear en vez de descartar la detección.
            if cv2.countNonZero(eroded) >= 16:
                mask = eroded

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)

        approx = cv2.approxPolyDP(contour, 1.5, True)
        pts = approx.reshape(-1, 2).astype(np.float64)
        if len(pts) < 3:
            continue
        return pts

    return None
