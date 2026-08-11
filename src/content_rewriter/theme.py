BACKGROUND = "#0B0D12"
SURFACE = "#12151D"
SURFACE_RAISED = "#171B26"
BORDER = "#232838"
BORDER_ACTIVE = "#3D46FF"
TEXT = "#E6E9F2"
TEXT_MUTED = "#8B93A7"
ACCENT = "#6D5EF8"
ACCENT_ALT = "#22D3EE"
SUCCESS = "#34D399"
DANGER = "#F87171"

FONT_STACK = '"Inter", "SF Pro Text", "Segoe UI", "Helvetica Neue", Arial, sans-serif'

STYLESHEET = f"""
QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: {FONT_STACK};
    font-size: 14px;
}}

QMainWindow, QWidget#root {{
    background: {BACKGROUND};
}}

QLabel#title {{
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.6px;
}}

QLabel#subtitle {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}

QLabel#cardLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.4px;
}}

QLabel#statusText {{
    color: {TEXT_MUTED};
    font-size: 12.5px;
}}

QLabel#metaText {{
    color: {TEXT_MUTED};
    font-size: 11.5px;
}}

QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 18px;
}}

QFrame#card[dragging="true"] {{
    border: 1px solid {BORDER_ACTIVE};
    background: #151A2B;
}}

QFrame#banner {{
    border-radius: 14px;
    border: 1px solid {BORDER};
    background: {SURFACE_RAISED};
}}

QFrame#banner[tone="error"] {{
    border: 1px solid #4A2230;
    background: #21131A;
}}

QFrame#banner[tone="success"] {{
    border: 1px solid #1F4034;
    background: #0F1F1B;
}}

QLabel#bannerText {{
    font-size: 13px;
}}

QFrame#chip {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QLabel#chipText {{
    font-size: 12.5px;
    color: {TEXT};
}}

QTextEdit {{
    background: transparent;
    border: none;
    color: {TEXT};
    font-size: 14.5px;
    line-height: 165%;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}

QTextEdit#result {{
    color: #D7DCEC;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}

QScrollBar::handle:vertical {{
    background: #2A3146;
    border-radius: 5px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background: #39415C;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}

QPushButton {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 11px;
    padding: 9px 18px;
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}

QPushButton:hover {{
    background: #1E2334;
    border: 1px solid #333B52;
}}

QPushButton:pressed {{
    background: #171B29;
}}

QPushButton:disabled {{
    color: #4E566B;
    background: #10131B;
    border: 1px solid #1B2030;
}}

QPushButton#primary {{
    background: {ACCENT};
    border: none;
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 700;
    padding: 13px 30px;
    border-radius: 13px;
}}

QPushButton#primary:hover {{
    background: #8073FF;
}}

QPushButton#primary:pressed {{
    background: #5646DC;
}}

QPushButton#primary:disabled {{
    background: #1B2030;
    color: #545C73;
}}

QPushButton#ghost {{
    background: transparent;
    border: 1px solid transparent;
    color: {TEXT_MUTED};
    padding: 6px 10px;
}}

QPushButton#ghost:hover {{
    color: {TEXT};
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
}}

QProgressBar {{
    background: #171B26;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    border-radius: 3px;
    background: {ACCENT};
}}

QToolTip {{
    background: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
}}
"""
