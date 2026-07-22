import math
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QColor, QRadialGradient, QPainter, QPainterPath, QPen


def location_pin_color(source: str, found: bool = False) -> QColor:
    if source == 'local':
        return QColor('#E77A20')
    if found:
        return QColor('#27A875')
    return QColor('#2F80ED')


def _location_pin_path(size: float) -> QPainterPath:
    half = size / 2
    path = QPainterPath()
    path.moveTo(0, half)
    path.cubicTo(-half * 0.3, half * 0.2, -half, 0, -half, -half * 0.25)
    path.cubicTo(-half, -half * 0.8, -half * 0.55, -half, 0, -half)
    path.cubicTo(half * 0.55, -half, half, -half * 0.8, half, -half * 0.25)
    path.cubicTo(half, 0, half * 0.3, half * 0.2, 0, half)
    path.closeSubpath()
    return path


def _paint_location_pin(
    painter: QPainter,
    size: float,
    color: QColor,
    found: bool,
) -> None:
    half = size / 2
    painter.setPen(QPen(QColor('#F5FAFF'), max(1.0, size / 12)))
    painter.setBrush(color)
    painter.drawPath(_location_pin_path(size))
    if found:
        check = QPainterPath()
        check.moveTo(-half * 0.38, -half * 0.28)
        check.lineTo(-half * 0.08, 0)
        check.lineTo(half * 0.38, -half * 0.48)
        pen = QPen(QColor('#FFFFFF'), max(1.6, size / 9))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(check)
        return

    inner_radius = max(2.0, size * 0.16)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor('#15345E'))
    painter.drawEllipse(
        QPointF(0, -half * 0.3),
        inner_radius,
        inner_radius,
    )


def location_pin_pixmap(
    size: int = 30,
    source: str = 'bundled',
    found: bool = False,
) -> QPixmap:
    padding = 4
    pixmap = QPixmap(size + padding * 2, size + padding * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.translate(pixmap.width() / 2, pixmap.height() / 2)
    _paint_location_pin(painter, size, location_pin_color(source, found), found)
    painter.end()
    return pixmap


class BaseMarker(QGraphicsPixmapItem):
    def __init__(self, base_data, x, y, base_icon_pixmap, config):
        super().__init__()
        self.base_data = base_data
        self.config = config
        self.base_icon_original = base_icon_pixmap
        self.marker_type = config['marker']['type']
        if self.marker_type == 'dot':
            self.current_size = config['marker']['dot']['size']
            if not config['marker']['dot']['dynamic_sizing']:
                self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        else:
            self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            self.current_size = config['marker']['icon']['base_size']
        self._update_icon_size(self.current_size)
        self.center_x = x
        self.center_y = y
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.glow_alpha = 0
        self.glow_increasing = True
        self.is_hovered = False
        self.shine_pos = 0
    def _update_icon_size(self, size):
        self.current_size = size
        scaled = self.base_icon_original.scaled(int(size), int(size), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.scaled_pixmap = scaled
        self.setPixmap(scaled)
        self.setOffset(-size / 2, -size / 2)
    def scale_to_zoom(self, zoom_level):
        if self.marker_type == 'dot':
            if not self.config['marker']['dot']['dynamic_sizing']:
                return
            size_min = self.config['marker']['dot']['size_min']
            size_max = self.config['marker']['dot']['size_max']
            formula = self.config['marker']['dot']['dynamic_sizing_formula']
        else:
            if not self.config['marker']['icon']['dynamic_sizing']:
                return
            size_min = self.config['marker']['icon']['size_min']
            size_max = self.config['marker']['icon']['size_max']
            formula = self.config['marker']['icon']['dynamic_sizing_formula']
        clamped_zoom = max(0.05, min(zoom_level, 30.0))
        if formula == 'sqrt':
            raw_size = 48 / math.sqrt(clamped_zoom)
        elif formula == 'linear':
            raw_size = 100 - zoom_level * 10
        elif formula == 'log':
            raw_size = 50 / math.log(clamped_zoom + 1)
        else:
            raw_size = self.current_size
        new_size = max(size_min, min(size_max, int(raw_size)))
        if new_size != self.current_size:
            self._update_icon_size(new_size)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.marker_type == 'icon':
            shine_pixmap = self.scaled_pixmap.copy()
            mask_pixmap = QPixmap(self.current_size, self.current_size)
            mask_pixmap.fill(QColor(0, 0, 0, 0))
            mask_painter = QPainter(mask_pixmap)
            mask_painter.setPen(Qt.NoPen)
            mask_painter.setBrush(QColor(255, 255, 255, 120))
            shine_pos = self.shine_pos - 50
            points = [QPointF(shine_pos, 0), QPointF(shine_pos + 15, 0), QPointF(shine_pos - 5, self.current_size), QPointF(shine_pos - 20, self.current_size)]
            mask_painter.drawPolygon(points)
            mask_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            mask_painter.drawPixmap(0, 0, self.scaled_pixmap)
            mask_painter.end()
            shine_painter = QPainter(shine_pixmap)
            shine_painter.setCompositionMode(QPainter.CompositionMode_Plus)
            shine_painter.drawPixmap(0, 0, mask_pixmap)
            shine_painter.end()
            self.setPixmap(shine_pixmap)
        glow_config = self.config['glow']
        if glow_config['enabled'] and (self.isSelected() or self.glow_alpha > 0 or self.is_hovered):
            alpha = max(self.glow_alpha, glow_config['hover_alpha'] if self.is_hovered else 0)
            glow_radius = self.current_size * glow_config['radius_multiplier']
            glow_color = QColor(*glow_config['color'])
            gradient = QRadialGradient(0, 0, glow_radius)
            gradient.setColorAt(0, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), alpha))
            gradient.setColorAt(0.5, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), alpha // 2))
            gradient.setColorAt(1, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(-glow_radius, -glow_radius, glow_radius * 2, glow_radius * 2))
        super().paint(painter, option, widget)
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
    def start_glow(self):
        self.glow_alpha = 180
    def update_glow(self):
        glow_config = self.config['glow']
        alpha_min = glow_config['selected_alpha_min']
        alpha_max = glow_config['selected_alpha_max']
        speed = glow_config['animation_speed']
        if self.isSelected():
            if self.glow_increasing:
                self.glow_alpha += speed
                if self.glow_alpha >= alpha_max:
                    self.glow_increasing = False
            else:
                self.glow_alpha -= speed
                if self.glow_alpha <= alpha_min:
                    self.glow_increasing = True
        elif self.glow_alpha > 0:
            self.glow_alpha -= speed * 1.5
            if self.glow_alpha < 0:
                self.glow_alpha = 0
        self.shine_pos = (self.shine_pos + 2) % 100
        self.update()
class PlayerMarker(QGraphicsPixmapItem):
    PLAYER_GLOW_COLOR = [0, 255, 150]
    SIZE_MIN = 32
    SIZE_MAX = 64
    BASE_SIZE = 48
    def __init__(self, player_data, x, y, player_icon_pixmap):
        super().__init__()
        self.player_data = player_data
        self.player_icon_original = player_icon_pixmap
        self.current_size = self.BASE_SIZE
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self._update_icon_size(self.current_size)
        self.center_x = x
        self.center_y = y
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.glow_alpha = 0
        self.glow_increasing = True
        self.is_hovered = False
        self.shine_pos = 0
    def _update_icon_size(self, size):
        self.current_size = size
        scaled = self.player_icon_original.scaled(int(size), int(size), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.scaled_pixmap = scaled
        self.setPixmap(scaled)
        self.setOffset(-size / 2, -size / 2)
    def scale_to_zoom(self, zoom_level):
        clamped_zoom = max(0.05, min(zoom_level, 30.0))
        raw_size = 48 / math.sqrt(clamped_zoom)
        new_size = max(self.SIZE_MIN, min(self.SIZE_MAX, int(raw_size)))
        if new_size != self.current_size:
            self._update_icon_size(new_size)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        shine_pixmap = self.scaled_pixmap.copy()
        mask_pixmap = QPixmap(self.current_size, self.current_size)
        mask_pixmap.fill(QColor(0, 0, 0, 0))
        mask_painter = QPainter(mask_pixmap)
        mask_painter.setPen(Qt.NoPen)
        mask_painter.setBrush(QColor(255, 255, 255, 120))
        shine_pos = self.shine_pos - 50
        points = [QPointF(shine_pos, 0), QPointF(shine_pos + 15, 0), QPointF(shine_pos - 5, self.current_size), QPointF(shine_pos - 20, self.current_size)]
        mask_painter.drawPolygon(points)
        mask_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        mask_painter.drawPixmap(0, 0, self.scaled_pixmap)
        mask_painter.end()
        shine_painter = QPainter(shine_pixmap)
        shine_painter.setCompositionMode(QPainter.CompositionMode_Plus)
        shine_painter.drawPixmap(0, 0, mask_pixmap)
        shine_painter.end()
        self.setPixmap(shine_pixmap)
        if self.isSelected() or self.glow_alpha > 0 or self.is_hovered:
            alpha = max(self.glow_alpha, 80 if self.is_hovered else 0)
            glow_radius = self.current_size * 1.5
            gradient = QRadialGradient(0, 0, glow_radius)
            color = QColor(*self.PLAYER_GLOW_COLOR)
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
            gradient.setColorAt(0.5, QColor(color.red(), color.green(), color.blue(), alpha // 2))
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(-glow_radius, -glow_radius, glow_radius * 2, glow_radius * 2))
        super().paint(painter, option, widget)
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
    def start_glow(self):
        self.glow_alpha = 180
    def update_glow(self):
        alpha_min = 80
        alpha_max = 180
        speed = 8
        if self.isSelected():
            if self.glow_increasing:
                self.glow_alpha += speed
                if self.glow_alpha >= alpha_max:
                    self.glow_increasing = False
            else:
                self.glow_alpha -= speed
                if self.glow_alpha <= alpha_min:
                    self.glow_increasing = True
        elif self.glow_alpha > 0:
            self.glow_alpha -= speed * 1.5
            if self.glow_alpha < 0:
                self.glow_alpha = 0
        self.shine_pos = (self.shine_pos + 2) % 100
        self.update()


class LocationMarker(QGraphicsItem):
    SIZE_MIN = 16
    SIZE_MAX = 34
    BASE_SIZE = 16

    def __init__(self, location_data, x, y, found=False):
        super().__init__()
        self.location_data = location_data
        self.found = found
        self.current_size = self.BASE_SIZE
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.center_x = x
        self.center_y = y
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setToolTip(location_data.name)
        self.glow_alpha = 0
        self.glow_increasing = True
        self.is_hovered = False

    def boundingRect(self):
        radius = self.current_size * 1.4
        return QRectF(-radius, -radius, radius * 2, radius * 2)

    def scale_to_zoom(self, zoom_level):
        clamped_zoom = max(0.05, min(zoom_level, 30.0))
        raw_size = 12 + math.sqrt(clamped_zoom) * 5
        new_size = max(self.SIZE_MIN, min(self.SIZE_MAX, int(raw_size)))
        if new_size != self.current_size:
            self.prepareGeometryChange()
            self.current_size = new_size
            self.update()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        color = location_pin_color(self.location_data.source, self.found)
        if self.isSelected() or self.glow_alpha > 0 or self.is_hovered:
            alpha = max(self.glow_alpha, 90 if self.is_hovered else 0)
            glow_radius = self.current_size * 1.35
            gradient = QRadialGradient(0, 0, glow_radius)
            gradient.setColorAt(
                0,
                QColor(color.red(), color.green(), color.blue(), alpha),
            )
            gradient.setColorAt(
                0.55,
                QColor(color.red(), color.green(), color.blue(), alpha // 2),
            )
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(
                -glow_radius,
                -glow_radius,
                glow_radius * 2,
                glow_radius * 2,
            ))

        _paint_location_pin(
            painter,
            self.current_size,
            color,
            self.found,
        )

    def set_found(self, found: bool) -> None:
        if self.found == found:
            return
        self.found = found
        self.update()

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def start_glow(self):
        self.glow_alpha = 180

    def update_glow(self):
        if self.isSelected():
            if self.glow_increasing:
                self.glow_alpha += 8
                if self.glow_alpha >= 180:
                    self.glow_increasing = False
            else:
                self.glow_alpha -= 8
                if self.glow_alpha <= 80:
                    self.glow_increasing = True
        elif self.glow_alpha > 0:
            self.glow_alpha = max(0, self.glow_alpha - 12)
        self.update()
