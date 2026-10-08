"""Dark-Mode-Theme fuer die GENESIS Referenz-UI (Originalauftrag §4).

Bewusst als einfaches, zentrales Qt-Stylesheet gehalten (kein externes
CSS-Framework noetig - Prinzip: Open Source, keine unnoetigen
Abhaengigkeiten). Farben orientieren sich an gaengigen modernen
Dark-Mode-Paletten professioneller Medien-/Entwicklertools.
"""

BACKGROUND = "#121417"
SURFACE = "#1b1e23"
SURFACE_ALT = "#22262c"
BORDER = "#2c3138"
TEXT_PRIMARY = "#e8eaed"
TEXT_SECONDARY = "#9aa0a6"
ACCENT = "#4f8cff"
ACCENT_HOVER = "#6ba0ff"
WARNING = "#f2b84b"
ERROR = "#f2545b"
SUCCESS = "#4bd18a"

DARK_STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
    font-size: 13px;
}}

QMainWindow {{
    background-color: {BACKGROUND};
}}

#Sidebar {{
    background-color: {SURFACE};
    border-right: 1px solid {BORDER};
}}

#TopBar {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}

QTreeWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QTreeWidget::item {{
    padding: 6px 4px;
    border-radius: 4px;
}}

QTreeWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

QTreeWidget::item:hover:!selected {{
    background-color: {SURFACE_ALT};
}}

QLineEdit {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
}}

QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

QPushButton {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    color: {TEXT_PRIMARY};
}}

QPushButton:hover {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: white;
}}

QPushButton#Primary {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: white;
    font-weight: 600;
}}

QPushButton#Primary:hover {{
    background-color: {ACCENT_HOVER};
}}

QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QLabel#CardValue {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

QLabel#CardLabel {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLabel#SectionTitle {{
    font-size: 18px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

QTableWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
}}

QHeaderView::section {{
    background-color: {SURFACE_ALT};
    color: {TEXT_SECONDARY};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {BORDER};
}}

QScrollBar:vertical {{
    background: {BACKGROUND};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
}}

QStatusBar {{
    background-color: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
}}
"""
