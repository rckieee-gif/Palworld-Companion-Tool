from PySide6.QtWidgets import QGraphicsItem, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsPolygonItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QColor, QPainter, QFont, QPolygonF, QBrush
class BaseRadiusRing(QGraphicsEllipseItem):
    def __init__(self, x, y, save_radius, is_preview=False):
        super().__init__()
        self.save_radius = save_radius
        self.is_preview = is_preview
        self.setPos(x, y)
        self._update_radius()
        self.setZValue(5)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, False)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self._setup_appearance()
    def _setup_appearance(self):
        if self.is_preview:
            pen = QPen(QColor(255, 215, 0, 200), 3)
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([10, 5])
            self.setPen(pen)
            self.setBrush(QColor(255, 215, 0, 30))
        else:
            pen = QPen(QColor(0, 255, 200, 220), 2)
            self.setPen(pen)
            self.setBrush(QColor(0, 255, 200, 40))
    def _update_radius(self):
        scene_radius = self._save_radius_to_scene_pixels(self.save_radius)
        diameter = scene_radius * 2
        self.setRect(-diameter / 2, -diameter / 2, diameter, diameter)
    @staticmethod
    def _save_radius_to_scene_pixels(save_radius):
        display_radius = save_radius / 3500.0 * 7.9
        scene_radius = display_radius * (2048 / 2000)
        scene_radius = scene_radius + 5
        return max(scene_radius, 15)
    def update_radius(self, new_save_radius):
        self.save_radius = new_save_radius
        self._update_radius()
        self.update()
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        super().paint(painter, option, widget)
class ExclusionZoneItem(QGraphicsRectItem):
    def __init__(self, zone_data, map_width=2048, map_height=2048):
        super().__init__()
        self.zone_data = zone_data
        self.map_width = map_width
        self.map_height = map_height
        self._update_geometry()
        self.setZValue(3)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._setup_appearance()
    def _update_geometry(self):
        from palworld_aio.map import annotations
        x1, y1 = (self.zone_data.get('x1', 0), self.zone_data.get('y1', 0))
        x2, y2 = (self.zone_data.get('x2', 0), self.zone_data.get('y2', 0))
        scene_x1, scene_y1 = annotations.world_to_scene(x1, y1, self.map_width, self.map_height)
        scene_x2, scene_y2 = annotations.world_to_scene(x2, y2, self.map_width, self.map_height)
        left = min(scene_x1, scene_x2)
        top = min(scene_y1, scene_y2)
        width = abs(scene_x2 - scene_x1)
        height = abs(scene_y2 - scene_y1)
        self.setRect(left, top, width, height)
    def _setup_appearance(self):
        color = [255, 0, 0, 100]
        r, g, b, a = (color[0], color[1], color[2], color[3] if len(color) > 3 else 100)
        pen = QPen(QColor(r, g, b, min(a + 50, 255)), 2)
        self.setPen(pen)
        self.setBrush(QColor(r, g, b, a))
    def update_zone_data(self, zone_data):
        self.zone_data = zone_data
        self._update_geometry()
        self._setup_appearance()
        self.update()
    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        pen = self.pen()
        new_pen = QPen(pen.color(), pen.width() + 2)
        new_pen.setStyle(Qt.DashLine)
        self.setPen(new_pen)
    def hoverLeaveEvent(self, event):
        super().hoverLeaveEvent(event)
        self._setup_appearance()
        self.update()
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        super().paint(painter, option, widget)
        if self.zone_data.get('name'):
            painter.setPen(QColor(255, 255, 255, 200))
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            rect = self.rect()
            painter.drawText(rect, Qt.AlignTop | Qt.AlignLeft, self.zone_data['name'])
class ZonePreviewItem(QGraphicsRectItem):
    def __init__(self):
        super().__init__()
        self.point_a = None
        self.point_b = None
        self.setZValue(8)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self._setup_appearance()
    def _setup_appearance(self):
        pen = QPen(QColor(255, 0, 0, 200), 2)
        pen.setStyle(Qt.DashLine)
        pen.setDashPattern([10, 5])
        self.setPen(pen)
        self.setBrush(QColor(255, 0, 0, 75))
    def update_preview(self, point_a, point_b):
        self.point_a = point_a
        self.point_b = point_b
        if point_a and point_b:
            x1, y1 = (point_a.x(), point_a.y())
            x2, y2 = (point_b.x(), point_b.y())
            left = min(x1, x2)
            top = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            self.setRect(left, top, width, height)
        self.update()
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        super().paint(painter, option, widget)
class PolygonExclusionZoneItem(QGraphicsPolygonItem):
    def __init__(self, zone_data, map_width=2048, map_height=2048):
        super().__init__()
        self.zone_data = zone_data
        self.map_width = map_width
        self.map_height = map_height
        self._update_geometry()
        self.setZValue(3)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._setup_appearance()
    def _update_geometry(self):
        from palworld_aio.map import annotations
        points = self.zone_data.get('points', [])
        if not points:
            return
        polygon_points = []
        for p in points:
            wx, wy = (p.get('x', 0), p.get('y', 0))
            sx, sy = annotations.world_to_scene(wx, wy, self.map_width, self.map_height)
            polygon_points.append(QPointF(sx, sy))
        qpolygon = QPolygonF(polygon_points)
        self.setPolygon(qpolygon)
    def _setup_appearance(self):
        color = [255, 0, 0, 100]
        r, g, b, a = (color[0], color[1], color[2], color[3] if len(color) > 3 else 100)
        pen = QPen(QColor(r, g, b, min(a + 50, 255)), 2)
        self.setPen(pen)
        self.setBrush(QColor(r, g, b, a))
    def update_zone_data(self, zone_data):
        self.zone_data = zone_data
        self._update_geometry()
        self._setup_appearance()
        self.update()
    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        pen = self.pen()
        new_pen = QPen(pen.color(), pen.width() + 2)
        new_pen.setStyle(Qt.DashLine)
        self.setPen(new_pen)
    def hoverLeaveEvent(self, event):
        super().hoverLeaveEvent(event)
        self._setup_appearance()
        self.update()
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        super().paint(painter, option, widget)
        if self.zone_data.get('name'):
            painter.setPen(QColor(255, 255, 255, 200))
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            poly = self.polygon()
            if not poly.isEmpty():
                rect = poly.boundingRect()
                painter.drawText(rect, Qt.AlignTop | Qt.AlignLeft, self.zone_data['name'])
class PolygonPreviewItem(QGraphicsPolygonItem):
    def __init__(self):
        super().__init__()
        self.points = []
        self.preview_point = None
        self.setZValue(8)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self._setup_appearance()
    def _setup_appearance(self):
        pen = QPen(QColor(255, 0, 0, 200), 2)
        pen.setStyle(Qt.DashLine)
        pen.setDashPattern([10, 5])
        self.setPen(pen)
        self.setBrush(QColor(255, 0, 0, 75))
    def boundingRect(self):
        if not self.points:
            return super().boundingRect()
        min_x = min((p.x() for p in self.points))
        max_x = max((p.x() for p in self.points))
        min_y = min((p.y() for p in self.points))
        max_y = max((p.y() for p in self.points))
        if self.preview_point:
            min_x = min(min_x, self.preview_point.x())
            max_x = max(max_x, self.preview_point.x())
            min_y = min(min_y, self.preview_point.y())
            max_y = max(max_y, self.preview_point.y())
        padding = 10
        return QRectF(min_x - padding, min_y - padding, max_x - min_x + padding * 2, max_y - min_y + padding * 2)
    def add_point(self, point):
        if point:
            self.points.append(point)
            self._update_polygon()
    def set_preview_point(self, point):
        self.preview_point = point
        self.update()
    def clear_points(self):
        self.points = []
        self.preview_point = None
        self.setPolygon(QPolygonF())
        self.update()
    def _update_polygon(self):
        if len(self.points) >= 2:
            polygon_points = [QPointF(p.x(), p.y()) for p in self.points]
            qpolygon = QPolygonF(polygon_points)
            self.setPolygon(qpolygon)
        elif len(self.points) == 1:
            self.setPolygon(QPolygonF([QPointF(self.points[0].x(), self.points[0].y())]))
        self.update()
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        if len(self.points) >= 2:
            pen = QPen(QColor(255, 0, 0, 200), 2)
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([10, 5])
            painter.setPen(pen)
            qpolygon = QPolygonF([QPointF(p.x(), p.y()) for p in self.points])
            painter.drawPolygon(qpolygon)
        elif len(self.points) == 1:
            pen = QPen(QColor(255, 0, 0, 200), 2)
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([10, 5])
            painter.setPen(pen)
            painter.drawPoint(self.points[0])
        for i, point in enumerate(self.points):
            painter.setPen(QPen(QColor(255, 255, 0, 255), 2))
            painter.setBrush(QBrush(QColor(255, 255, 0, 255)))
            radius = 4
            painter.drawEllipse(point, radius, radius)
            if i > 0:
                prev = self.points[i - 1]
                painter.setPen(QPen(QColor(255, 255, 0, 255), 1))
                painter.drawLine(prev, point)
        if self.preview_point and self.points:
            last_point = self.points[-1]
            painter.setPen(QPen(QColor(255, 255, 0, 150), 1, Qt.DashLine))
            painter.drawLine(last_point, self.preview_point)
