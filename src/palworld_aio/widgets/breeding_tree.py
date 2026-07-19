from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from palworld_aio.breeding_analyzer import (
    BreedingPath,
    BreedingTreeNode,
    breeding_tree_ancestors,
    build_breeding_tree,
    expand_breeding_tree,
)


class BreedingTreeWidget(QWidget):
    expansion_requested = Signal(object)
    tree_changed = Signal(object)

    NODE_WIDTH = 112
    NODE_HEIGHT = 116
    ICON_SIZE = 58
    HORIZONTAL_GAP = 18
    VERTICAL_GAP = 58
    MARGIN_X = 20
    MARGIN_TOP = 22
    MARGIN_BOTTOM = 30
    BADGE_RADIUS = 13

    def __init__(
        self,
        path: BreedingPath,
        pal_info: dict,
        owned_species: set[str],
        icon_loader: Callable[[str, int], QPixmap | None],
        expandable_species: set[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._root = build_breeding_tree(path)
        self._pal_info = pal_info
        self._owned_species = set(owned_species)
        self._expandable_species = set(expandable_species or ())
        self._icon_loader = icon_loader
        self._icon_cache: dict[str, QPixmap | None] = {}
        self._subtree_widths: dict[int, float] = {}
        self._placements: list[tuple[BreedingTreeNode, QRectF]] = []
        self._rects_by_node: dict[int, QRectF] = {}
        self._max_depth = 0
        self._canvas_width = 360
        self._canvas_height = 180
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet('background: transparent;')
        self._layout_tree()

    def _layout_tree(self):
        self._subtree_widths.clear()
        self._placements.clear()
        self._rects_by_node.clear()
        self._max_depth = 0
        if not self._root:
            self.setMinimumSize(QSize(self._canvas_width, self._canvas_height))
            self.setFixedHeight(self._canvas_height)
            return
        tree_width = self._measure(self._root)
        self._canvas_width = max(360, int(tree_width + (self.MARGIN_X * 2)))
        left = (self._canvas_width - tree_width) / 2
        self._place(self._root, left, 0)
        self._canvas_height = int(
            self.MARGIN_TOP
            + ((self._max_depth + 1) * self.NODE_HEIGHT)
            + (self._max_depth * self.VERTICAL_GAP)
            + self.BADGE_RADIUS
            + self.MARGIN_BOTTOM
        )
        self.setMinimumWidth(self._canvas_width)
        self.setFixedHeight(self._canvas_height)

    @property
    def root(self) -> BreedingTreeNode | None:
        return self._root

    @property
    def owned_species(self) -> set[str]:
        return set(self._owned_species)

    def blocked_species_for(self, node: BreedingTreeNode) -> frozenset[str]:
        if self._root is None:
            return frozenset({node.species})
        return breeding_tree_ancestors(self._root, node) | {node.species}

    def expand_leaf(
        self,
        node: BreedingTreeNode,
        parent_a: str,
        parent_b: str,
    ) -> None:
        if self._root is None:
            raise ValueError('This breeding tree has no root Pal.')
        self._root = expand_breeding_tree(
            self._root,
            node,
            parent_a,
            parent_b,
        )
        self._layout_tree()
        self.updateGeometry()
        self.update()
        self.tree_changed.emit(self._root)

    def _measure(self, node: BreedingTreeNode) -> float:
        if node.is_leaf:
            width = float(self.NODE_WIDTH)
        else:
            children_width = sum(self._measure(parent) for parent in node.parents)
            children_width += self.HORIZONTAL_GAP * (len(node.parents) - 1)
            width = max(float(self.NODE_WIDTH), children_width)
        self._subtree_widths[id(node)] = width
        return width

    def _place(self, node: BreedingTreeNode, left: float, depth: int):
        subtree_width = self._subtree_widths[id(node)]
        x = left + ((subtree_width - self.NODE_WIDTH) / 2)
        y = self.MARGIN_TOP + (depth * (self.NODE_HEIGHT + self.VERTICAL_GAP))
        rect = QRectF(x, y, self.NODE_WIDTH, self.NODE_HEIGHT)
        self._placements.append((node, rect))
        self._rects_by_node[id(node)] = rect
        self._max_depth = max(self._max_depth, depth)
        if node.is_leaf:
            return
        children_width = sum(self._subtree_widths[id(parent)] for parent in node.parents)
        children_width += self.HORIZONTAL_GAP * (len(node.parents) - 1)
        child_left = left + ((subtree_width - children_width) / 2)
        for parent in node.parents:
            self._place(parent, child_left, depth + 1)
            child_left += self._subtree_widths[id(parent)] + self.HORIZONTAL_GAP

    def sizeHint(self):
        return QSize(self._canvas_width, self._canvas_height)

    def paintEvent(self, _event):
        if not self._root:
            return
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        painter.translate(self._horizontal_offset(), 0)
        self._draw_connectors(painter)
        for node, rect in self._placements:
            self._draw_node(painter, node, rect, node is self._root)

    def _horizontal_offset(self) -> float:
        return max(0.0, (self.width() - self._canvas_width) / 2)

    def _draw_connectors(self, painter: QPainter):
        painter.setPen(QPen(QColor('#dce7ef'), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QColor('#dce7ef'))
        for node, rect in self._placements:
            if node.is_leaf:
                continue
            parent_rects = [self._rects_by_node[id(parent)] for parent in node.parents]
            node_x = rect.center().x()
            node_bottom = rect.bottom()
            parent_top = min(parent_rect.top() for parent_rect in parent_rects)
            junction_y = node_bottom + ((parent_top - node_bottom) / 2)
            left_x = min(parent_rect.center().x() for parent_rect in parent_rects)
            right_x = max(parent_rect.center().x() for parent_rect in parent_rects)
            painter.drawLine(QPointF(node_x, node_bottom), QPointF(node_x, junction_y))
            painter.drawLine(QPointF(left_x, junction_y), QPointF(right_x, junction_y))
            for parent_rect in parent_rects:
                parent_x = parent_rect.center().x()
                painter.drawLine(QPointF(parent_x, junction_y), QPointF(parent_x, parent_rect.top()))
            arrow = QPolygonF([
                QPointF(node_x, node_bottom + 1),
                QPointF(node_x - 5, node_bottom + 9),
                QPointF(node_x + 5, node_bottom + 9),
            ])
            painter.drawPolygon(arrow)

    def _draw_node(
        self,
        painter: QPainter,
        node: BreedingTreeNode,
        rect: QRectF,
        is_target: bool,
    ):
        is_owned_leaf = node.is_leaf and node.species in self._owned_species
        is_unowned_leaf = node.is_leaf and not is_owned_leaf
        border_color = QColor('#f4ea00') if is_target else QColor('#263746')
        border_width = 2 if is_target else 1
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(QBrush(QColor('#09121a')))
        painter.drawRoundedRect(rect, 7, 7)

        if is_target:
            self._draw_crown(painter, rect)

        icon_rect = QRectF(
            rect.center().x() - (self.ICON_SIZE / 2),
            rect.top() + 11,
            self.ICON_SIZE,
            self.ICON_SIZE,
        )
        if is_target:
            icon_border = QColor('#f4ea00')
        elif is_owned_leaf:
            icon_border = QColor('#4ade80')
        elif is_unowned_leaf:
            icon_border = QColor('#f59e0b')
        else:
            icon_border = QColor('#dce7ef')
        self._draw_icon(painter, node.species, icon_rect, icon_border)

        name = self._pal_info.get(node.species, {}).get('name', node.species)
        font = QFont('Segoe UI', 10)
        font.setBold(True)
        available_width = int(rect.width() - 10)
        longest_word = max(name.split() or [name], key=len)
        while font.pointSize() > 7 and QFontMetrics(font).horizontalAdvance(longest_word) > available_width:
            font.setPointSize(font.pointSize() - 1)
        painter.setFont(font)
        painter.setPen(QColor('#f8fafc'))
        name_rect = QRectF(rect.left() + 5, rect.top() + 74, rect.width() - 10, 36)
        painter.drawText(name_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, name)

        if node.is_leaf and (is_owned_leaf or self._can_expand(node)):
            self._draw_leaf_badge(painter, rect, is_owned_leaf)

    def _draw_icon(self, painter: QPainter, species: str, rect: QRectF, border: QColor):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#17232d'))
        painter.drawEllipse(rect)
        pixmap = self._icon_for(species)
        if pixmap and not pixmap.isNull():
            clip = QPainterPath()
            clip.addEllipse(rect.adjusted(2, 2, -2, -2))
            painter.save()
            painter.setClipPath(clip)
            painter.drawPixmap(rect.adjusted(2, 2, -2, -2).toRect(), pixmap)
            painter.restore()
        else:
            fallback_font = QFont('Segoe UI', 20)
            fallback_font.setBold(True)
            painter.setFont(fallback_font)
            painter.setPen(QColor('#94a3b8'))
            name = self._pal_info.get(species, {}).get('name', species)
            painter.drawText(rect, Qt.AlignCenter, name[:1].upper())
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 2))
        painter.drawEllipse(rect)

    def _icon_for(self, species: str) -> QPixmap | None:
        if species not in self._icon_cache:
            icon_path = self._pal_info.get(species, {}).get('icon', '')
            self._icon_cache[species] = self._icon_loader(icon_path, self.ICON_SIZE)
        return self._icon_cache[species]

    @staticmethod
    def _draw_crown(painter: QPainter, rect: QRectF):
        center_x = rect.center().x()
        crown = QPolygonF([
            QPointF(center_x - 12, rect.top() - 3),
            QPointF(center_x - 12, rect.top() - 13),
            QPointF(center_x - 6, rect.top() - 8),
            QPointF(center_x, rect.top() - 16),
            QPointF(center_x + 6, rect.top() - 8),
            QPointF(center_x + 12, rect.top() - 13),
            QPointF(center_x + 12, rect.top() - 3),
        ])
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#f4ea00'))
        painter.drawPolygon(crown)

    def _draw_leaf_badge(self, painter: QPainter, rect: QRectF, is_owned: bool):
        center = QPointF(rect.center().x(), rect.bottom())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#15803d') if is_owned else QColor('#b45309'))
        painter.drawEllipse(center, self.BADGE_RADIUS, self.BADGE_RADIUS)
        painter.setPen(QPen(QColor('#ffffff'), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if is_owned:
            painter.drawLine(
                QPointF(center.x() - 6, center.y()),
                QPointF(center.x() - 2, center.y() + 5),
            )
            painter.drawLine(
                QPointF(center.x() - 2, center.y() + 5),
                QPointF(center.x() + 7, center.y() - 5),
            )
        else:
            painter.drawLine(
                QPointF(center.x() - 6, center.y()),
                QPointF(center.x() + 6, center.y()),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - 6),
                QPointF(center.x(), center.y() + 6),
            )

    def mouseMoveEvent(self, event: QMouseEvent):
        point = QPointF(event.position().x() - self._horizontal_offset(), event.position().y())
        tooltip = ''
        clickable_badge = False
        for node, rect in self._placements:
            if not rect.adjusted(-2, -2, 2, self.BADGE_RADIUS).contains(point):
                continue
            name = self._pal_info.get(node.species, {}).get('name', node.species)
            if node is self._root:
                role = 'Target Pal'
            elif not node.is_leaf:
                role = 'Bred in this path'
            elif node.species in self._owned_species:
                role = 'Owned starting Pal'
            else:
                role = 'Unowned partner'
            tooltip = f'{name}\n{role}'
            if (
                self._can_expand(node)
                and self._badge_contains(rect, point)
            ):
                tooltip += '\nClick + to choose breeding parents'
                clickable_badge = True
            break
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor if clickable_badge else Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def _can_expand(self, node: BreedingTreeNode) -> bool:
        return (
            node.is_leaf
            and node.species not in self._owned_species
            and node.species in self._expandable_species
        )

    @staticmethod
    def _badge_contains(rect: QRectF, point: QPointF) -> bool:
        center = QPointF(rect.center().x(), rect.bottom())
        delta_x = point.x() - center.x()
        delta_y = point.y() - center.y()
        return (
            (delta_x * delta_x) + (delta_y * delta_y)
            <= BreedingTreeWidget.BADGE_RADIUS ** 2
        )

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            point = QPointF(
                event.position().x() - self._horizontal_offset(),
                event.position().y(),
            )
            for node, rect in self._placements:
                if (
                    self._can_expand(node)
                    and self._badge_contains(rect, point)
                ):
                    self.expansion_requested.emit(node)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def leaveEvent(self, event):
        self.setToolTip('')
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)
