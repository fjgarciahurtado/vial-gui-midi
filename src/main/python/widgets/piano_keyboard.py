# SPDX-License-Identifier: GPL-2.0-or-later

from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy

from keycodes.keycodes import Keycode, KEYCODES_MIDI_NOTES_ACTIVE
from util import tr

# (label shown on the key, fragment used to build the QMK id, black key)
NOTES = [
    ("C", "C", False),
    ("C#", "Cs", True),
    ("D", "D", False),
    ("D#", "Ds", True),
    ("E", "E", False),
    ("F", "F", False),
    ("F#", "Fs", True),
    ("G", "G", False),
    ("G#", "Gs", True),
    ("A", "A", False),
    ("A#", "As", True),
    ("B", "B", False),
]

# MI_C..MI_B are the base octave, MI_C_1..MI_B_5 are the five octaves above it
OCTAVE_COUNT = 6
WHITE_PER_OCTAVE = 7
VISIBLE_OCTAVES = 3

BLACK_WIDTH_RATIO = 0.62
BLACK_HEIGHT_RATIO = 0.62
WHITE_ASPECT = 4.0


def note_qmk_id(note_fragment, octave):
    """ MI_C for the base octave, MI_C_3 for the octaves above it """
    if octave == 0:
        return "MI_{}".format(note_fragment)
    return "MI_{}_{}".format(note_fragment, octave)


def octave_name(octave):
    return "Base" if octave == 0 else str(octave)


class PianoKey(QPushButton):

    def __init__(self, keycode, label, black, parent=None):
        super().__init__(parent)

        self.keycode = keycode
        self.black = black
        self.setText(label)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(Keycode.tooltip(keycode.qmk_id))
        # drives the stylesheet selectors below
        self.setProperty("black", "true" if black else "false")


class KeyArea(QWidget):
    """ Holds the piano keys, which are positioned manually so black keys can overlap white ones """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.white_keys = []
        self.black_keys = []

    def clear(self):
        for btn in self.buttons():
            btn.hide()
            btn.deleteLater()
        self.white_keys = []
        self.black_keys = []

    def buttons(self):
        # black keys are stored alongside the index of the white key they are anchored to
        return self.white_keys + [btn for _, btn in self.black_keys]

    def key_metrics(self):
        width = max(20, int(round(self.fontMetrics().height() * 1.6)))
        return width, int(round(width * WHITE_ASPECT))

    def relayout(self):
        white_w, height = self.key_metrics()
        black_w = int(round(white_w * BLACK_WIDTH_RATIO))
        black_h = int(round(height * BLACK_HEIGHT_RATIO))

        self.setFixedSize(max(white_w * len(self.white_keys), white_w), height)

        for idx, btn in enumerate(self.white_keys):
            btn.setGeometry(idx * white_w, 0, white_w, height)

        # a black key sits on the boundary between the white key it follows and the next one
        for white_idx, btn in self.black_keys:
            btn.setGeometry(int(round((white_idx + 1) * white_w - black_w / 2)), 0, black_w, black_h)
            btn.raise_()

        return black_h


class PianoKeyboard(QWidget):
    """ Piano-style picker for MIDI note keycodes.

    Exposes the same interface as DisplayKeyboard so it can be used as a Tab alternative.
    """

    keycode_changed = pyqtSignal(str)

    def __init__(self, visible_octaves=VISIBLE_OCTAVES):
        super().__init__()

        self.visible_octaves = visible_octaves
        self.offset = 0
        self.active_octaves = []
        self.keycode_filter = None
        self.applied_padding = None

        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.prev_btn = QPushButton("<")
        self.prev_btn.setFocusPolicy(Qt.NoFocus)
        self.prev_btn.clicked.connect(lambda: self.shift(-1))
        self.next_btn = QPushButton(">")
        self.next_btn.setFocusPolicy(Qt.NoFocus)
        self.next_btn.clicked.connect(lambda: self.shift(1))
        self.range_lbl = QLabel()

        # the arrows only change which octaves are drawn, they do not transpose the keyboard
        nav_tooltip = tr("PianoKeyboard",
                         "Chooses which octaves are displayed. This only affects this view - to change the "
                         "octave the keyboard actually plays, assign the MIDI Oct keycodes.")
        for w in (self.prev_btn, self.next_btn, self.range_lbl):
            w.setToolTip(nav_tooltip)

        self.nav = QHBoxLayout()
        self.nav.setContentsMargins(0, 0, 0, 0)
        self.nav.addStretch()
        self.nav.addWidget(self.prev_btn)
        self.nav.addWidget(self.range_lbl)
        self.nav.addWidget(self.next_btn)
        self.nav.addStretch()

        self.key_area = KeyArea(self)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.nav)
        layout.addWidget(self.key_area)
        layout.setAlignment(self.key_area, Qt.AlignHCenter)
        self.setLayout(layout)

        self.recreate_keys(None)

    def available_keycodes(self):
        """ qmk_id -> Keycode for every MIDI note the keyboard supports and the filter allows """
        available = {}
        for keycode in KEYCODES_MIDI_NOTES_ACTIVE:
            if keycode.hidden:
                continue
            if self.keycode_filter is not None and not self.keycode_filter(keycode.qmk_id):
                continue
            available[keycode.qmk_id] = keycode
        return available

    def recreate_keys(self, keycode_filter):
        self.keycode_filter = keycode_filter
        available = self.available_keycodes()

        self.active_octaves = [
            octave for octave in range(OCTAVE_COUNT)
            if any(note_qmk_id(fragment, octave) in available for _, fragment, _ in NOTES)
        ]

        max_offset = max(0, len(self.active_octaves) - self.visible_octaves)
        self.offset = min(self.offset, max_offset)

        self.rebuild(available)

    def visible_octave_list(self):
        return self.active_octaves[self.offset:self.offset + self.visible_octaves]

    def rebuild(self, available=None):
        if available is None:
            available = self.available_keycodes()

        self.key_area.clear()
        self.applied_padding = None

        white_index = 0
        for octave in self.visible_octave_list():
            for label, fragment, black in NOTES:
                keycode = available.get(note_qmk_id(fragment, octave))
                if black:
                    # a black key is anchored to the white key before it, which must exist
                    if keycode is not None and white_index > 0:
                        btn = self.make_key(keycode, label, octave, True)
                        self.key_area.black_keys.append((white_index - 1, btn))
                else:
                    if keycode is not None:
                        btn = self.make_key(keycode, label, octave, False)
                        self.key_area.white_keys.append(btn)
                        white_index += 1

        black_h = self.key_area.relayout()
        self.apply_stylesheet(black_h)
        self.update_nav()

    def make_key(self, keycode, label, octave, black):
        text = label if octave == 0 else "{}{}".format(label, octave)
        btn = PianoKey(keycode, text, black, self.key_area)
        btn.clicked.connect(lambda _, k=keycode: self.keycode_changed.emit(k.qmk_id))
        btn.show()
        return btn

    def update_nav(self):
        octaves = self.visible_octave_list()
        navigable = len(self.active_octaves) > self.visible_octaves

        for w in (self.prev_btn, self.next_btn, self.range_lbl):
            w.setVisible(navigable)

        if not octaves:
            self.range_lbl.setText("")
            return

        if len(octaves) == 1:
            self.range_lbl.setText(tr("PianoKeyboard", "Octave {}").format(octave_name(octaves[0])))
        else:
            self.range_lbl.setText(tr("PianoKeyboard", "Octaves {} - {}").format(
                octave_name(octaves[0]), octave_name(octaves[-1])))

        self.prev_btn.setEnabled(self.offset > 0)
        self.next_btn.setEnabled(self.offset + self.visible_octaves < len(self.active_octaves))

    def shift(self, delta):
        max_offset = max(0, len(self.active_octaves) - self.visible_octaves)
        offset = min(max(self.offset + delta, 0), max_offset)
        if offset != self.offset:
            self.offset = offset
            self.rebuild()

    def apply_stylesheet(self, black_h):
        if self.applied_padding == black_h:
            return
        self.applied_padding = black_h

        palette = self.palette()
        dark = palette.color(QPalette.Window).lightness() < 128
        if dark:
            white_bg, white_fg, black_bg, black_fg, border = "#d6d6d6", "#101010", "#0d0d0d", "#e0e0e0", "#5a5a5a"
        else:
            white_bg, white_fg, black_bg, black_fg, border = "#ffffff", "#101010", "#1e1e1e", "#f0f0f0", "#808080"
        highlight = palette.color(QPalette.Highlight).name()
        highlight_text = palette.color(QPalette.HighlightedText).name()

        # labels are pushed below the black keys so they stay readable on the white key tails
        self.key_area.setStyleSheet("""
            PianoKey[black="false"] {{
                background-color: {white_bg}; color: {white_fg};
                border: 1px solid {border}; border-top: none;
                border-bottom-left-radius: 3px; border-bottom-right-radius: 3px;
                padding-top: {padding}px;
            }}
            PianoKey[black="true"] {{
                background-color: {black_bg}; color: {black_fg};
                border: 1px solid {border}; border-top: none;
                border-bottom-left-radius: 3px; border-bottom-right-radius: 3px;
            }}
            PianoKey:hover {{ background-color: {highlight}; color: {highlight_text}; }}
            PianoKey:pressed {{ background-color: {highlight}; color: {highlight_text}; }}
        """.format(white_bg=white_bg, white_fg=white_fg, black_bg=black_bg, black_fg=black_fg,
                   border=border, padding=int(black_h * 0.55), highlight=highlight,
                   highlight_text=highlight_text))

    def changeEvent(self, evt):
        super().changeEvent(evt)
        if evt.type() in (QEvent.PaletteChange, QEvent.FontChange):
            self.rebuild()

    def has_keys(self):
        return len(self.key_area.white_keys) > 0 or len(self.key_area.black_keys) > 0

    def relabel_buttons(self):
        """ Piano keys are labelled with note names.

        Deliberately does not use KeycodeDisplay.relabel_buttons: that would replace the note names
        with the generic MIDI keycode labels, and country keymap overrides never apply to MIDI.
        """
