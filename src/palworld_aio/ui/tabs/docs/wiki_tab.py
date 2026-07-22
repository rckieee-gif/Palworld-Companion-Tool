import os
import json
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QStackedWidget, QLineEdit, QScrollArea,
    QFrame, QGridLayout, QAbstractItemView, QStyle, QComboBox, QToolButton,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QPixmap, QIcon, QCursor, QKeySequence
from i18n import t
from palworld_aio.game_data import GameDataError, load_game_data
from palworld_aio.ui.pal_assets import element_pixmap
from palworld_aio.wiki_text import prepare_wiki_entries
from resource_resolver import get_base_dir, resource_path

LOGGER = logging.getLogger(__name__)
_DATA_ERRORS = {}

_WORK_SUITABILITY_DISPLAY = {
    'EmitFlame': 'Kindling',
    'Watering': 'Watering',
    'Seeding': 'Planting',
    'GenerateElectricity': 'Electricity',
    'Handcraft': 'Handiwork',
    'Collection': 'Gathering',
    'Deforest': 'Lumbering',
    'Mining': 'Mining',
    'ProductMedicine': 'Medicine',
    'Cool': 'Cooling',
    'Transport': 'Transporting',
    'MonsterFarm': 'Farming',
    'OilExtraction': 'Oil Extraction',
}

_CATEGORIES = [
    ('pals', 'docs.wiki.pals', 'characters.json', 'pals'),
    ('items', 'docs.wiki.items', 'items.json', 'items'),
    ('buildings', 'docs.wiki.buildings', 'world.json', 'structures'),
    ('active_skills', 'docs.wiki.active_skills', 'skills.json', 'skills'),
    ('passive_skills', 'docs.wiki.passive_skills', 'skills.json', 'passives'),
    ('technologies', 'docs.wiki.technologies', 'world.json', 'technology'),
    ('elements', 'docs.wiki.elements', 'skills.json', 'elements'),
    ('work_suitability', 'docs.wiki.work_suitability', 'work_suitability.json', 'work_types'),
]

_CATEGORY_CONFIG = {
    'pals': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('name') or '').lower()),
            ('paldeck', 'docs.wiki.sort.index', lambda d: _resolve_zukan(d) or 9999),
        ],
        'filter_groups': [
            {'id': 'element', 'label_key': 'docs.wiki.filter.element', 'field': 'elements', 'type': 'dict_keys', 'is_element': True},
        ],
    },
    'items': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('name') or '').lower()),
            ('price', 'docs.wiki.sort.price', lambda d: d.get('price') or 0),
            ('weight', 'docs.wiki.sort.weight', lambda d: d.get('weight') or 0),
        ],
        'filter_groups': [
            {'id': 'type', 'label_key': 'docs.wiki.filter.type', 'field': 'type_a_display', 'type': 'field_values'},
            {'id': 'rarity', 'label_key': 'docs.wiki.filter.rarity', 'field': 'rarity', 'type': 'field_values'},
        ],
    },
    'buildings': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('name') or '').lower()),
            ('rank', 'docs.wiki.sort.rank', lambda d: d.get('rank') or 0),
            ('hp', 'docs.wiki.sort.hp', lambda d: d.get('hp') or 0),
        ],
        'filter_groups': [
            {'id': 'type', 'label_key': 'docs.wiki.filter.type', 'field': 'type_a_display', 'type': 'field_values'},
        ],
    },
    'active_skills': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('name') or '').lower()),
            ('power', 'docs.wiki.sort.power', lambda d: d.get('power') or 0),
            ('cooldown', 'docs.wiki.sort.cooldown', lambda d: d.get('cooldown') or 0),
        ],
        'filter_groups': [
            {'id': 'element', 'label_key': 'docs.wiki.filter.element', 'field': 'element', 'type': 'field_values', 'is_element': True},
        ],
    },
    'passive_skills': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('name') or '').lower()),
            ('rank', 'docs.wiki.sort.rank', lambda d: d.get('rank') or 0),
        ],
        'filter_groups': [
            {'id': 'rank', 'label_key': 'docs.wiki.filter.rank', 'field': 'rank', 'type': 'int_values', 'values': [1, 2, 3, 4]},
        ],
    },
    'technologies': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('name') or '').lower()),
            ('tier', 'docs.wiki.sort.tier', lambda d: d.get('tier') or 0),
            ('level', 'docs.wiki.sort.level', lambda d: d.get('level_cap') or 0),
            ('cost', 'docs.wiki.sort.cost', lambda d: d.get('cost') or 0),
        ],
        'filter_groups': [
            {'id': 'type', 'label_key': 'docs.wiki.filter.type', 'field': 'type', 'type': 'field_values', 'value_keys': {'boss': 'docs.wiki.filter.value.boss', 'standard': 'docs.wiki.filter.value.standard'}},
        ],
    },
    'elements': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('display') or d.get('name') or '').lower()),
        ],
        'filter_groups': [],
    },
    'work_suitability': {
        'sort_fields': [
            ('name', 'docs.wiki.sort.name', lambda d: (d.get('display_name') or d.get('id') or '').lower()),
        ],
        'filter_groups': [],
    },
}

_LIST_ICON = 28


def _tx(key, default, **values):
    translated = t(key, default=default, **values)
    return default.format(**values) if translated in ('None', 'null', '') else translated

def _load_json(filename, key):
    try:
        data = load_game_data(filename)
    except GameDataError as exc:
        _DATA_ERRORS[filename] = str(exc)
        LOGGER.error('%s', exc)
        return []
    value = data.get(key, [])
    if not isinstance(value, (list, dict)):
        message = f'Wiki category {key} has an invalid format in {filename}.'
        _DATA_ERRORS[filename] = message
        LOGGER.error('%s', message)
        return []
    return value

def _icon(icon_path, size=_LIST_ICON):
    if icon_path:
        base_dir = get_base_dir()
        fp = resource_path(base_dir, 'game_data', icon_path.lstrip('/')) if icon_path.startswith('/icons/') else resource_path(base_dir, 'game_data', 'icons', icon_path)
        if os.path.exists(fp):
            px = QPixmap(fp)
            if not px.isNull():
                return px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        base = fp.rsplit('.', 1)[0]
        for ext in ('.webp', '.png'):
            p = base + ext
            if os.path.exists(p):
                px = QPixmap(p)
                if not px.isNull():
                    return px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    base_dir = get_base_dir()
    unknown = resource_path(base_dir, 'game_data', 'icons', 'T_icon_unknown.webp')
    if os.path.exists(unknown):
        px = QPixmap(unknown)
        if not px.isNull():
            return px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None

_item_names = None

def _resolve_item(id):
    global _item_names
    if _item_names is None:
        items = _load_json('items.json', 'items')
        _item_names = {i['asset']: i['name'] for i in items}
    return _item_names.get(id, id)

_pals_cache = None

def _pals():
    global _pals_cache
    if _pals_cache is None:
        _pals_cache = prepare_wiki_entries(
            'pals',
            _load_json('characters.json', 'pals'),
        )
    return _pals_cache

def _pals_by_element(name):
    return [p for p in _pals() if name in p.get('elements', {})]

def _pals_by_work(wid):
    return [(p, p.get('work_suitabilities', {}).get(wid, 0)) for p in _pals() if p.get('work_suitabilities', {}).get(wid, 0) > 0]

_WORK_ICON_REMAP = {
    'ProductMedicine': '/icons/ui/T_icon_palwork_08.webp',
    'Cool': '/icons/ui/T_icon_palwork_10.webp',
    'Transport': '/icons/ui/T_icon_palwork_11.webp',
    'MonsterFarm': '/icons/ui/T_icon_palwork_12.webp',
    'OilExtraction': '/icons/ui/T_icon_palwork_09.webp',
}

def _work_icon(wid):
    return _WORK_ICON_REMAP.get(wid)

_work_paths = None

def _work_icon_path(wid):
    global _work_paths
    if _work_paths is None:
        types = _load_json('work_suitability.json', 'work_types')
        _work_paths = {}
        for t in types:
            rid = t.get('id', '')
            remapped = _work_icon(rid)
            _work_paths[rid] = remapped if remapped else t.get('icon', '')
    return _work_paths.get(wid, '')

import re

def _enum_name(raw):
    if not raw or '::' not in str(raw):
        return str(raw) if raw else ''
    name = str(raw).split('::')[-1]
    return re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', name).strip()

_learnset_cache = None
_learnset_ci = None

def _learnset_for_pal(asset):
    global _learnset_cache, _learnset_ci
    if _learnset_cache is None:
        ls = _load_json('pals_learnset.json', 'learnset')
        _learnset_cache = ls if isinstance(ls, dict) else {}
        _learnset_ci = {k.lower(): v for k, v in _learnset_cache.items()}
    direct = _learnset_cache.get(asset)
    if direct is not None:
        return direct
    return _learnset_ci.get(asset.lower(), [])

_skill_names = None

def _skill_name(waza_id):
    global _skill_names
    if _skill_names is None:
        sk = _load_json('skills.json', 'skills')
        _skill_names = {s.get('asset', '').lower(): s.get('name', s.get('asset', '')) for s in sk}
    nid = waza_id.replace('EPalWazaID::', '')
    return _skill_names.get(nid.lower(), nid)

_skill_elem = None

def _skill_elem_cache(waza_id):
    global _skill_elem
    if _skill_elem is None:
        sk = _load_json('skills.json', 'skills')
        _skill_elem = {s.get('asset', '').lower(): s.get('element', '') for s in sk}
    nid = waza_id.replace('EPalWazaID::', '')
    return _skill_elem.get(nid.lower(), '')

def _get(data, path):
    for p in path.split('.'):
        if isinstance(data, dict):
            data = data.get(p)
        else:
            return None
    return data

def _v(text):
    if text is None or text == 'None':
        return None
    return str(text)


def _normalize_elem(name):
    s = str(name)
    if s.startswith('EPalElementType::'):
        return s.split('::')[-1]
    return s


_zukan_map = None
_zukan_prefixes = ('boss_', 'megaboss_', 'predator_', 'gym_', 'raid_', 'police_')

def _resolve_zukan(item):
    global _zukan_map
    if _zukan_map is None:
        pals = _load_json('characters.json', 'pals')
        _zukan_map = {}
        for p in pals:
            idx = p.get('stats', {}).get('zukan_index')
            if idx and idx > 0:
                _zukan_map[p.get('asset', '').lower()] = idx
    idx = item.get('stats', {}).get('zukan_index')
    if idx and idx > 0:
        return idx
    key = item.get('asset', '').lower()
    # Strip prefix
    for prefix in _zukan_prefixes:
        if key.startswith(prefix):
            key = key[len(prefix):]
            break
    # Progressively strip trailing _tokens until a match
    parts = key.split('_')
    for i in range(len(parts), 0, -1):
        candidate = '_'.join(parts[:i])
        if candidate in _zukan_map:
            return _zukan_map[candidate]
    return 0


def _compute_filter_values(all_data, fg):
    ftype = fg['type']
    field = fg['field']
    if ftype == 'dict_keys':
        vals = set()
        for d in all_data:
            v = d.get(field, {})
            if isinstance(v, dict):
                vals.update(v.keys())
        result = sorted(vals)
        if fg.get('is_element') and 'None' not in result:
            result.append('None')
        return result
    elif ftype == 'field_values':
        vals = set()
        for d in all_data:
            v = d.get(field)
            if v is not None and v != '':
                normalized = _normalize_elem(v) if fg.get('is_element') else v
                vals.add(normalized)
        result = sorted(vals, key=str)
        if fg.get('is_element') and 'None' in result:
            result.remove('None')
            result.append('None')
        return result
    elif ftype == 'int_values':
        return list(fg.get('values', []))
    return []


class CatBtn(QPushButton):
    """Theme-driven category control kept as a named type for tests and styling."""


class WidthFlexibleWidget(QWidget):
    """Let a scroll-area child shrink below its layout's preferred width."""

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setWidth(0)
        return hint

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint


class ResponsiveGrid(WidthFlexibleWidget):
    """Reflow child widgets as the available detail width changes."""

    def __init__(
        self,
        widgets,
        *,
        minimum_column_width=170,
        maximum_columns=3,
        spacing=8,
        parent=None,
    ):
        super().__init__(parent)
        self._widgets = list(widgets)
        self._minimum_column_width = minimum_column_width
        self._maximum_columns = maximum_columns
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._reflow(self._column_count(900))

    def _column_count(self, width):
        return max(
            1,
            min(
                self._maximum_columns,
                max(1, width) // self._minimum_column_width,
            ),
        )

    def _reflow(self, columns):
        if columns == self._columns:
            return
        while self._grid.count():
            self._grid.takeAt(0)
        for index, widget in enumerate(self._widgets):
            row, column = divmod(index, columns)
            self._grid.addWidget(widget, row, column)
        for column in range(columns):
            self._grid.setColumnStretch(column, 1)
        self._columns = columns
        self._grid.invalidate()
        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        self._reflow(self._column_count(event.size().width()))
        super().resizeEvent(event)


class WikiDetailPanel(QScrollArea):
    def __init__(self, category_id, parent=None):
        super().__init__(parent)
        self.setObjectName('wikiDetail')
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self._cat = category_id
        self._cached_data = None
        self._pal_sort_by = 'name'
        self._pal_sort_rev = False
        self._c = WidthFlexibleWidget()
        self._c.setObjectName('wikiDetailContent')
        self._c.setMinimumWidth(0)
        self._c.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._l = QVBoxLayout(self._c)
        self._l.setContentsMargins(24, 22, 24, 28)
        self._l.setSpacing(12)
        self.setWidget(self._c)
        self.show_empty()

    def _clr(self):
        while self._l.count():
            item = self._l.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _label(self, text, object_name, *, wrap=True):
        lbl = QLabel(text)
        lbl.setObjectName(object_name)
        lbl.setWordWrap(wrap)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return lbl

    def _kv(self, k, v):
        return self._info_card(k, _v(v) or '')

    def _card(self, label, value, icon_px=None):
        f = QFrame()
        f.setObjectName('wikiStatCard')
        f.setProperty('wikiStatLabel', label)
        f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lo = QVBoxLayout(f)
        lo.setContentsMargins(12, 10, 12, 10)
        lo.setSpacing(4)
        if icon_px:
            il = QLabel()
            il.setPixmap(icon_px)
            il.setFixedSize(20, 20)
            lo.addWidget(il, 0, Qt.AlignLeft)
        ll = QLabel(label)
        ll.setObjectName('wikiStatLabel')
        ll.setWordWrap(True)
        lo.addWidget(ll)
        vl = QLabel(str(value))
        vl.setObjectName('wikiStatValue')
        vl.setWordWrap(True)
        lo.addWidget(vl)
        return f

    def _badge(self, text):
        l = QLabel(text)
        l.setObjectName('wikiBadge')
        l.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        return l

    def _section(self, title):
        self._l.addWidget(self._label(title, 'wikiSectionTitle'))

    def _description(self, text):
        if text:
            self._l.addWidget(self._label(str(text), 'wikiBodyText'))

    def _identity(
        self,
        name,
        *,
        code='',
        icon_path='',
        pixmap=None,
        icon_size=64,
        badges=None,
        elements=None,
    ):
        header = QFrame()
        header.setObjectName('wikiIdentity')
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(16)

        image = pixmap or (_icon(icon_path, icon_size) if icon_path else None)
        if image:
            image_label = QLabel()
            image_label.setObjectName('wikiIdentityIcon')
            image_label.setPixmap(image)
            image_label.setFixedSize(icon_size, icon_size)
            image_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(image_label, 0, Qt.AlignTop)

        text_box = QWidget()
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(self._label(str(name), 'wikiEntryTitle'), 1)
        for element_name in elements or []:
            element_icon = element_pixmap(str(element_name).lower(), 26)
            if element_icon:
                element_label = QLabel()
                element_label.setPixmap(element_icon)
                element_label.setFixedSize(26, 26)
                element_label.setToolTip(str(element_name))
                title_row.addWidget(element_label, 0, Qt.AlignTop)
        text_layout.addLayout(title_row)

        badge_values = [str(value) for value in badges or [] if value]
        if badge_values:
            badge_row = QHBoxLayout()
            badge_row.setContentsMargins(0, 0, 0, 0)
            badge_row.setSpacing(6)
            for value in badge_values:
                badge_row.addWidget(self._badge(value))
            badge_row.addStretch()
            text_layout.addLayout(badge_row)
        if code:
            text_layout.addWidget(self._label(str(code), 'wikiCodeText'))
        layout.addWidget(text_box, 1, Qt.AlignTop)
        self._l.addWidget(header)

    def _info_card(self, title, subtitle='', *, icon_px=None, trailing=''):
        card = QFrame()
        card.setObjectName('wikiInfoCard')
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(9)
        if icon_px:
            icon_label = QLabel()
            icon_label.setPixmap(icon_px)
            icon_label.setFixedSize(28, 28)
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label, 0, Qt.AlignVCenter)
        text_box = QWidget()
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self._label(str(title), 'wikiInfoTitle'))
        if subtitle not in ('', None):
            text_layout.addWidget(self._label(str(subtitle), 'wikiInfoSubtitle'))
        layout.addWidget(text_box, 1)
        if trailing not in ('', None):
            trailing_label = self._label(str(trailing), 'wikiInfoTrailing', wrap=False)
            layout.addWidget(trailing_label, 0, Qt.AlignVCenter)
        return card

    def _add_grid(
        self,
        widgets,
        *,
        minimum_column_width=170,
        maximum_columns=3,
        spacing=8,
    ):
        widgets = list(widgets)
        if widgets:
            self._l.addWidget(ResponsiveGrid(
                widgets,
                minimum_column_width=minimum_column_width,
                maximum_columns=maximum_columns,
                spacing=spacing,
            ))

    def _add_stats(self, pairs, *, title=None, maximum_columns=4):
        cards = [
            self._card(label, value)
            for label, value in pairs
            if value not in (None, '')
        ]
        if not cards:
            return
        if title:
            self._section(title)
        self._add_grid(
            cards,
            minimum_column_width=145,
            maximum_columns=maximum_columns,
        )

    def _pal_grid(self, pals, show_level=False):
        cards = []
        for pal, level in pals:
            deck = _resolve_zukan(pal)
            subtitle = f'#{deck}' if deck else pal.get('asset', '')
            trailing = f'Lv.{int(level)}' if show_level and level else ''
            cards.append(self._info_card(
                pal.get('name', '?'),
                subtitle,
                icon_px=_icon(pal.get('icon', ''), 28),
                trailing=trailing,
            ))
        self._add_grid(cards, minimum_column_width=210, maximum_columns=3)

    def show_empty(self, message: str | None = None) -> None:
        self._clr()
        empty = QFrame()
        empty.setObjectName('wikiDetailEmpty')
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(24, 80, 24, 24)
        layout.setSpacing(6)
        layout.addStretch()
        title = _tx('docs.wiki.empty_title', 'Select an entry')
        layout.addWidget(self._label(title, 'wikiEmptyTitle'), 0, Qt.AlignHCenter)
        detail = message or _tx(
            'docs.wiki.empty_detail',
            'Choose an item from the results to view its details.',
        )
        layout.addWidget(self._label(detail, 'wikiEmptyText'), 0, Qt.AlignHCenter)
        layout.addStretch()
        self._l.addWidget(empty, 1)

    def _render_pal(self, d):
        name = _get(d, 'name') or ''
        code = _get(d, 'asset') or ''
        elements = _get(d, 'elements') or {}
        work = _get(d, 'work_suitabilities') or {}
        partner = _get(d, 'partner_skill') or ''
        partner_description = (
            _get(d, '_display_description')
            or _get(d, 'description')
            or ''
        )
        stats = _get(d, 'stats') or {}
        zukan = _resolve_zukan(d)
        element_names = list(elements) if isinstance(elements, dict) else []
        self._identity(
            name,
            code=code,
            icon_path=_get(d, 'icon') or '',
            icon_size=96,
            badges=[f'#{zukan}' if zukan else ''],
            elements=element_names,
        )

        size = stats.get('size', '')
        size = str(size).split('::')[-1] if size else ''
        self._add_stats(
            [
                (_tx('docs.wiki.hp', 'HP'), stats.get('hp')),
                (_tx('docs.wiki.melee_atk', 'Melee Atk'), stats.get('melee_attack')),
                (_tx('docs.wiki.shot_atk', 'Shot Atk'), stats.get('shot_attack')),
                (_tx('docs.wiki.defense', 'Defense'), stats.get('defense')),
                (_tx('docs.wiki.rarity', 'Rarity'), stats.get('rarity')),
                (_tx('docs.wiki.food', 'Food'), stats.get('food_amount')),
                (_tx('docs.wiki.size', 'Size'), size),
                (_tx('docs.wiki.run_speed', 'Run Speed'), stats.get('run_speed')),
                (_tx('docs.wiki.ride_sprint', 'Ride Sprint'), stats.get('ride_sprint_speed')),
            ],
            title=_tx('docs.wiki.stats', 'Stats'),
        )

        active_work = {
            key: value
            for key, value in work.items()
            if isinstance(value, (int, float)) and value > 0
        } if isinstance(work, dict) else {}
        if active_work:
            self._section(_tx('docs.wiki.work_suitability', 'Work Suitability'))
            work_cards = []
            for work_id, level in active_work.items():
                display_name = _WORK_SUITABILITY_DISPLAY.get(work_id, work_id)
                work_cards.append(self._info_card(
                    display_name,
                    icon_px=_icon(_work_icon_path(work_id), 28),
                    trailing=f'Lv.{int(level)}',
                ))
            self._add_grid(
                work_cards,
                minimum_column_width=180,
                maximum_columns=3,
            )

        if partner:
            self._section(_tx('docs.wiki.partner_skill', 'Partner Skill'))
            self._add_grid([
                self._info_card(partner, partner_description),
            ], maximum_columns=1)

        moves = _learnset_for_pal(code) if code else []
        if moves:
            self._section(_tx('docs.wiki.skill_set', 'Skill Set'))
            move_cards = []
            for move in moves:
                move_id = move.get('WazaID', '')
                level = move.get('level', '')
                source = move.get('source', '')
                element = _skill_elem_cache(move_id)
                trailing = f'Lv.{level}' if level else ('Egg' if source == 'egg' else '')
                move_cards.append(self._info_card(
                    _skill_name(move_id),
                    element,
                    icon_px=element_pixmap(element.lower(), 24) if element else None,
                    trailing=trailing,
                ))
            self._add_grid(
                move_cards,
                minimum_column_width=220,
                maximum_columns=2,
            )

    def _render_item(self, d):
        name = _get(d, 'name') or ''
        code = _get(d, 'asset') or ''
        desc = _get(d, 'description') or ''
        self._identity(
            name,
            code=code,
            icon_path=_get(d, 'icon') or '',
            icon_size=64,
        )
        self._description(desc)
        self._add_stats(
            [
                (_tx('docs.wiki.category', 'Category'), _get(d, 'type_a_display')),
                (_tx('docs.wiki.subcategory', 'Subcategory'), _get(d, 'type_b_display')),
                (_tx('docs.wiki.rarity', 'Rarity'), _get(d, 'rarity')),
                (_tx('docs.wiki.price', 'Price'), _get(d, 'price')),
                (_tx('docs.wiki.weight', 'Weight'), _get(d, 'weight')),
                (_tx('docs.wiki.max_stack', 'Max Stack'), _get(d, 'max_stack')),
                (_tx('docs.wiki.rank', 'Rank'), _get(d, 'rank')),
                (_tx('docs.wiki.satiety', 'Satiety'), _get(d, 'restore_satiety')),
                (_tx('docs.wiki.sanity', 'Sanity'), _get(d, 'restore_sanity')),
                (_tx('docs.wiki.durability', 'Durability'), _get(d, 'durability')),
            ],
            title=_tx('docs.wiki.details', 'Details'),
        )

    def _render_building(self, d):
        name = _get(d, 'name') or ''
        code = _get(d, 'asset') or ''
        desc = _get(d, 'description') or ''
        sub = _get(d, 'type_a_display')
        badges = [str(sub)] if sub else []
        self._identity(
            name,
            code=code,
            icon_path=_get(d, 'icon') or '',
            icon_size=64,
            badges=badges,
        )
        self._description(desc)
        stats = [
            (_tx('docs.wiki.rank', 'Rank'), _get(d, 'rank')),
            (_tx('docs.wiki.hp', 'HP'), _get(d, 'hp')),
            (_tx('docs.wiki.defense', 'Defense'), _get(d, 'defense')),
            (_tx('docs.wiki.work_required', 'Work Required'), _get(d, 'required_work_amount')),
        ]
        extra = []
        if _get(d, 'belongs_to_base') is not None:
            extra.append((
                _tx('docs.wiki.base_required', 'Base Required'),
                _tx('docs.wiki.yes', 'Yes') if _get(d, 'belongs_to_base')
                else _tx('docs.wiki.no', 'No'),
            ))
        if _get(d, 'install_max_per_base') is not None:
            extra.append((
                _tx('docs.wiki.max_per_base', 'Max per Base'),
                _get(d, 'install_max_per_base'),
            ))
        if _get(d, 'is_paintable') is not None:
            extra.append((
                _tx('docs.wiki.paintable', 'Paintable'),
                _tx('docs.wiki.yes', 'Yes') if _get(d, 'is_paintable')
                else _tx('docs.wiki.no', 'No'),
            ))
        self._add_stats(
            stats + extra,
            title=_tx('docs.wiki.details', 'Details'),
        )
        materials = _get(d, 'materials')
        if isinstance(materials, list) and materials:
            self._section(_tx('docs.wiki.materials', 'Materials'))
            cards = [
                self._info_card(
                    _resolve_item(material.get('id', '?')),
                    trailing=f"x{material.get('count', 0)}",
                )
                for material in materials
            ]
            self._add_grid(cards, minimum_column_width=190, maximum_columns=3)

    def _render_element(self, d):
        name = _get(d, 'name') or ''
        display = _get(d, 'display') or name
        icons = _get(d, 'icons')
        main_icon = None
        if isinstance(icons, dict):
            icon_paths = [value for value in icons.values() if isinstance(value, str)]
            if icon_paths:
                main_icon = icon_paths[min(1, len(icon_paths) - 1)]
        self._identity(
            display,
            code=name,
            icon_path=main_icon or '',
            icon_size=64,
        )

        pals = [(p, None) for p in _pals_by_element(name)]
        if pals:
            if self._pal_sort_by == 'name':
                pals.sort(key=lambda x: x[0].get('name', '').lower(), reverse=self._pal_sort_rev)
            elif self._pal_sort_by == 'index':
                pals.sort(key=lambda x: x[0].get('stats', {}).get('zukan_index', 9999), reverse=self._pal_sort_rev)
            self._section(_tx('docs.wiki.pals_count', 'Pals ({count})', count=len(pals)))
            self._render_pal_sort_bar([
                ('name', _tx('docs.wiki.sort.name', 'Name')),
                ('index', _tx('docs.wiki.sort.index', '#')),
            ])
            self._pal_grid(pals)

    def _render_work(self, d):
        name = _get(d, 'display_name') or _get(d, 'id') or ''
        desc = _get(d, 'description') or ''
        self._identity(
            name,
            code=_get(d, 'id') or '',
            icon_path=_get(d, 'icon') or '',
            icon_size=64,
        )
        self._description(desc)

        work_id = _get(d, 'id')
        pals = _pals_by_work(work_id) if work_id else []
        if pals:
            if self._pal_sort_by == 'name':
                pals.sort(key=lambda x: x[0].get('name', '').lower(), reverse=self._pal_sort_rev)
            elif self._pal_sort_by == 'level':
                pals.sort(key=lambda x: x[1], reverse=self._pal_sort_rev)
            self._section(_tx('docs.wiki.pals_count', 'Pals ({count})', count=len(pals)))
            self._render_pal_sort_bar([
                ('name', _tx('docs.wiki.sort.name', 'Name')),
                ('level', _tx('docs.wiki.sort.work_level', 'Level')),
            ])
            self._pal_grid(pals, show_level=True)

    def _render_pal_sort_bar(self, options):
        w = QWidget()
        w.setObjectName('wikiInlineToolbar')
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 2)
        lo.setSpacing(6)
        combo = QComboBox()
        combo.setObjectName('wikiInlineSort')
        for fid, label in options:
            combo.addItem(label, fid)
        current = combo.findData(self._pal_sort_by)
        combo.setCurrentIndex(max(0, current))
        combo.currentIndexChanged.connect(
            lambda _index, control=combo: self._set_pal_sort(control.currentData())
        )
        lo.addWidget(combo)
        direction = QToolButton()
        direction.setObjectName('wikiSortDirection')
        direction.setIcon(self.style().standardIcon(
            QStyle.SP_ArrowDown if self._pal_sort_rev else QStyle.SP_ArrowUp
        ))
        direction.setToolTip(
            _tx('docs.wiki.sort.descending', 'Descending') if self._pal_sort_rev
            else _tx('docs.wiki.sort.ascending', 'Ascending')
        )
        direction.clicked.connect(self._toggle_pal_sort_direction)
        lo.addWidget(direction)
        lo.addStretch()
        self._l.addWidget(w)

    def _set_pal_sort(self, field):
        if not field or field == self._pal_sort_by:
            return
        self._pal_sort_by = field
        self._pal_sort_rev = False
        if self._cached_data is not None:
            self.show_item(self._cached_data)

    def _toggle_pal_sort_direction(self):
        self._pal_sort_rev = not self._pal_sort_rev
        if self._cached_data is not None:
            self.show_item(self._cached_data)

    def _toggle_pal_sort(self, field):
        if self._pal_sort_by == field:
            self._toggle_pal_sort_direction()
        else:
            self._set_pal_sort(field)

    def _render_active_skill(self, d):
        name = _get(d, 'name') or ''
        code = _get(d, 'asset') or ''
        element = _get(d, 'element') or ''
        desc = _get(d, 'description') or ''
        power = _get(d, 'power')
        cooldown = _get(d, 'cooldown')
        self._identity(
            name,
            code=code,
            pixmap=element_pixmap(element.lower(), 56) if element else None,
            icon_size=56,
            badges=[element],
        )
        self._description(desc)
        wpr = _get(d, 'WazaPowerRate')
        mhn = _get(d, 'MaxHitNum')
        hit_interval = _get(d, 'HitInterval')
        self._add_stats(
            [
                (_tx('docs.wiki.power', 'Power'), power),
                (_tx('docs.wiki.ct', 'CT'), f'{cooldown}s' if cooldown is not None else None),
                (_tx('docs.wiki.hit_power_rate', 'Hit Power Rate'), wpr),
                (_tx('docs.wiki.max_hits', 'Max Hits'), mhn),
                (
                    _tx('docs.wiki.hit_interval', 'Hit Interval'),
                    f'{hit_interval}s' if hit_interval is not None else None,
                ),
            ],
            title=_tx('docs.wiki.stats', 'Stats'),
        )

    def _render_passive_skill(self, d):
        name = _get(d, 'name') or ''
        code = _get(d, 'asset') or ''
        desc = _get(d, '_display_description') or _get(d, 'description') or ''
        rank = _get(d, 'rank')
        self._identity(
            name,
            code=code,
            icon_path=_get(d, 'icon') or '',
            icon_size=56,
            badges=[f"{_tx('docs.wiki.rank', 'Rank')} {rank}" if rank else ''],
        )
        self._description(desc)

        effects = []
        for index in ('1', '2', '3', '4'):
            val = _get(d, f'effect{index}')
            etype = _get(d, f'efftype{index}')
            if val is not None and etype and 'no' not in str(etype).lower():
                numeric_value = float(val)
                if numeric_value != 0:
                    effects.append((_enum_name(etype), numeric_value))
        if effects:
            self._section(_tx('docs.wiki.effects', 'Effects'))
            cards = []
            for effect_type, effect_value in effects:
                sign = '+' if effect_value > 0 else ''
                display_value = (
                    int(effect_value)
                    if effect_value == int(effect_value)
                    else effect_value
                )
                card = self._info_card(
                    effect_type,
                    trailing=f'{sign}{display_value}%',
                )
                card.setProperty(
                    'tone',
                    'positive' if effect_value > 0 else 'negative',
                )
                cards.append(card)
            self._add_grid(cards, minimum_column_width=210, maximum_columns=3)

    def _render_technology(self, d):
        name = _get(d, 'name') or ''
        code = _get(d, 'asset') or ''
        desc = _get(d, 'description') or ''
        cost = _get(d, 'cost')
        level_cap = _get(d, 'level_cap')
        tier = _get(d, 'tier')
        technology_type = _get(d, 'type') or ''
        badges = [
            _tx('docs.wiki.ancient', 'Ancient')
            if technology_type == 'boss' else ''
        ]
        self._identity(
            name,
            code=code,
            icon_path=_get(d, 'icon') or '',
            icon_size=56,
            badges=badges,
        )
        self._description(desc)
        self._add_stats(
            [
                (_tx('docs.wiki.sort.tier', 'Tier'), tier),
                (_tx('docs.wiki.cost', 'Cost'), cost),
                (_tx('docs.wiki.level_cap', 'Level Cap'), level_cap),
            ],
            title=_tx('docs.wiki.details', 'Details'),
        )

        unlock_b = d.get('unlock_build_objects', [])
        unlock_i = d.get('unlock_item_recipes', [])

        def _decode_list(value):
            if not isinstance(value, str):
                return value if isinstance(value, list) else []
            if not value:
                return []
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                LOGGER.warning('Could not decode technology unlock list for %s', code)
                return []
            return decoded if isinstance(decoded, list) else []

        unlock_b = _decode_list(unlock_b)
        unlock_i = _decode_list(unlock_i)

        unlocks_b = [_resolve_item(b) for b in unlock_b]
        unlocks_i = [_resolve_item(i) for i in unlock_i]
        if unlocks_b:
            self._section(_tx('docs.wiki.unlocks_buildings', 'Unlocks Buildings'))
            self._add_grid(
                [self._info_card(unlock) for unlock in unlocks_b],
                minimum_column_width=210,
                maximum_columns=3,
            )
        if unlocks_i:
            self._section(_tx('docs.wiki.unlocks_items', 'Unlocks Items'))
            self._add_grid(
                [self._info_card(unlock) for unlock in unlocks_i],
                minimum_column_width=210,
                maximum_columns=3,
            )

    def _render_generic(self, d):
        name = d.get(
            'name',
            d.get('display_name', d.get('id', _tx('docs.wiki.empty_title', 'Select an entry'))),
        )
        self._identity(
            name,
            code=d.get('asset', ''),
            icon_path=d.get('icon', ''),
            icon_size=64,
        )
        fields = []
        for key, value in d.items():
            if key in ('name', 'asset', 'icon'):
                continue
            if isinstance(value, (str, int, float, bool)):
                fields.append(self._kv(key.replace('_', ' ').title(), value))
            elif (
                isinstance(value, list)
                and value
                and all(isinstance(item, str) for item in value)
            ):
                fields.append(self._kv(
                    key.replace('_', ' ').title(),
                    ', '.join(value),
                ))
        if fields:
            self._section(_tx('docs.wiki.details', 'Details'))
            self._add_grid(fields, minimum_column_width=220, maximum_columns=2)

    def show_item(self, data: dict | None) -> None:
        self._clr()
        self._cached_data = data
        if not isinstance(data, dict) or not data:
            self.show_empty()
            return
        if self._cat == 'pals':
            self._render_pal(data)
        elif self._cat == 'items':
            self._render_item(data)
        elif self._cat == 'buildings':
            self._render_building(data)
        elif self._cat == 'elements':
            self._render_element(data)
        elif self._cat == 'work_suitability':
            self._render_work(data)
        elif self._cat == 'active_skills':
            self._render_active_skill(data)
        elif self._cat == 'passive_skills':
            self._render_passive_skill(data)
        elif self._cat == 'technologies':
            self._render_technology(data)
        else:
            self._render_generic(data)
        self._l.addStretch(1)
        self.verticalScrollBar().setValue(0)


class WikiCategoryPage(QWidget):
    def __init__(self, category_id, parent=None):
        super().__init__(parent)
        self._cat = category_id
        self._all_data = []
        self._loaded = False
        self._config = _CATEGORY_CONFIG.get(category_id, {})
        self._sort_by = None
        self._sort_reverse = False
        self._sort_fields = {}
        self._sort_labels = {}
        self._filter_groups = []
        self._active_filters = {}
        self._filter_combos = {}
        self._filter_values_cache = {}
        self._filtered_indices = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setObjectName('wikiContentSplitter')
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(1)

        browser = QFrame()
        browser.setObjectName('wikiBrowserPane')
        browser_layout = QVBoxLayout(browser)
        browser_layout.setContentsMargins(14, 14, 14, 12)
        browser_layout.setSpacing(9)

        self._category_title = QLabel()
        self._category_title.setObjectName('wikiBrowserTitle')
        browser_layout.addWidget(self._category_title)

        self._search = QLineEdit()
        self._search.setObjectName('wikiSearch')
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(
            lambda: self._apply_sort_filter() if self._loaded else None
        )
        browser_layout.addWidget(self._search)

        sort_cfg = self._config.get('sort_fields', [])
        self._sort_fields = {sid: fn for sid, _, fn in sort_cfg}
        self._sort_labels = {sid: label for sid, label, _ in sort_cfg}
        if sort_cfg:
            sort_row = QWidget()
            sort_row.setObjectName('wikiSortRow')
            sort_layout = QHBoxLayout(sort_row)
            sort_layout.setContentsMargins(0, 0, 0, 0)
            sort_layout.setSpacing(6)
            self._sort_combo = QComboBox()
            self._sort_combo.setObjectName('wikiSortCombo')
            self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
            sort_layout.addWidget(self._sort_combo, 1)
            self._sort_direction = QToolButton()
            self._sort_direction.setObjectName('wikiSortDirection')
            self._sort_direction.setCursor(QCursor(Qt.PointingHandCursor))
            self._sort_direction.clicked.connect(self._toggle_sort_direction)
            sort_layout.addWidget(self._sort_direction)
            browser_layout.addWidget(sort_row)
        else:
            self._sort_combo = None
            self._sort_direction = None

        self._filter_groups = self._config.get('filter_groups', [])
        self._filter_section = QWidget()
        self._filter_section.setObjectName('wikiFilterSection')
        self._filter_layout = QVBoxLayout(self._filter_section)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_layout.setSpacing(6)
        if self._filter_groups:
            browser_layout.addWidget(self._filter_section)

        results_header = QWidget()
        results_layout = QHBoxLayout(results_header)
        results_layout.setContentsMargins(1, 2, 1, 0)
        results_layout.setSpacing(6)
        self._result_count = QLabel()
        self._result_count.setObjectName('wikiResultCount')
        results_layout.addWidget(self._result_count)
        results_layout.addStretch()
        self._reset_button = QToolButton()
        self._reset_button.setObjectName('wikiResetButton')
        self._reset_button.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        self._reset_button.setCursor(QCursor(Qt.PointingHandCursor))
        self._reset_button.clicked.connect(self.reset_controls)
        results_layout.addWidget(self._reset_button)
        browser_layout.addWidget(results_header)

        self._list = QListWidget()
        self._list.setObjectName('wikiResults')
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.currentItemChanged.connect(self._on_sel)
        self._list.setSpacing(0)
        self._list.setIconSize(QSize(36, 36))
        self._list.setUniformItemSizes(True)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        empty_results = QFrame()
        empty_results.setObjectName('wikiResultsEmpty')
        empty_layout = QVBoxLayout(empty_results)
        empty_layout.setContentsMargins(18, 30, 18, 30)
        empty_layout.addStretch()
        self._empty_results_label = QLabel()
        self._empty_results_label.setObjectName('wikiEmptyText')
        self._empty_results_label.setWordWrap(True)
        self._empty_results_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self._empty_results_label)
        empty_layout.addStretch()

        self._results_stack = QStackedWidget()
        self._results_stack.setObjectName('wikiResultsStack')
        self._results_stack.addWidget(self._list)
        self._results_stack.addWidget(empty_results)
        browser_layout.addWidget(self._results_stack, 1)

        browser.setMinimumWidth(260)
        browser.setMaximumWidth(390)
        self._splitter.addWidget(browser)

        self._detail = WikiDetailPanel(self._cat)
        self._splitter.addWidget(self._detail)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([310, 650])
        layout.addWidget(self._splitter, 1)
        self.refresh_labels()

    def _build_filter_group_widget(self, fg):
        values = _compute_filter_values(self._all_data, fg)
        if not values:
            return None
        self._filter_values_cache[fg['id']] = values
        combo = QComboBox()
        combo.setObjectName('wikiFilterCombo')
        label = _tx(fg['label_key'], fg['id'].replace('_', ' ').title())
        combo.addItem(_tx('docs.wiki.filter.all', 'All {label}', label=label), None)
        for value in values:
            display = self._filter_display(fg, value)
            if fg.get('is_element'):
                pixmap = element_pixmap(_normalize_elem(value).lower(), 20)
                if pixmap:
                    combo.addItem(QIcon(pixmap), display, value)
                    continue
            combo.addItem(display, value)
        combo.currentIndexChanged.connect(
            lambda _index, group_id=fg['id'], control=combo:
            self._on_filter_changed(group_id, control.currentData())
        )
        self._filter_combos[fg['id']] = combo
        return combo

    @staticmethod
    def _filter_display(fg, value):
        value_keys = fg.get('value_keys', {})
        if value in value_keys:
            return _tx(value_keys[value], str(value))
        return str(value)

    def load(self):
        category_index = [category[0] for category in _CATEGORIES].index(self._cat)
        _, _, filename, data_key = _CATEGORIES[category_index]
        items = _load_json(filename, data_key)
        if not isinstance(items, list):
            _DATA_ERRORS[filename] = f'Wiki category {data_key} must be a list.'
        if filename in _DATA_ERRORS:
            self._all_data = []
            self._loaded = True
            self._list.clear()
            message = _DATA_ERRORS[filename]
            self._empty_results_label.setText(message)
            self._results_stack.setCurrentIndex(1)
            self._set_result_count(0)
            self._detail.show_empty(message)
            return
        if self._cat == 'work_suitability':
            for item in items:
                fixed = _work_icon(item.get('id', ''))
                if fixed:
                    item['icon'] = fixed
        self._all_data = prepare_wiki_entries(self._cat, items)
        self._loaded = True
        self._active_filters = {}
        self._filter_combos = {}
        while self._filter_layout.count():
            item = self._filter_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for filter_group in self._filter_groups:
            combo = self._build_filter_group_widget(filter_group)
            if combo:
                self._filter_layout.addWidget(combo)
        self._apply_sort_filter()

    def _apply_sort_filter(self):
        if not self._loaded:
            return

        current_item = self._list.currentItem()
        current_index = current_item.data(Qt.UserRole) if current_item else None
        query_terms = self._search.text().casefold().split()
        indices = list(range(len(self._all_data)))

        if query_terms:
            search_fields = (
                'name',
                'asset',
                'display_name',
                'display',
                'id',
                'description',
                '_display_description',
                'partner_skill',
                'type_a_display',
                'type_b_display',
            )
            indices = [
                index
                for index in indices
                if all(
                    term in ' '.join(
                        str(self._all_data[index].get(field) or '')
                        for field in search_fields
                    ).casefold()
                    for term in query_terms
                )
            ]

        for filter_group in self._filter_groups:
            active_value = self._active_filters.get(filter_group['id'])
            if active_value is None:
                continue
            indices = [
                index
                for index in indices
                if self._item_matches_filter(
                    self._all_data[index],
                    filter_group,
                    active_value,
                )
            ]

        if self._sort_by is not None and self._sort_by in self._sort_fields:
            key_fn = self._sort_fields[self._sort_by]
            indices.sort(
                key=lambda index, field=key_fn: field(self._all_data[index]),
                reverse=self._sort_reverse,
            )

        self._filtered_indices = indices
        self._rebuild_list()
        self._set_result_count(len(indices))
        self._reset_button.setEnabled(self._has_active_controls())
        if not indices:
            self._results_stack.setCurrentIndex(1)
            self._detail.show_empty(_tx(
                'docs.wiki.no_results_detail',
                'Try a different search or filter.',
            ))
            return

        self._results_stack.setCurrentIndex(0)
        selected_row = 0
        if current_index in indices:
            selected_row = indices.index(current_index)
        self._list.setCurrentRow(selected_row)
        selected = self._list.item(selected_row)
        if selected:
            data_index = selected.data(Qt.UserRole)
            if data_index is not None and data_index < len(self._all_data):
                self._detail.show_item(self._all_data[data_index])

    def _set_result_count(self, count: int) -> None:
        self._result_count.setText(_tx(
            'docs.wiki.result_count',
            '{count} results',
            count=count,
        ))

    def _has_active_controls(self) -> bool:
        return bool(
            self._search.text()
            or self._sort_by is not None
            or any(value is not None for value in self._active_filters.values())
        )

    def _item_matches_filter(self, item, fg, active_val):
        ftype = fg['type']
        field = fg['field']
        if ftype == 'dict_keys':
            v = item.get(field, {})
            if active_val == 'None':
                return not isinstance(v, dict) or len(v) == 0
            return isinstance(v, dict) and active_val in v
        elif ftype == 'field_values':
            raw = item.get(field)
            if raw is None or raw == '':
                return active_val == 'None'
            check = _normalize_elem(raw) if fg.get('is_element') else raw
            return str(check) == str(active_val)
        elif ftype == 'int_values':
            raw = item.get(field)
            if raw is None:
                return False
            try:
                return int(raw) == int(active_val)
            except (ValueError, TypeError):
                return False
        return True

    def _rebuild_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        for data_index in self._filtered_indices:
            item = self._all_data[data_index]
            name = item.get(
                'display',
                item.get('name', item.get('display_name', item.get('id', '?'))),
            )
            icon_path = item.get('icon', '')
            if not icon_path and self._cat == 'elements':
                icons = item.get('icons', {})
                icon_paths = [
                    value for value in icons.values() if isinstance(value, str)
                ] if isinstance(icons, dict) else []
                if icon_paths:
                    icon_path = icon_paths[min(1, len(icon_paths) - 1)]
            title = str(name)
            if self._cat == 'pals':
                deck = _resolve_zukan(item)
                title = f'#{deck}  {name}' if deck else title
            subtitle = self._result_subtitle(item)
            list_item = QListWidgetItem(
                f'{title}\n{subtitle}' if subtitle else title
            )
            list_item.setData(Qt.UserRole, data_index)
            list_item.setToolTip(title)
            list_item.setSizeHint(QSize(0, 54 if subtitle else 46))
            if self._cat == 'active_skills':
                element = item.get('element', '')
                pixmap = element_pixmap(element.lower(), 30) if element else None
            else:
                pixmap = _icon(icon_path, 36)
            if pixmap:
                list_item.setIcon(QIcon(pixmap))
            self._list.addItem(list_item)
        self._list.blockSignals(False)

    def _result_subtitle(self, item):
        if self._cat == 'pals':
            elements = item.get('elements', {})
            return ' | '.join(elements) if isinstance(elements, dict) else ''
        if self._cat == 'items':
            return ' | '.join(str(value) for value in (
                item.get('type_a_display'),
                item.get('rarity'),
            ) if value not in (None, ''))
        if self._cat == 'buildings':
            return str(item.get('type_a_display') or '')
        if self._cat == 'active_skills':
            values = [item.get('element')]
            if item.get('power') is not None:
                values.append(f"{_tx('docs.wiki.power', 'Power')} {item['power']}")
            return ' | '.join(str(value) for value in values if value)
        if self._cat == 'passive_skills' and item.get('rank') is not None:
            return f"{_tx('docs.wiki.rank', 'Rank')} {item['rank']}"
        if self._cat == 'technologies':
            return ' | '.join(str(value) for value in (
                f"{_tx('docs.wiki.sort.tier', 'Tier')} {item['tier']}"
                if item.get('tier') is not None else '',
                f"{_tx('docs.wiki.level_cap', 'Level Cap')} {item['level_cap']}"
                if item.get('level_cap') is not None else '',
            ) if value)
        return str(item.get('id') or '')

    def _toggle_sort(self, field_id):
        if self._sort_combo is None:
            return
        if self._sort_by == field_id:
            self._toggle_sort_direction()
            return
        index = self._sort_combo.findData(field_id)
        if index >= 0:
            self._sort_combo.setCurrentIndex(index)

    def _on_sort_changed(self, _index):
        if self._sort_combo is None:
            return
        self._sort_by = self._sort_combo.currentData()
        if self._sort_by is None:
            self._sort_reverse = False
        self._update_sort_direction()
        if self._loaded:
            self._apply_sort_filter()

    def _toggle_sort_direction(self):
        if self._sort_by is None:
            return
        self._sort_reverse = not self._sort_reverse
        self._update_sort_direction()
        self._apply_sort_filter()

    def _update_sort_direction(self):
        if self._sort_direction is None:
            return
        self._sort_direction.setEnabled(self._sort_by is not None)
        self._sort_direction.setIcon(self.style().standardIcon(
            QStyle.SP_ArrowDown if self._sort_reverse else QStyle.SP_ArrowUp
        ))
        self._sort_direction.setToolTip(
            _tx('docs.wiki.sort.descending', 'Descending') if self._sort_reverse
            else _tx('docs.wiki.sort.ascending', 'Ascending')
        )

    def _toggle_filter(self, group_id, value):
        combo = self._filter_combos.get(group_id)
        if combo is None:
            return
        target = None if self._active_filters.get(group_id) == value else value
        index = combo.findData(target)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _on_filter_changed(self, group_id, value):
        self._active_filters[group_id] = value
        if self._loaded:
            self._apply_sort_filter()

    def reset_controls(self) -> None:
        controls = [self._search]
        if self._sort_combo is not None:
            controls.append(self._sort_combo)
        controls.extend(self._filter_combos.values())
        for control in controls:
            control.blockSignals(True)
        self._search.clear()
        self._sort_by = None
        self._sort_reverse = False
        if self._sort_combo is not None:
            self._sort_combo.setCurrentIndex(0)
        self._active_filters = {
            group_id: None for group_id in self._filter_combos
        }
        for combo in self._filter_combos.values():
            combo.setCurrentIndex(0)
        for control in controls:
            control.blockSignals(False)
        self._update_sort_direction()
        if self._loaded:
            self._apply_sort_filter()

    def focus_search(self) -> None:
        self._search.setFocus(Qt.ShortcutFocusReason)
        self._search.selectAll()

    def clear_search(self) -> None:
        if self._search.text():
            self._search.clear()

    def _on_sel(self, current, _previous):
        if not current:
            return
        data_index = current.data(Qt.UserRole)
        if data_index is not None and data_index < len(self._all_data):
            self._detail.show_item(self._all_data[data_index])

    def refresh_labels(self) -> None:
        category_spec = next(
            category for category in _CATEGORIES if category[0] == self._cat
        )
        category_title = _tx(category_spec[1], self._cat.replace('_', ' ').title())
        self._category_title.setText(category_title)
        self._search.setPlaceholderText(_tx(
            'docs.wiki.search_category',
            'Search {category}',
            category=category_title,
        ))
        self._empty_results_label.setText(_tx(
            'docs.wiki.no_results',
            'No matching entries',
        ))
        self._reset_button.setToolTip(_tx(
            'docs.wiki.reset',
            'Reset search, sort, and filters',
        ))

        if self._sort_combo is not None:
            selected = self._sort_by
            self._sort_combo.blockSignals(True)
            self._sort_combo.clear()
            self._sort_combo.addItem(
                _tx('docs.wiki.sort.default', 'Default order'),
                None,
            )
            for field_id, label_key in self._sort_labels.items():
                default = field_id.replace('_', ' ').title()
                self._sort_combo.addItem(_tx(label_key, default), field_id)
            selected_index = self._sort_combo.findData(selected)
            self._sort_combo.setCurrentIndex(max(0, selected_index))
            self._sort_combo.blockSignals(False)
            self._update_sort_direction()

        for filter_group in self._filter_groups:
            combo = self._filter_combos.get(filter_group['id'])
            if combo is None:
                continue
            selected = combo.currentData()
            label = _tx(
                filter_group['label_key'],
                filter_group['id'].replace('_', ' ').title(),
            )
            combo.setItemText(
                0,
                _tx('docs.wiki.filter.all', 'All {label}', label=label),
            )
            values = self._filter_values_cache.get(filter_group['id'], [])
            for index, value in enumerate(values, start=1):
                combo.setItemText(index, self._filter_display(filter_group, value))
            selected_index = combo.findData(selected)
            if selected_index >= 0:
                combo.setCurrentIndex(selected_index)

        self._set_result_count(len(self._filtered_indices))
        current = self._list.currentItem()
        if current:
            data_index = current.data(Qt.UserRole)
            if data_index is not None and data_index < len(self._all_data):
                self._detail.show_item(self._all_data[data_index])


class WikiTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('wikiWorkspace')
        self.parent_window = parent
        self._pages = {}
        self._current_category = None
        self._setup_ui()
        self._setup_shortcuts()
        if _CATEGORIES:
            self._switch_category(_CATEGORIES[0][0])

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        category_rail = QFrame()
        category_rail.setObjectName('wikiCategoryRail')
        category_layout = QVBoxLayout(category_rail)
        category_layout.setContentsMargins(12, 16, 12, 12)
        category_layout.setSpacing(5)

        self._browse_label = QLabel()
        self._browse_label.setObjectName('wikiRailTitle')
        category_layout.addWidget(self._browse_label)
        category_layout.addSpacing(4)

        self._cat_btns = {}
        for cat_id, i18n_key, *_ in _CATEGORIES:
            button = CatBtn()
            button.setProperty('wikiCategory', True)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setCursor(QCursor(Qt.PointingHandCursor))
            button.setMinimumHeight(40)
            button.clicked.connect(
                lambda _checked=False, category=cat_id:
                self._switch_category(category)
            )
            self._cat_btns[cat_id] = button
            category_layout.addWidget(button)

        category_layout.addStretch()
        category_rail.setFixedWidth(174)
        layout.addWidget(category_rail)

        self._cat_stack = QStackedWidget()
        self._cat_stack.setObjectName('wikiCategoryStack')
        for cat_id, *_ in _CATEGORIES:
            page = WikiCategoryPage(cat_id)
            self._pages[cat_id] = page
            self._cat_stack.addWidget(page)
        layout.addWidget(self._cat_stack, 1)
        self.refresh_labels()

    def _setup_shortcuts(self):
        find_action = QAction(self)
        find_action.setShortcut(QKeySequence.Find)
        find_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        find_action.triggered.connect(self.focus_search)
        self.addAction(find_action)

        clear_action = QAction(self)
        clear_action.setShortcut(QKeySequence(Qt.Key_Escape))
        clear_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        clear_action.triggered.connect(self.clear_search)
        self.addAction(clear_action)

    def _switch_category(self, cat_id):
        if cat_id in self._pages:
            self._current_category = cat_id
            category_index = [
                category[0] for category in _CATEGORIES
            ].index(cat_id)
            self._cat_stack.setCurrentIndex(category_index)
            page = self._pages[cat_id]
            if not page._loaded:
                page.load()
            self._cat_btns[cat_id].setChecked(True)

    def refresh(self) -> None:
        if self._current_category:
            self._pages[self._current_category].refresh_labels()

    def focus_search(self) -> None:
        if self._current_category:
            self._pages[self._current_category].focus_search()

    def clear_search(self) -> None:
        if self._current_category:
            self._pages[self._current_category].clear_search()

    def refresh_labels(self) -> None:
        self._browse_label.setText(_tx('docs.wiki.browse', 'Browse'))
        for cat_id, i18n_key, *_ in _CATEGORIES:
            if cat_id in self._cat_btns:
                default = cat_id.replace('_', ' ').title()
                self._cat_btns[cat_id].setText(_tx(i18n_key, default))
            if cat_id in self._pages:
                self._pages[cat_id].refresh_labels()
