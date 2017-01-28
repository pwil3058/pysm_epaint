#  Copyright 2017 Peter Williams <pwil3058@gmail.com>
#
# This software is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License only.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software; if not, write to:
#  The Free Software Foundation, Inc., 51 Franklin Street,
#  Fifth Floor, Boston, MA 02110-1301 USA

"""Create/edit paint specifications
"""

import fractions
import hashlib
import math
import os

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from ..bab import mathx
from ..bab import options

from ..gtx import actions
from ..gtx import coloured
from ..gtx import dialogue
from ..gtx import entries
from ..gtx import recollect
from ..gtx import screen

from . import gpaint
from . import lexicon
from . import vpaint
from . import pchar
from . import rgbh

__all__ = []
__author__ = "Peter Williams <pwil3058@gmail.com>"

class UnsavedChangesDialogue(dialogue.Dialog):
    # TODO: make a better UnsavedChangesDialogue()
    SAVE_AND_CONTINUE, CONTINUE_UNSAVED = range(1, 3)
    def __init__(self, parent, message):
        buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        buttons += (_("Save and Continue"), UnsavedChangesDialogue.SAVE_AND_CONTINUE)
        buttons += (_("Continue Without Saving"), UnsavedChangesDialogue.CONTINUE_UNSAVED)
        dialogue.Dialog.__init__(self,
            parent=parent,
            flags=Gtk.DialogFlags.MODAL,
            buttons=buttons,
        )
        self.vbox.pack_start(Gtk.Label(message), expand=True, fill=True, padding=0)
        self.show_all()

class UnacceptedChangesDialogue(dialogue.Dialog):
    # TODO: make a better UnacceptedChangesDialogue()
    ACCEPT_CHANGES_AND_CONTINUE, CONTINUE_DISCARDING_CHANGES = range(1, 3)
    def __init__(self, parent, message):
        buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        buttons += (_('Accept and Continue'), UnacceptedChangesDialogue.ACCEPT_CHANGES_AND_CONTINUE)
        buttons += (_('Continue (Discarding Changes)'), UnacceptedChangesDialogue.CONTINUE_DISCARDING_CHANGES)
        dialogue.Dialog.__init__(self,
            parent=parent,
            flags=Gtk.DialogFlags.MODAL,
            buttons=buttons,
        )
        self.vbox.pack_start(Gtk.Label(message), expand=True, fill=True, padding=0)
        self.show_all()

class UnaddedNewColourDialogue(dialogue.Dialog):
    # TODO: make a better UnaddedNewColourDialogue()
    DISCARD_AND_CONTINUE = 1
    def __init__(self, parent, message):
        buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        buttons += (_('Discard and Continue'), UnaddedNewColourDialogue.DISCARD_AND_CONTINUE)
        dialogue.Dialog.__init__(self,
            parent=parent,
            flags=Gtk.DialogFlags.MODAL,
            buttons=buttons,
        )
        self.vbox.pack_start(Gtk.Label(message), expand=True, fill=True, padding=0)
        self.show_all()

class ColourSampleMatcher(Gtk.VBox):
    COLOUR = None
    HUE_DISPLAY_SPAN =  math.pi / 10
    VALUE_DISPLAY_INCR = fractions.Fraction(1, 10)
    DEFAULT_COLOUR = lambda self: self.COLOUR(self.COLOUR.RGB.WHITE / 2)
    DELTA_HUE = [mathx.Angle(math.pi / x) for x in [200, 100, 50]]
    DELTA_VALUE = [0.0025, 0.005, 0.01]
    DELTA_CHROMA = [0.0025, 0.005, 0.01]
    DEFAULT_AUTO_MATCH_RAW = True
    PROVIDE_RGB_ENTRY = True

    class HueClockwiseButton(coloured.ColouredButton):
        def __init__(self):
            coloured.ColouredButton.__init__(self, label="->")
        def set_colour(self, colour):
            if options.get("colour_wheel", "red_to_yellow_clockwise"):
                new_colour = colour.get_rotated_rgb(ColourSampleMatcher.HUE_DISPLAY_SPAN)
            else:
                new_colour = colour.get_rotated_rgb(-ColourSampleMatcher.HUE_DISPLAY_SPAN)
            coloured.ColouredButton.set_colour(self, new_colour.gdk_color)

    class HueAntiClockwiseButton(coloured.ColouredButton):
        def __init__(self):
            coloured.ColouredButton.__init__(self, label="<-")
        def set_colour(self, colour):
            if options.get("colour_wheel", "red_to_yellow_clockwise"):
                new_colour = colour.get_rotated_rgb(-ColourSampleMatcher.HUE_DISPLAY_SPAN)
            else:
                new_colour = colour.get_rotated_rgb(ColourSampleMatcher.HUE_DISPLAY_SPAN)
            coloured.ColouredButton.set_colour(self, new_colour.gdk_color)

    class IncrValueButton(coloured.ColouredButton):
        def __init__(self):
            coloured.ColouredButton.__init__(self, label=_("Value")+"++")
        def set_colour(self, colour):
            value = min(colour.value + ColourSampleMatcher.VALUE_DISPLAY_INCR, fractions.Fraction(1))
            coloured.ColouredButton.set_colour(self, colour.hue_rgb_for_value(value).gdk_color)

    class DecrValueButton(coloured.ColouredButton):
        def __init__(self):
            coloured.ColouredButton.__init__(self, label=_("Value")+"--")
        def set_colour(self, colour):
            value = max(colour.value - ColourSampleMatcher.VALUE_DISPLAY_INCR, fractions.Fraction(0))
            coloured.ColouredButton.set_colour(self, colour.hue_rgb_for_value(value).gdk_color)

    class IncrGraynessButton(coloured.ColouredButton):
        def __init__(self):
            coloured.ColouredButton.__init__(self, label=_("Grayness") + "++")
        def set_colour(self, colour):
            coloured.ColouredButton.set_colour(self, colour.value_rgb.gdk_color)

    class DecrGraynessButton(coloured.ColouredButton):
        def __init__(self):
            coloured.ColouredButton.__init__(self, label=_("Grayness") + "--")
        def set_colour(self, colour):
            coloured.ColouredButton.set_colour(self, colour.hue_rgb_for_value().gdk_color)

    def __init__(self, auto_match_on_paste=False):
        Gtk.VBox.__init__(self)
        self._delta = 256 # must be a power of two
        self.auto_match_on_paste = auto_match_on_paste
        # Add RGB entry field
        if self.PROVIDE_RGB_ENTRY:
            self.rgb_entry = gpaint.RGBEntryBox()
            self.rgb_entry.connect("colour-changed", self._rgb_entry_changed_cb)
            self.pack_start(self.rgb_entry, expand=False, fill=True, padding=0)
        default_colour = self.DEFAULT_COLOUR()
        if hasattr(default_colour, "warmth"):
            self.hcv_display = gpaint.HCVWDisplay()
        else:
            self.hcv_display = gpaint.HCVDisplay()
        self.pack_start(self.hcv_display, expand=False, fill=True, padding=0)
        # Add value modification buttons
        # Lighten
        hbox = Gtk.HBox()
        self.incr_value_button = self.IncrValueButton()
        hbox.pack_start(self.incr_value_button, expand=True, fill=True, padding=0)
        self.incr_value_button.connect("clicked", self.incr_value_cb)
        self.pack_start(hbox, expand=False, fill=True, padding=0)
        # Add anti clockwise hue angle modification button
        hbox = Gtk.HBox()
        self.hue_acw_button = self.HueAntiClockwiseButton()
        hbox.pack_start(self.hue_acw_button, expand=False, fill=True, padding=0)
        self.hue_acw_button.connect("clicked", self.modify_hue_acw_cb)
        # Add the sample display panel
        self.sample_display = gpaint.ColourSampleArea()
        self.sample_display.connect("samples_changed", self._sample_change_cb)
        hbox.pack_start(self.sample_display, expand=True, fill=True, padding=0)
        # Add anti clockwise hue angle modification button
        self.hue_cw_button = self.HueClockwiseButton()
        hbox.pack_start(self.hue_cw_button, expand=False, fill=True, padding=0)
        self.hue_cw_button.connect("clicked", self.modify_hue_cw_cb)
        self.pack_start(hbox, expand=True, fill=True, padding=0)
        # Darken
        hbox = Gtk.HBox()
        self.decr_value_button = self.DecrValueButton()
        hbox.pack_start(self.decr_value_button, expand=True, fill=True, padding=0)
        self.decr_value_button.connect("clicked", self.decr_value_cb)
        self.pack_start(hbox, expand=False, fill=True, padding=0)
        # Grayness
        hbox = Gtk.HBox()
        self.decr_grayness_button = self.DecrGraynessButton()
        hbox.pack_start(self.decr_grayness_button, expand=True, fill=True, padding=0)
        self.decr_grayness_button.connect("clicked", self.decr_grayness_cb)
        self.incr_grayness_button = self.IncrGraynessButton()
        hbox.pack_start(self.incr_grayness_button, expand=True, fill=True, padding=0)
        self.incr_grayness_button.connect("clicked", self.incr_grayness_cb)
        self.pack_start(hbox, expand=False, fill=True, padding=0)
        #
        self.set_colour(default_colour)
        #
        self.show_all()

    def set_colour(self, colour):
        colour = self.COLOUR(colour) if colour is not None else self.DEFAULT_COLOUR()
        self.rgb_manipulator = rgbh.RGBManipulator(colour.rgb)
        self._set_colour(colour)

    def _set_colour_fm_manipulator(self):
        self._set_colour(self.COLOUR(self.rgb_manipulator.get_rgb()))

    def _set_colour(self, colour):
        self.colour = colour
        if hasattr(self, "rgb_entry"):
            self.rgb_entry.set_colour(self.colour)
        self.sample_display.set_bg_colour(self.colour.rgb)
        self.hue_cw_button.set_colour(self.colour)
        self.hue_acw_button.set_colour(self.colour)
        self.incr_value_button.set_colour(self.colour)
        self.decr_value_button.set_colour(self.colour)
        self.incr_grayness_button.set_colour(self.colour)
        self.decr_grayness_button.set_colour(self.colour)
        self.hcv_display.set_colour(self.colour)

    def _auto_match_sample(self, samples, raw):
        total = [0, 0, 0]
        npixels = 0
        for sample in samples:
            assert sample.get_bits_per_sample() == 8
            nc = sample.get_n_channels()
            rs = sample.get_rowstride()
            width = sample.get_width()
            n_rows = sample.get_height()
            data = list(sample.get_pixels())
            for row_num in range(n_rows):
                row_start = row_num * rs
                for j in range(width):
                    offset = row_start + j * nc
                    for i in range(3):
                        total[i] += data[offset + i]
            npixels += width * n_rows
        rgb = self.COLOUR.RGB(*(self.COLOUR.RGB.ROUND((total[i] << 8) / npixels) for i in range(3)))
        if raw:
            self.set_colour(rgb)
        else:
            self.set_colour(self.COLOUR(rgb).hue_rgb_for_value())

    def auto_match_sample(self, raw):
        samples = self.sample_display.get_samples()
        if samples:
            self._auto_match_sample(samples, raw)

    def _sample_change_cb(self, widget, *args):
        if self.auto_match_on_paste:
            self.auto_match_sample(raw=self.DEFAULT_AUTO_MATCH_RAW)

    def _rgb_entry_changed_cb(self, entry):
        self.set_colour(entry.get_colour())

    def _get_delta_index(self, modifier_button_states):
        if modifier_button_states & Gdk.ModifierType.CONTROL_MASK:
            return 0
        elif modifier_button_states & Gdk.ModifierType.SHIFT_MASK:
            return 2
        else:
            return 1

    def incr_grayness_cb(self, button, state):
        if self.rgb_manipulator.decr_chroma(self.DELTA_CHROMA[self._get_delta_index(state)]):
            self._set_colour_fm_manipulator()
        else:
            # let the user know that we're at the limit
            Gdk.beep()

    def decr_grayness_cb(self, button, state):
        if self.rgb_manipulator.incr_chroma(self.DELTA_CHROMA[self._get_delta_index(state)]):
            self._set_colour_fm_manipulator()
        else:
            # let the user know that we're at the limit
            Gdk.beep()

    def incr_value_cb(self, button, state):
        if self.rgb_manipulator.incr_value(self.DELTA_VALUE[self._get_delta_index(state)]):
            self._set_colour_fm_manipulator()
        else:
            # let the user know that we're at the limit
            Gdk.beep()

    def decr_value_cb(self, button, state):
        if self.rgb_manipulator.decr_value(self.DELTA_VALUE[self._get_delta_index(state)]):
            self._set_colour_fm_manipulator()
        else:
            # let the user know that we're at the limit
            Gdk.beep()

    def modify_hue_acw_cb(self, button, state):
        if not options.get("colour_wheel", "red_to_yellow_clockwise"):
            if self.rgb_manipulator.rotate_hue(self.DELTA_HUE[self._get_delta_index(state)]):
                self._set_colour_fm_manipulator()
            else:
                Gdk.beep()
        else:
            if self.rgb_manipulator.rotate_hue(-self.DELTA_HUE[self._get_delta_index(state)]):
                self._set_colour_fm_manipulator()
            else:
                Gdk.beep()

    def modify_hue_cw_cb(self, button, state):
        if not options.get("colour_wheel", "red_to_yellow_clockwise"):
            if self.rgb_manipulator.rotate_hue(-self.DELTA_HUE[self._get_delta_index(state)]):
                self._set_colour_fm_manipulator()
            else:
                Gdk.beep()
        else:
            if self.rgb_manipulator.rotate_hue(self.DELTA_HUE[self._get_delta_index(state)]):
                self._set_colour_fm_manipulator()
            else:
                Gdk.beep()

class PaintEditor(Gtk.VBox):
    AC_READY, AC_NOT_READY, AC_MASK = actions.ActionCondns.new_flags_and_mask(2)
    COLOUR_NAME_LEXICON = lexicon.COLOUR_NAME_LEXICON
    GENERAL_WORDS_LEXICON = lexicon.GENERAL_WORDS_LEXICON
    PAINT = None
    RESET_CHARACTERISTICS = True

    def __init__(self):
        Gtk.VBox.__init__(self)
        #
        table = Gtk.Table(rows=3, columns=2, homogeneous=False)
        # Colour Name
        stext =  Gtk.Label(label=_("Colour Name:"))
        table.attach(stext, 0, 1, 0, 1, xoptions=0)
        self.colour_name = entries.TextEntryAutoComplete(self.COLOUR_NAME_LEXICON)
        self.colour_name.connect("new-words", lexicon.new_paint_words_cb)
        self.colour_name.connect("changed", self._changed_cb)
        table.attach(self.colour_name, 1, 2, 0, 1)
        next_row = 1
        self.extra_entries = {}
        for extra in self.PAINT.EXTRAS:
            label = Gtk.Label(label=extra.prompt_text)
            table.attach(label, 0, 1, next_row, next_row + 1, xoptions=0)
            self.extra_entries[extra.name] = entries.TextEntryAutoComplete(self.GENERAL_WORDS_LEXICON)
            self.extra_entries[extra.name].set_text(extra.default_value)
            self.extra_entries[extra.name].connect("new-words", lexicon.new_general_words_cb)
            self.extra_entries[extra.name].connect("changed", self._changed_cb)
            table.attach(self.extra_entries[extra.name], 1, 2, next_row, next_row + 1)
            next_row += 1
        self.c_choosers = pchar.Choosers(self.PAINT.CHARACTERISTICS.NAMES)
        for chooser in self.c_choosers.values():
            label = Gtk.Label(label=chooser.PROMPT_TEXT)
            table.attach(label, 0, 1, next_row, next_row + 1, xoptions=0)
            table.attach(chooser, 1, 2, next_row, next_row + 1)
            chooser.connect("changed", self._changed_cb)
            next_row += 1
        self.pack_start(table, expand=False, fill=True, padding=0)
        # Matcher
        class ColourMatcher(ColourSampleMatcher):
            COLOUR = self.PAINT.COLOUR
        self.colour_matcher = ColourMatcher()
        self.pack_start(self.colour_matcher, expand=True, fill=True, padding=0)
        #
        self.show_all()

    def _changed_cb(self, widget):
        # pass on any change signals (including where they came from)
        self.emit("changed", widget)

    def reset(self):
        self.colour_matcher.sample_display.erase_samples()
        self.colour_matcher.set_colour(None)
        self.colour_name.set_text("")
        for extra in self.PAINT.EXTRAS:
            self.extra_entries[extra.name].set_text(extra.default_value)
        if self.RESET_CHARACTERISTICS:
            for chooser in self.c_choosers.values():
                chooser.set_active(-1)

    def get_paint(self):
        name = self.colour_name.get_text()
        rgb = self.colour_matcher.colour.rgb
        kwargs = self.c_choosers.get_kwargs()
        for extra in self.PAINT.EXTRAS:
            kwargs[extra.name] = self.extra_entries[extra.name].get_text()
        return self.PAINT(name=name, rgb=rgb, **kwargs)

    def set_paint(self, paint):
        self.colour_matcher.set_colour(paint.rgb)
        self.colour_name.set_text(paint.name)
        for extra in self.PAINT.EXTRAS:
            self.extra_entries[extra.name].set_text(getattr(paint, extra.name))
        self.c_choosers.set_selections(**paint.characteristics.get_kwargs())

    def auto_match_sample(self, raw=False):
        self.colour_matcher.auto_match_sample(raw)

    def get_masked_condns(self):
        if self.colour_name.get_text_length() == 0 or not self.c_choosers.all_active:
            return actions.MaskedCondns(self.AC_NOT_READY, self.AC_MASK)
        return actions.MaskedCondns(self.AC_READY, self.AC_MASK)

GObject.signal_new("changed", PaintEditor, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))

class ModelPaintEditor(PaintEditor):
    PAINT = vpaint.ModelPaint


class PaintSeriesEditor(Gtk.HPaned, actions.CAGandUIManager, dialogue.ReporterMixin, dialogue.AskerMixin):
    PAINT_EDITOR = None
    PAINT_LIST_NOTEBOOK = None
    UI_DESCR = """
    <ui>
      <menubar name="paint_series_editor_menubar">
        <menu action="paint_series_editor_file_menu">
          <menuitem action="new_paint_series"/>
          <menuitem action="open_paint_series_file"/>
          <menuitem action="save_paint_series_to_file"/>
          <menuitem action="save_paint_series_as_file"/>
          <menuitem action="close_colour_editor"/>
        </menu>
        <menu action="paint_series_editor_samples_menu">
          <menuitem action="take_screen_sample"/>
          <menuitem action="open_sample_viewer"/>
        </menu>
      </menubar>
    </ui>
    """
    AC_HAS_COLOUR, AC_NOT_HAS_COLOUR, AC_HAS_FILE, AC_ID_READY, AC_MASK = actions.ActionCondns.new_flags_and_mask(4)
    def __init__(self):
        Gtk.HPaned.__init__(self)
        actions.CAGandUIManager.__init__(self)
        #
        self.set_file_path(None)
        self.set_current_colour(None)
        self.saved_hash = None
        self.__closed = False

        # First assemble the parts
        self.paint_editor = self.PAINT_EDITOR()
        self.paint_editor.connect("changed", self._paint_editor_change_cb)
        self.paint_editor.colour_matcher.sample_display.connect("samples-changed", self._sample_change_cb)
        self.buttons = self.action_groups.create_action_button_box([
            "add_colour_into_series",
            "accept_colour_changes",
            "reset_colour_editor",
            "take_screen_sample",
            "automatch_sample_images_raw",
        ])
        self.paint_colours = self.PAINT_LIST_NOTEBOOK(wheel_popup="/colour_wheel_EI_popup")
        self.paint_colours.set_wheels_edit_paint_acb(self._load_wheel_colour_into_editor_cb)
        self.paint_colours.set_size_request(480, 480)
        self.paint_colours.paint_list.action_groups.connect_activate("edit_selected_paint", self._edit_selected_colour_cb)
        # as these are company names don't split them up for autocompletion
        self.manufacturer_name = entries.TextEntryAutoComplete(lexicon.GENERAL_WORDS_LEXICON, multiword=False)
        self.manufacturer_name.connect("new-words", lexicon.new_general_words_cb)
        self.manufacturer_name.connect("changed", self._id_changed_cb)
        mnlabel = Gtk.Label(label=_("Manufacturer:"))
        self.series_name = entries.TextEntryAutoComplete(lexicon.GENERAL_WORDS_LEXICON)
        self.series_name.connect("new-words", lexicon.new_general_words_cb)
        self.series_name.connect("changed", self._id_changed_cb)
        snlabel = Gtk.Label(label=_("Series:"))
        self.set_current_colour(None)
        # Now arrange them
        vbox = Gtk.VBox()
        table = Gtk.Table(rows=2, columns=2, homogeneous=False)
        table.attach(mnlabel, 0, 1, 0, 1, xoptions=0)
        table.attach(snlabel, 0, 1, 1, 2, xoptions=0)
        table.attach(self.manufacturer_name, 1, 2, 0, 1)
        table.attach(self.series_name, 1, 2, 1, 2)
        vbox.pack_start(table, expand=False, fill=True, padding=0)
        vbox.pack_start(self.paint_colours, expand=True, fill=True, padding=0)
        self.pack1(vbox, resize=True, shrink=False)
        vbox = Gtk.VBox()
        vbox.pack_start(self.paint_editor, expand=True, fill=True, padding=0)
        vbox.pack_start(self.buttons, expand=False, fill=True, padding=0)
        self.pack2(vbox, resize=True, shrink=False)
        self.set_position(recollect.get("editor", "hpaned_position"))
        self.connect("notify", self._notify_cb)
        self.show_all()
    def _notify_cb(self, widget, parameter):
        if parameter.name == "position":
            recollect.set("editor", "hpaned_position", str(widget.get_position()))
    def populate_action_groups(self):
        self.action_groups[gpaint.ColourSampleArea.AC_SAMPLES_PASTED].add_actions([
            ("automatch_sample_images_raw", None, _("Auto Match"), None,
            _("Auto matically match the colour to the sample images."),
            self._automatch_sample_images_raw_cb),
        ])
        self.action_groups[PaintEditor.AC_READY|self.AC_NOT_HAS_COLOUR].add_actions([
            ("add_colour_into_series", None, _("Add"), None,
            _("Accept this colour and add it to the series."),
            self._add_colour_into_series_cb),
        ])
        self.action_groups[PaintEditor.AC_READY|self.AC_HAS_COLOUR].add_actions([
            ("accept_colour_changes", None, _("Accept"), None,
            _("Accept the changes made to this colour."),
            self._accept_colour_changes_cb),
        ])
        self.action_groups[self.AC_HAS_FILE|self.AC_ID_READY].add_actions([
            ("save_paint_series_to_file", Gtk.STOCK_SAVE, None, None,
            _("Save the current series definition to file."),
            self._save_paint_series_to_file_cb),
        ])
        self.action_groups[self.AC_ID_READY].add_actions([
            ("save_paint_series_as_file", Gtk.STOCK_SAVE_AS, None, None,
            _("Save the current series definition to a user chosen file."),
            self._save_paint_series_as_file_cb),
        ])
        # TODO: make some of these conditional
        self.action_groups[actions.AC_DONT_CARE].add_actions([
            ("paint_series_editor_file_menu", None, _("File")),
            ("paint_series_editor_samples_menu", None, _("Samples")),
            ("reset_colour_editor", None, _("Reset"), None,
            _("Reset the colour editor to its default state."),
            self._reset_colour_editor_cb),
            ("open_paint_series_file", Gtk.STOCK_OPEN, None, None,
            _("Load a paint series from a file for editing."),
            self._open_paint_series_file_cb),
            ("take_screen_sample", None, _("Take Sample"), None,
            _("Take a sample of an arbitrary selected section of the screen and add it to the clipboard."),
            lambda _action: screen.take_screen_sample()),
            ("open_sample_viewer", None, _("Open Sample Viewer"), None,
            _("Open a graphics file containing colour samples."),
            self._open_sample_viewer_cb),
            ("close_colour_editor", Gtk.STOCK_CLOSE, None, None,
            _("Close this window."),
            self._close_colour_editor_cb),
            ("new_paint_series", Gtk.STOCK_NEW, None, None,
            _("Start a new paint colour series."),
            self._new_paint_series_cb),
        ])
    def get_masked_condns(self):
        condns = 0
        if self.current_colour is None:
            condns |= self.AC_NOT_HAS_COLOUR
        else:
            condns |= self.AC_HAS_COLOUR
        if self.file_path is not None:
            condns |= self.AC_HAS_FILE
        if self.manufacturer_name.get_text_length() > 0 and self.series_name.get_text_length() > 0:
            condns |= self.AC_ID_READY
        return actions.MaskedCondns(condns, self.AC_MASK)
    def unsaved_changes_ok(self):
        """
        Check that the last saved definition is up to date
        """
        if not self.colour_edit_state_ok():
            return False
        manl = self.manufacturer_name.get_text_length()
        serl = self.series_name.get_text_length()
        coll = len(self.paint_colours)
        if manl == 0 and serl == 0 and coll == 0:
            return True
        dtext = self.get_definition_text()
        if hashlib.sha1(dtext.encode()).digest() == self.saved_hash:
            return True
        parent = self.get_toplevel()
        dlg = UnsavedChangesDialogue(
            parent=parent if isinstance(parent, Gtk.Window) else None,
            message=_("The series definition has unsaved changes.")
        )
        response = dlg.run()
        dlg.destroy()
        if response == Gtk.ResponseType.CANCEL:
            return False
        elif response == UnsavedChangesDialogue.CONTINUE_UNSAVED:
            return True
        elif self.file_path is not None:
            self.save_to_file(None)
        else:
            self._save_paint_series_as_file_cb(None)
        return True
    def _paint_editor_change_cb(self, widget, *args):
        """
        Update actions' "enabled" statuses based on paint editor condition
        """
        self.action_groups.update_condns(widget.get_masked_condns())
    def _sample_change_cb(self, widget, *args):
        """
        Update actions' "enabled" statuses based on sample area condition
        """
        self.action_groups.update_condns(widget.get_masked_condns())
    def _id_changed_cb(self, widget, *args):
        """
        Update actions' "enabled" statuses based on manufacturer and
        series name state
        """
        if self.manufacturer_name.get_text_length() == 0:
            condns = 0
        elif self.series_name.get_text_length() == 0:
            condns = 0
        else:
            condns = self.AC_ID_READY
        self.action_groups.update_condns(actions.MaskedCondns(condns, self.AC_ID_READY))
    def set_current_colour(self, colour):
        """
        Set a reference to the colour currently being edited and
        update action conditions for this change
        """
        self.current_colour = colour
        mask = self.AC_NOT_HAS_COLOUR + self.AC_HAS_COLOUR
        condns = self.AC_NOT_HAS_COLOUR if colour is None else self.AC_HAS_COLOUR
        self.action_groups.update_condns(actions.MaskedCondns(condns, mask))
    def set_file_path(self, file_path):
        """
        Set the file path for the paint colour series currently being
        edited and update action conditions for this change
        """
        self.file_path = file_path
        condns = 0 if file_path is None else self.AC_HAS_FILE
        self.action_groups.update_condns(actions.MaskedCondns(condns, self.AC_HAS_FILE))
        if condns:
            recollect.set("editor", "last_file", file_path)
        self.emit("file_changed", self.file_path)
    def colour_edit_state_ok(self):
        if self.current_colour is None:
            if self.paint_editor.colour_name.get_text_length() > 0:
                parent = self.get_toplevel()
                msg = _("New colour \"{0}\" has not been added to the series.").format(self.paint_editor.colour_name.get_text())
                dlg = UnaddedNewColourDialogue(parent=parent if isinstance(parent, Gtk.Window) else None,message=msg)
                response = dlg.run()
                dlg.destroy()
                return response == UnaddedNewColourDialogue.DISCARD_AND_CONTINUE
        else:
            edit_colour = self.paint_editor.get_paint()
            if self.current_colour != edit_colour:
                parent = self.get_toplevel()
                msg = _("Colour \"{0}\" has changes that have not been accepted.").format(edit_colour.name)
                dlg = UnacceptedChangesDialogue(parent=parent if isinstance(parent, Gtk.Window) else None,message=msg)
                response = dlg.run()
                dlg.destroy()
                if response == UnacceptedChangesDialogue.ACCEPT_CHANGES_AND_CONTINUE:
                    self._accept_colour_changes_cb()
                    return True
                else:
                    return response == UnacceptedChangesDialogue.CONTINUE_DISCARDING_CHANGES
        return True
    def _edit_selected_colour_cb(self, _action):
        """
        Load the selected paint colour into the editor
        """
        if self.colour_edit_state_ok():
            paint = self.paint_colours.paint_list.get_selected_paints()[0]
            self.paint_editor.set_paint(paint)
            self.set_current_colour(paint)
    def _load_wheel_colour_into_editor_cb(self, _action, wheel):
        if self.colour_edit_state_ok():
            paint = wheel.popup_colour
            if paint:
                self.paint_editor.set_paint(paint)
                self.set_current_colour(paint)
    def _ask_overwrite_ok(self, name):
        return self.ask_ok_cancel(_("A colour with the name \"{0}\" already exists.\n Overwrite?").format(name))
    def _accept_colour_changes_cb(self, _widget=None):
        edited_colour = self.paint_editor.get_paint()
        if edited_colour.name != self.current_colour.name:
            # there's a name change so check for duplicate names
            other_colour = self.paint_colours.get_paint_with_name(edited_colour.name)
            if other_colour is not None:
                if self._ask_overwrite_ok(edited_colour.name):
                    self.paint_colours.remove_paint(other_colour)
                else:
                    return
        # and do a full replace to make sure the view gets updated
        self.paint_colours.remove_paint(self.current_colour)
        self.paint_colours.add_paint(edited_colour)
        self.current_colour = edited_colour
        self.paint_colours.queue_draw()
    def _reset_colour_editor_cb(self, _widget):
        if self.colour_edit_state_ok():
            self.paint_editor.reset()
            self.set_current_colour(None)
    def _new_paint_series_cb(self, _action):
        """
        Throw away the current data and prepare to create a new series
        """
        if not self.unsaved_changes_ok():
            return
        self.paint_editor.reset()
        self.paint_colours.clear()
        self.manufacturer_name.set_text("")
        self.series_name.set_text("")
        self.set_file_path(None)
        self.set_current_colour(None)
        self.saved_hash = None
    def _add_colour_into_series_cb(self, _widget):
        new_colour = self.paint_editor.get_paint()
        old_colour = self.paint_colours.get_paint_with_name(new_colour.name)
        if old_colour is not None:
            if not self._ask_overwrite_ok(new_colour.name):
                return
            old_colour.set_rgb(new_colour.rgb)
            old_colour.set_extras(**new_colour.get_extras())
            old_colour.set_characteristics(**new_colour.characteristics.get_kwargs())
            self.paint_colours.queue_draw()
            self.set_current_colour(old_colour)
        else:
            self.paint_colours.add_paint(new_colour)
            self.set_current_colour(new_colour)
    def _automatch_sample_images_raw_cb(self, _widget):
        self.paint_editor.auto_match_sample(raw=True)
    def load_fm_file(self, filepath):
        try:
            with open(filepath, "r") as fobj:
                text = fobj.read()
        except IOError as edata:
            return self.report_io_error(edata)
        try:
            series = vpaint.PaintSeries.fm_definition(text)
        except vpaint.PaintSeries.ParseError as edata:
            return self.alert_user(_("Format Error:  {}: {}").format(edata, filepath))
        # All OK so clear the paint editor and ditch the current colours
        self.paint_editor.reset()
        self.set_current_colour(None)
        self.paint_colours.clear()
        # and load the new ones
        for paint in series.iter_paints():
            self.paint_colours.add_paint(paint)
        self.manufacturer_name.set_text(series.series_id.maker)
        self.series_name.set_text(series.series_id.name)
        self.set_file_path(filepath)
        self.saved_hash = hashlib.sha1(text.encode()).digest()
    def _open_paint_series_file_cb(self, _action):
        """
        Ask the user for the name of the file then open it.
        """
        if not self.unsaved_changes_ok():
            return
        if self.file_path:
            lastdir = os.path.dirname(self.file_path) + os.sep
        else:
            last_file = recollect.get("editor", "last_file")
            lastdir = os.path.dirname(last_file) + os.sep if last_file else None
        file_path = self.ask_file_path(_("Paint Series Description File:"), suggestion=lastdir, existing=True)
        if file_path:
            self.load_fm_file(file_path)
    def _open_sample_viewer_cb(self, _action):
        """
        Launch a window containing a sample viewer
        """
        SampleViewer(self.get_toplevel()).show()
    def get_definition_text(self):
        """
        Get the text sefinition of the current series
        """
        maker = self.manufacturer_name.get_text()
        name = self.series_name.get_text()
        series = vpaint.PaintSeries(maker=maker, name=name, paints=self.paint_colours.iter_paints())
        return series.definition_text()
    def save_to_file(self, filepath=None):
        if filepath is None:
            filepath = self.file_path
        definition = self.get_definition_text()
        try:
            with open(filepath, "w") as fobj:
                fobj.write(definition)
        except IOError as edata:
            return self.report_io_error(edata)
        # save was successful so set our filepath
        self.set_file_path(filepath)
        self.saved_hash = hashlib.sha1(definition.encode()).digest()
    def _save_paint_series_to_file_cb(self, _action):
        """
        Save the paint series to the current file
        """
        self.save_to_file(None)
    def _save_paint_series_as_file_cb(self, _action):
        """
        Ask the user for the name of the file then open it.
        """
        if self.file_path:
            lastdir = os.path.dirname(self.file_path) + os.sep
        else:
            last_file = recollect.get("editor", "last_file")
            lastdir = os.path.dirname(last_file) if last_file else None
        file_path = self.ask_file_path(_("Paint Series Description File:"), suggestion=lastdir, existing=False)
        if file_path:
            if not os.path.exists(file_path) or self.ask_yes_no(_("{}: already exists. Overwrite?").format(file_path)):
                self.save_to_file(file_path)
    def _close_colour_editor_cb(self, _action):
        """
        Close the Paint Series Editor
        """
        if not self.unsaved_changes_ok():
            return
        self.__closed = True
        self.get_toplevel().destroy()
    def _exit_colour_editor_cb(self, _action):
        """
        Exit the Paint Series Editor
        """
        if not self.__closed and not self.unsaved_changes_ok():
            return
        Gtk.main_quit()
GObject.signal_new("file_changed", PaintSeriesEditor, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
