import unittest.mock

import pytest

from keycodes.keycodes import Keycode, create_midi_keycodes, recreate_keycodes, \
    KEYCODES_MIDI, KEYCODES_MIDI_NOTES, KEYCODES_MIDI_NOTES_ACTIVE, KEYCODES_MIDI_CONTROLS_ACTIVE, \
    KEYCODES_MIDI_ADVANCED, KEYCODES_MIDI_BASIC_CONTROLS
from tabbed_keycodes import FilteredTabbedKeycodes, keycode_filter_any, keycode_filter_masked
from widgets.piano_keyboard import PianoKeyboard, NOTES, note_qmk_id, VISIBLE_OCTAVES, \
    OCTAVE_COUNT, WHITE_PER_OCTAVE

BLACK_PER_OCTAVE = 5


@pytest.fixture(autouse=True)
def reset_midi_keycodes():
    yield
    create_midi_keycodes(None)
    recreate_keycodes()


def setup_midi(level):
    create_midi_keycodes(level)
    recreate_keycodes()


def make_piano(level, keycode_filter=keycode_filter_any):
    setup_midi(level)
    piano = PianoKeyboard()
    piano.recreate_keys(keycode_filter)
    return piano


class TestMidiKeycodeGroups:

    def test_disabled_keyboard_has_no_midi_keycodes(self):
        setup_midi(None)
        assert KEYCODES_MIDI == []
        assert KEYCODES_MIDI_NOTES_ACTIVE == []
        assert KEYCODES_MIDI_CONTROLS_ACTIVE == []

    def test_basic_exposes_notes_and_all_off_only(self):
        setup_midi("basic")
        assert KEYCODES_MIDI_NOTES_ACTIVE == KEYCODES_MIDI_NOTES
        assert KEYCODES_MIDI_CONTROLS_ACTIVE == KEYCODES_MIDI_BASIC_CONTROLS
        # advanced controls must not leak onto a keyboard that only declares basic MIDI
        assert not any(kc in KEYCODES_MIDI_CONTROLS_ACTIVE for kc in KEYCODES_MIDI_ADVANCED)

    def test_advanced_exposes_notes_and_every_control(self):
        setup_midi("advanced")
        assert KEYCODES_MIDI_NOTES_ACTIVE == KEYCODES_MIDI_NOTES
        assert KEYCODES_MIDI_CONTROLS_ACTIVE == KEYCODES_MIDI_BASIC_CONTROLS + KEYCODES_MIDI_ADVANCED

    def test_notes_and_controls_partition_keycodes_midi(self):
        setup_midi("advanced")
        assert sorted(id(kc) for kc in KEYCODES_MIDI) == \
               sorted(id(kc) for kc in KEYCODES_MIDI_NOTES_ACTIVE + KEYCODES_MIDI_CONTROLS_ACTIVE)

    def test_all_notes_are_covered_by_the_piano_note_map(self):
        setup_midi("basic")
        mapped = {note_qmk_id(fragment, octave)
                  for octave in range(OCTAVE_COUNT) for _, fragment, _ in NOTES}
        assert {kc.qmk_id for kc in KEYCODES_MIDI_NOTES} == mapped


class TestPianoKeyboard:

    def test_no_keys_when_keyboard_has_no_midi(self, qtbot):
        piano = make_piano(None)
        qtbot.addWidget(piano)
        assert not piano.has_keys()

    def test_renders_one_screenful_of_octaves(self, qtbot):
        piano = make_piano("basic")
        qtbot.addWidget(piano)
        assert piano.has_keys()
        assert len(piano.key_area.white_keys) == WHITE_PER_OCTAVE * VISIBLE_OCTAVES
        assert len(piano.key_area.black_keys) == BLACK_PER_OCTAVE * VISIBLE_OCTAVES

    def test_every_key_maps_to_a_registered_keycode(self, qtbot):
        piano = make_piano("advanced")
        qtbot.addWidget(piano)
        keys = piano.key_area.white_keys + [btn for _, btn in piano.key_area.black_keys]
        for btn in keys:
            assert Keycode.find_by_qmk_id(btn.keycode.qmk_id) is not None

    def test_clicking_a_key_emits_its_keycode(self, qtbot):
        piano = make_piano("basic")
        qtbot.addWidget(piano)
        first = piano.key_area.white_keys[0]
        with qtbot.waitSignal(piano.keycode_changed) as blocker:
            first.click()
        assert blocker.args == [first.keycode.qmk_id]
        # the leftmost key of the default view is the base octave C
        assert first.keycode.qmk_id == "MI_C"

    def test_black_keys_overlap_the_white_keys(self, qtbot):
        piano = make_piano("basic")
        qtbot.addWidget(piano)
        white_bottom = piano.key_area.white_keys[0].geometry().bottom()
        for _, btn in piano.key_area.black_keys:
            assert btn.geometry().bottom() < white_bottom
        # a black key must straddle the boundary between two white keys
        white_idx, black = piano.key_area.black_keys[0]
        left, right = piano.key_area.white_keys[white_idx], piano.key_area.white_keys[white_idx + 1]
        assert black.geometry().left() > left.geometry().left()
        assert black.geometry().right() < right.geometry().right()

    def test_octave_navigation_scrolls_through_all_octaves(self, qtbot):
        piano = make_piano("basic")
        qtbot.addWidget(piano)
        assert piano.visible_octave_list() == [0, 1, 2]

        piano.next_btn.click()
        assert piano.visible_octave_list() == [1, 2, 3]
        assert piano.key_area.white_keys[0].keycode.qmk_id == "MI_C_1"

        # cannot scroll past the last octave
        for _ in range(10):
            piano.next_btn.click()
        assert piano.visible_octave_list() == [3, 4, 5]
        assert not piano.next_btn.isEnabled()

        for _ in range(10):
            piano.prev_btn.click()
        assert piano.visible_octave_list() == [0, 1, 2]
        assert not piano.prev_btn.isEnabled()

    def test_navigation_is_view_only_and_never_emits(self, qtbot):
        piano = make_piano("basic")
        qtbot.addWidget(piano)
        with qtbot.assertNotEmitted(piano.keycode_changed):
            piano.next_btn.click()
            piano.prev_btn.click()

    def test_masked_filter_hides_every_note(self, qtbot):
        piano = make_piano("advanced", keycode_filter_masked)
        qtbot.addWidget(piano)
        assert not piano.has_keys()

    def test_relabel_keeps_note_names(self, qtbot):
        piano = make_piano("basic")
        qtbot.addWidget(piano)
        before = [btn.text() for btn in piano.key_area.white_keys]
        piano.relabel_buttons()
        assert [btn.text() for btn in piano.key_area.white_keys] == before
        # note names, not the generic "MIDI\nC" keycode labels
        assert before[0] == "C"


class TestMidiTab:

    def find_midi_tab(self, tabs):
        return next(tab for tab in tabs.tabs if tab.label == "MIDI")

    def test_tab_hidden_without_midi_support(self, qtbot):
        setup_midi(None)
        tabs = FilteredTabbedKeycodes()
        qtbot.addWidget(tabs)
        assert not self.find_midi_tab(tabs).has_buttons()

    def test_tab_shown_for_basic_midi_even_with_no_extra_controls(self, qtbot):
        setup_midi("basic")
        tabs = FilteredTabbedKeycodes()
        qtbot.addWidget(tabs)
        midi = self.find_midi_tab(tabs)
        # regression: has_buttons() used to ignore the keyboard display, which hid the whole tab
        assert midi.has_buttons()
        assert midi.alternatives[0].kb_display.has_keys()

    def test_piano_alternative_excludes_notes_from_the_button_grid(self, qtbot):
        setup_midi("advanced")
        tabs = FilteredTabbedKeycodes()
        qtbot.addWidget(tabs)
        midi = self.find_midi_tab(tabs)
        piano_alt, fallback_alt = midi.alternatives[0], midi.alternatives[1]

        note_ids = {kc.qmk_id for kc in KEYCODES_MIDI_NOTES}
        assert not any(btn.keycode.qmk_id in note_ids for btn in piano_alt.buttons)
        assert "MI_ALLOFF" in {btn.keycode.qmk_id for btn in piano_alt.buttons}
        # the plain grid fallback still offers everything
        assert note_ids <= {btn.keycode.qmk_id for btn in fallback_alt.buttons}

    def test_tab_selection_falls_back_to_the_grid_when_narrow(self, qtbot):
        setup_midi("advanced")
        tabs = FilteredTabbedKeycodes()
        qtbot.addWidget(tabs)
        midi = self.find_midi_tab(tabs)

        piano_alt = midi.alternatives[0]
        assert piano_alt.required_width() > 0
        # the plain grid has no keyboard display, so it always fits
        assert midi.alternatives[1].required_width() == 0

    def test_keycode_changed_propagates_from_piano_to_tab(self, qtbot):
        setup_midi("basic")
        tabs = FilteredTabbedKeycodes()
        qtbot.addWidget(tabs)
        midi = self.find_midi_tab(tabs)
        piano = midi.alternatives[0].kb_display

        with qtbot.waitSignal(tabs.keycode_changed) as blocker:
            piano.key_area.white_keys[0].click()
        assert blocker.args == ["MI_C"]
