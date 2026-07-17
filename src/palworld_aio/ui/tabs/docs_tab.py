from PySide6.QtWidgets import QVBoxLayout, QWidget

from palworld_aio.ui.tabs.docs.wiki_tab import WikiTab


class DocsTab(QWidget):
    """Built-in game-data wiki, available without a loaded world."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.wiki_tab = WikiTab(self)
        layout.addWidget(self.wiki_tab)

    def refresh(self) -> None:
        self.wiki_tab.refresh()

    def refresh_labels(self) -> None:
        self.wiki_tab.refresh_labels()
