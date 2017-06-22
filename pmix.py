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

"""Generic mechanisms for mixing paints
"""
import cgi
import collections
import os
import time

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from ..bab import mathx

from ..gtx import actions
from ..gtx import coloured
from ..gtx import dialogue
from ..gtx import entries
from ..gtx import gutils
from ..gtx import icons
from ..gtx import printer
from ..gtx import recollect
from ..gtx import screen
from ..gtx import tlview

from ..pixbufx import iview

from . import gpaint
from . import lexicon
from . import vpaint
from . import pedit

__all__ = []
__author__ = "Peter Williams <pwil3058@gmail.com>"

BLOB = collections.namedtuple("BLOB", ["paint", "parts"])

class Mixture:
    PAINT = None
    def __init__(self, blobs):
        rgb = self.PAINT.COLOUR.RGB.BLACK
        self.characteristics = self.PAINT.CHARACTERISTICS()
        parts = 0
        for blob in blobs:
            parts += blob.parts
            rgb += blob.paint.rgb * blob.parts
            self.characteristics += blob.paint.characteristics * blob.parts
        assert parts > 0, "Empty Mixture"
        self.colour = self.PAINT.COLOUR(rgb / parts)
        self.characteristics /= parts
        self.blobs = sorted(blobs, key=lambda x: x.parts, reverse=True)
    def __getattr__(self, attr_name):
        try:
            return getattr(self.colour, attr_name)
        except AttributeError:
            return getattr(self.characteristics, attr_name)
    def _components_str(self):
        string = _("\nComponents:\n")
        for blob in self.blobs:
            string += _("\t{0} Part(s): {1}\n").format(blob.parts, blob.paint)
        return string
    def __str__(self):
        return _("Mixed Colour: ") + Colour.__str__(self) + self._components_str()
    def contains_paint(self, paint):
        for blob in self.blobs:
            if blob.paint == paint:
                return True
        return False

class MixedPaint:
    MIXTURE = None
    def __init__(self, blobs, name, notes=""):
        self.mixture = self.MIXTURE(blobs)
        self.name = name
        self.notes = notes
    def __getattr__(self, attr_name):
        return getattr(self.mixture, attr_name)
    def __str__(self):
        return ("Name: \"{0}\" Notes: \"{1}\"").format(self.name, self.notes) + Colour.__str__(self) + self._components_str()

class ModelMixture(Mixture):
    PAINT = vpaint.ModelPaint

class MixedModelPaint(MixedPaint):
    MIXTURE = ModelMixture

class NewMixedColourDialogue(dialogue.Dialog):
    COLOUR = None
    def __init__(self, number, parent=None):
        dialogue.Dialog.__init__(self, title=_("New Mixed Colour: #{:03d}").format(number),
                            parent=parent,
                            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.REJECT,
                                     Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT)
                            )
        vbox = self.get_content_area()
        self.colour_description = entries.TextEntryAutoComplete(lexicon.COLOUR_NAME_LEXICON)
        self.colour_description.connect("new-words", lexicon.new_paint_words_cb)
        self.colour_description.connect("changed", self._description_changed_cb)
        self.set_response_sensitive(Gtk.ResponseType.ACCEPT, len(self.colour_description.get_text()) > 0)
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(_("Description:")), expand=False, fill=True, padding=0)
        hbox.pack_start(self.colour_description, expand=True, fill=True, padding=0)
        vbox.pack_start(hbox, expand=False, fill=True, padding=0)
        class ColourSpecifier(pedit.ColourSampleMatcher):
            COLOUR = self.COLOUR
        self.colour_specifier = ColourSpecifier(auto_match_on_paste=True)
        vbox.pack_start(self.colour_specifier, expand=True, fill=True, padding=0)
        button = Gtk.Button(_("Take Screen Sample"))
        button.connect("clicked", lambda _button: screen.take_screen_sample())
        vbox.pack_start(button, expand=False, fill=True, padding=0)
        vbox.show_all()
    def _description_changed_cb(self, widget):
        self.set_response_sensitive(Gtk.ResponseType.ACCEPT, len(self.colour_description.get_text()) > 0)


def paint_parts_adjustment():
    return Gtk.Adjustment(0, 0, 999, 1, 10, 0)

class PaintPartsSpinButton(Gtk.EventBox, actions.CAGandUIManager):
    UI_DESCR = """
        <ui>
            <popup name="paint_spinner_popup">
                <menuitem action="paint_colour_info"/>
                <menuitem action="remove_me"/>
            </popup>
        </ui>
        """
    def __init__(self, paint, sensitive=False, *kwargs):
        Gtk.EventBox.__init__(self)
        actions.CAGandUIManager.__init__(self, popup="/paint_spinner_popup")
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.set_size_request(85, 40)
        self.paint = paint
        self.entry = Gtk.SpinButton()
        self.entry.set_adjustment(paint_parts_adjustment())
        self.entry.set_numeric(True)
        self.entry.connect("button_press_event", self._button_press_cb)
        self.set_tooltip_text(str(paint))
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        hbox = Gtk.HBox()
        hbox.pack_start(coloured.ColouredLabel(self.paint.name, self.paint.rgb.gdk_color), expand=True, fill=True, padding=0)
        vbox = Gtk.VBox()
        vbox.pack_start(gpaint.ColouredRectangle(self.paint), expand=True, fill=True, padding=0)
        vbox.pack_start(self.entry, expand=False, fill=True, padding=0)
        vbox.pack_start(gpaint.ColouredRectangle(self.paint), expand=True, fill=True, padding=0)
        hbox.pack_start(vbox, expand=False, fill=True, padding=0)
        hbox.pack_start(gpaint.ColouredRectangle(self.paint, (5, -1)), expand=False, fill=True, padding=0)
        frame.add(hbox)
        self.add(frame)
        self.set_sensitive(sensitive)
        self.show_all()
    def populate_action_groups(self):
        """
        Populate action groups ready for UI initialization.
        """
        self.action_groups[actions.AC_DONT_CARE].add_actions(
            [
                ("paint_colour_info", Gtk.STOCK_INFO, None, None,
                 _("Detailed information for this paint colour."),
                 self._paint_colour_info_cb
                ),
                ("remove_me", Gtk.STOCK_REMOVE, None, None,
                 _("Remove this paint paint from the mixer."),
                ),
            ]
        )
    def get_parts(self):
        return self.entry.get_value_as_int()
    def set_parts(self, parts):
        return self.entry.set_value(parts)
    def divide_parts(self, divisor):
        return self.entry.set_value(self.entry.get_value_as_int() / divisor)
    def get_blob(self):
        return BLOB(self.paint, self.get_parts())
    def set_sensitive(self, sensitive):
        self.entry.set_sensitive(sensitive)
    def _paint_colour_info_cb(self, _action):
        gpaint.PaintColourInformationDialogue(self.paint).show()

class PaintPartsSpinButtonBox(Gtk.VBox):
    # TODO: implement PaintPartsSpinButtonBox() using Gtk.FlowBox
    """
    A dynamic array of coloured spinners
    """
    def __init__(self):
        Gtk.VBox.__init__(self)
        self.__spinbuttons = []
        self.__hboxes = []
        self.__count = 0
        self.__ncols = 6
        self.__sensitive = False
        self.__suppress_change_notification = False
    def set_sensitive(self, sensitive):
        self.__sensitive = sensitive
        for sb in self.__spinbuttons:
            sb.set_sensitive(sensitive)
    def add_paint(self, paint):
        """
        Add a spinner for the given paint to the box
        """
        spinbutton = PaintPartsSpinButton(paint, self.__sensitive)
        spinbutton.action_groups.connect_activate("remove_me", self._remove_me_cb, spinbutton)
        spinbutton.entry.connect("value-changed", self._spinbutton_value_changed_cb)
        self.__spinbuttons.append(spinbutton)
        self._pack_append(spinbutton)
        self.show_all()
    def _pack_append(self, spinbutton):
        if self.__count % self.__ncols == 0:
            self.__hboxes.append(Gtk.HBox())
            self.pack_start(self.__hboxes[-1], expand=False, fill=True, padding=0)
        self.__hboxes[-1].pack_start(spinbutton, expand=True, fill=True, padding=0)
        self.__count += 1
    def _unpack_all(self):
        """
        Unpack all the spinbuttons and hboxes
        """
        for hbox in self.__hboxes:
            for child in hbox.get_children():
                hbox.remove(child)
            self.remove(hbox)
        self.__hboxes = []
        self.__count = 0
    def _remove_me_cb(self, _action, spinbutton):
        """
        Signal anybody who cares that spinbutton.paint should be removed
        """
        self.emit("remove-paint", spinbutton.paint)
    def _spinbutton_value_changed_cb(self, spinbutton):
        """
        Signal those interested that our contributions have changed
        """
        if not self.__suppress_change_notification:
            self.emit("contributions-changed", self.get_contributions())
    def del_paint(self, paint):
        # do this the easy way by taking them all out and putting back
        # all but the one to be deleted
        self._unpack_all()
        for spinbutton in self.__spinbuttons[:]:
            if spinbutton.paint == paint:
                self.__spinbuttons.remove(spinbutton)
            else:
                self._pack_append(spinbutton)
        self.show_all()
    def get_paints(self):
        return [spinbutton.paint for spinbutton in self.__spinbuttons]
    def get_paints_with_zero_parts(self):
        return [spinbutton.paint for spinbutton in self.__spinbuttons if spinbutton.get_parts() == 0]
    def has_paint(self, paint):
        """
        Do we already contain the given paint?
        """
        for spinbutton in self.__spinbuttons:
            if spinbutton.paint == paint:
                return True
        return False
    def get_contributions(self):
        """
        Return a list of paint paints with non zero parts
        """
        return [spinbutton.get_blob() for spinbutton in self.__spinbuttons if spinbutton.get_parts() > 0]
    def divide_parts(self, divisor):
        if divisor is not None and divisor > 1:
            self.__suppress_change_notification = True
            for spinbutton in self.__spinbuttons:
                spinbutton.divide_parts(divisor)
            self.__suppress_change_notification = False
            self.emit("contributions-changed", self.get_contributions())
    def simplify_parts(self):
        self.divide_parts(mathx.gcd(*[sb.get_parts() for sb in self.__spinbuttons]))
    def reset_parts(self):
        """
        Reset all spinbutton values to zero
        """
        self.__suppress_change_notification = True
        for spinbutton in self.__spinbuttons:
            spinbutton.set_parts(0)
        self.__suppress_change_notification = False
        self.emit("contributions-changed", self.get_contributions())
GObject.signal_new("remove-paint", PaintPartsSpinButtonBox, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
GObject.signal_new("contributions-changed", PaintPartsSpinButtonBox, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))

class MatchedPaintListStore(gpaint.PaintListStore):
    COLUMN_DEFS = list()
    def __init__(self):
        gpaint.PaintListStore.__init__(self, GObject.TYPE_PYOBJECT)
    def append_paint(self, paint, target_colour):
        self.append([paint, target_colour])
    def get_paint_users(self, paint):
        return [row[0] for row in self if row[0].contains_paint(paint)]
    def get_target_colour(self, colour):
        """
        Return the target colour for the given colour
        """
        model_iter = self.get_paint_iter(colour)
        if model_iter is None:
            raise LookupError()
        return self[model_iter][1]
    def _notes_edited_cb(self, cell, path, new_text):
        self[path][0].notes = new_text

class MixedPaintComponentsListStore(gpaint.PaintListStore):
    COLUMN_DEFS = list()
    def __init__(self):
        gpaint.PaintListStore.__init__(self, int)
    def append_paint(self, paint, parts=0):
        self.append([paint, parts])
    def get_parts(self, paint):
        """
        Return the number of parts selected for the given paint
        """
        model_iter = self.get_paint_iter(paint)
        if model_iter is None:
            raise LookupError()
        return self[model_iter][1]
    def reset_parts(self):
        """
        Reset the number of parts for all colours to zero
        """
        model_iter = self.get_iter_first()
        while model_iter is not None:
            self[model_iter][1] = 0
            model_iter = self.iter_next(model_iter)
        self.emit("contributions-changed", [])
    def get_contributions(self):
        """
        Return a list of BLOB() tuples where parts is greater than zero
        """
        return [BLOB(row[0], row[1]) for row in self if row[1] > 0]
    def get_paint_users(self, paint):
        return [row[0] for row in self if row[0].contains_paint(paint)]
    def process_parts_change(self, contribution):
        """
        Work out contributions with modifications in contribution.
        This is necessary because the parts field in the model hasn't
        been updated yet as it causes a "jerky" appearance in the
        CellRendererSpin due to SpinButton being revreated every time
        an edit starts and updating the model causes restart of edit.
        """
        contributions = []
        for row in self:
            if row[0] == contribution.paint:
                if contribution.parts > 0:
                    contributions.append(contribution)
            elif row[1] > 0:
                contributions.append(BLOB(row[0], row[1]))
        self.emit("contributions-changed", contributions)
    def _parts_value_changed_cb(self, cell, path, spinbutton):
        """
        Change the model for a change to a spinbutton value
        """
        new_parts = spinbutton.get_value_as_int()
        row = self.get_row(self.get_iter(path))
        self.process_parts_change(BLOB(colour=row[0], parts=new_parts))
    def _notes_edited_cb(self, cell, path, new_text):
        self[path][0].notes = new_text
GObject.signal_new("contributions-changed", MixedPaintComponentsListStore, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT, ))

def generate_components_list_spec(view, model):
    """
    Generate the SPECIFICATION for a mixed colour components list
    """
    parts_col_spec = tlview.ColumnSpec(
        title =_("Parts"),
        properties={},
        sort_key_function=lambda row: row[1],
        cells=[
            tlview.CellSpec(
                cell_renderer_spec=tlview.CellRendererSpec(
                    cell_renderer=Gtk.CellRendererText,
                    expand=None,
                    properties={"width-chars" : 8},
                    start=False
                ),
                cell_data_function_spec=None,
                attributes={"text" : 1}
            ),
        ]
    )
    name_col_spec = gpaint.tns_paint_list_column_spec(gpaint.TNS(_("Name"), "name", {"expand" : True}, lambda row: row[0].name))
    attr_cols_specs = gpaint.paint_list_column_specs(model)
    return tlview.ViewSpec(
        properties={},
        selection_mode=Gtk.SelectionMode.SINGLE,
        columns=[parts_col_spec, name_col_spec] + attr_cols_specs
    )

class MixedPaintComponentsListView(gpaint.PaintListView):
    UI_DESCR = """
    <ui>
        <popup name="paint_list_popup">
            <menuitem action="show_paint_details"/>
        </popup>
    </ui>
    """
    MODEL = MixedPaintComponentsListStore
    SPECIFICATION = generate_components_list_spec

recollect.define("mixed_colour_information", "last_size", recollect.Defn(eval, ""))

class MixedPaintInformationDialogue(dialogue.Dialog):
    """
    A dialog to display the detailed information for a mixed colour
    """
    COMPONENT_LIST_VIEW = None
    def __init__(self, colour, target_colour=None, parent=None):
        dialogue.Dialog.__init__(self, title=_("Mixed Colour: {}").format(colour.name), parent=parent)
        last_size = recollect.get("mixed_colour_information", "last_size")
        if last_size:
            self.set_default_size(*last_size)
        vbox = self.get_content_area()
        vbox.pack_start(coloured.ColouredLabel(colour.name, colour.gdk_color), expand=False, fill=True, padding=0)
        vbox.pack_start(coloured.ColouredLabel(colour.notes, colour.gdk_color), expand=False, fill=True, padding=0)
        if target_colour:
            vbox.pack_start(coloured.ColouredLabel(_("Target"), target_colour.gdk_color), expand=False, fill=True, padding=0)
        if hasattr(colour, "warmth"):
            vbox.pack_start(gpaint.HCVWDisplay(colour=colour, target_colour=target_colour), expand=False, fill=True, padding=0)
        else:
            vbox.pack_start(gpaint.HCVDisplay(colour=colour, target_colour=target_colour), expand=False, fill=True, padding=0)
        if hasattr(colour, "characteristics"):
            for characteristic in colour.characteristics:
                vbox.pack_start(Gtk.Label(characteristic.description()), expand=False, fill=True, padding=0)
        self.cview = self.COMPONENT_LIST_VIEW()
        for component in colour.blobs:
            self.cview.model.append(component)
        vbox.pack_start(self.cview, expand=False, fill=True, padding=0)
        self.connect("configure-event", self._configure_event_cb)
        vbox.show_all()
    def _configure_event_cb(self, widget, allocation):
        recollect.set("mixed_colour_information", "last_size", "({0.width}, {0.height})".format(allocation))
    def unselect_all(self):
        self.cview.get_selection().unselect_all()

class MatchedModelPaintListStore(MatchedPaintListStore):
    COLUMN_DEFS = [
            gpaint.TNS(_("Value"), "value", {}, lambda row: row[0].value),
            gpaint.TNS(_("Hue"), "hue", {}, lambda row: row[0].hue),
        ] + gpaint.paint_characteristics_tns_list(vpaint.ModelPaint)

def notes_cell_data_func(column, cell, model, model_iter, *args):
    colour = model[model_iter][0]
    cell.set_property("text", colour.notes)
    cell.set_property("background-gdk", colour.gdk_color)
    cell.set_property("foreground-gdk", colour.best_foreground_gdk_color())

def match_cell_data_func(column, cell, model, model_iter, attribute):
    colour = model[model_iter][1]
    cell.set_property("background-gdk", colour.gdk_color)

def generate_matched_paint_list_spec(view, model):
    """
    Generate the specification for a paint colour parts list
    """
    matched_col_spec = tlview.ColumnSpec(
        title =_("Matched"),
        properties={},
        sort_key_function=lambda row: row[1].hue,
        cells=[
            tlview.CellSpec(
                cell_renderer_spec=tlview.CellRendererSpec(
                    cell_renderer=Gtk.CellRendererText,
                    expand=None,
                    properties=None,
                    start=False
                ),
                cell_data_function_spec=tlview.CellDataFunctionSpec(
                    function=match_cell_data_func,
                ),
                attributes={}
            ),
        ]
    )
    notes_col_spec = tlview.ColumnSpec(
        title =_("Notes"),
        properties={"resizable" : True, "expand" : True},
        sort_key_function=lambda row: row[0].notes,
        cells=[
            tlview.CellSpec(
                cell_renderer_spec=tlview.CellRendererSpec(
                    cell_renderer=Gtk.CellRendererText,
                    expand=None,
                    properties={"editable" : True, },
                    signal_handlers = {"edited" : model._notes_edited_cb},
                    start=False
                ),
                cell_data_function_spec=tlview.CellDataFunctionSpec(
                    function=notes_cell_data_func,
                ),
                attributes={}
            ),
        ]
    )
    name_col_spec = gpaint.tns_paint_list_column_spec(gpaint.TNS(_("Name"), "name", {}, lambda row: row[0].name))
    attr_cols_specs = gpaint.paint_list_column_specs(model)
    return tlview.ViewSpec(
        properties={},
        selection_mode=Gtk.SelectionMode.MULTIPLE,
        columns=[name_col_spec, matched_col_spec, notes_col_spec] + attr_cols_specs
    )

class MatchedPaintListView(gpaint.PaintListView):
    UI_DESCR = """
    <ui>
        <popup name="paint_list_popup">
            <menuitem action="show_paint_details"/>
            <menuitem action="remove_selected_paints"/>
        </popup>
    </ui>
    """
    MODEL = MatchedPaintListStore
    SPECIFICATION = generate_matched_paint_list_spec
    MIXED_PAINT_INFORMATION_DIALOGUE = MixedPaintInformationDialogue
    def __init__(self, *args, **kwargs):
        gpaint.PaintListView.__init__(self, *args, **kwargs)
    def get_selected_paints_and_targets(self):
        """Return the currently selected paints as a list.
        """
        model, paths = self.get_selection().get_selected_rows()
        return [(model[p][0], model[p][0]) for p in paths]
    def _show_paint_details_cb(self, _action):
        paint, target_colour = self.get_selected_paints_and_targets()[0]
        self.MIXED_PAINT_INFORMATION_DIALOGUE(paint, target_colour).show()

class MixedModelPaintInformationDialogue(MixedPaintInformationDialogue):
    class COMPONENT_LIST_VIEW(MixedPaintComponentsListView):
        class MODEL(MixedPaintComponentsListStore):
            COLUMN_DEFS = gpaint.ModelPaintListStore.COLUMN_DEFS[1:]

class MatchedModelPaintListView(MatchedPaintListView):
    UI_DESCR = """
    <ui>
        <popup name="paint_list_popup">
            <menuitem action="show_paint_details"/>
            <menuitem action="remove_selected_paints"/>
        </popup>
    </ui>
    """
    MODEL = MatchedModelPaintListStore
    MIXED_PAINT_INFORMATION_DIALOGUE = MixedModelPaintInformationDialogue

recollect.define('reference_image_viewer', 'last_file', recollect.Defn(str, ''))
recollect.define('reference_image_viewer', 'last_size', recollect.Defn(str, ''))

class ReferenceImageViewer(Gtk.Window, actions.CAGandUIManager):
    """
    A top level window for a colour sample file
    """
    UI_DESCR = """
    <ui>
      <menubar name="reference_image_menubar">
        <menu action="reference_image_file_menu">
          <menuitem action="open_reference_image_file"/>
          <menuitem action="close_reference_image_viewer"/>
        </menu>
      </menubar>
    </ui>
    """
    TITLE_TEMPLATE = _("mcmmtk: Reference Image: {}")
    def __init__(self, parent):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        actions.CAGandUIManager.__init__(self)
        last_size = recollect.get("reference_image_viewer", "last_size")
        if last_size:
            self.set_default_size(*eval(last_size))
        self.set_icon_from_file(icons.APP_ICON_FILE)
        self.set_size_request(300, 200)
        last_image_file = recollect.get("reference_image_viewer", "last_file")
        if os.path.isfile(last_image_file):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(last_image_file)
            except GLib.GError:
                pixbuf = None
                last_image_file = None
        else:
            pixbuf = None
            last_image_file = None
        self.set_title(self.TITLE_TEMPLATE.format(None if last_image_file is None else os.path.relpath(last_image_file)))
        self.ref_image = iview.PixbufView()
        self._menubar = self.ui_manager.get_widget("/reference_image_menubar")
        self.buttons = self.ref_image.action_groups.create_action_button_box([
            "zoom_in",
            "zoom_out",
        ])
        vbox = Gtk.VBox()
        vbox.pack_start(self._menubar, expand=False, fill=True, padding=0)
        vbox.pack_start(self.ref_image, expand=True, fill=True, padding=0)
        vbox.pack_start(self.buttons, expand=False, fill=True, padding=0)
        self.add(vbox)
        self.set_transient_for(parent)
        self.connect("size-allocate", self._size_allocation_cb)
        self.show_all()
        if pixbuf is not None:
            self.ref_image.set_pixbuf(pixbuf)
    def _size_allocation_cb(self, widget, allocation):
        recollect.set("reference_image_viewer", "last_size", "({0.width}, {0.height})".format(allocation))
    def populate_action_groups(self):
        self.action_groups[actions.AC_DONT_CARE].add_actions([
            ("reference_image_file_menu", None, _("File")),
            ("open_reference_image_file", Gtk.STOCK_OPEN, None, None,
            _("Load an image file for reference."),
            self._open_reference_image_file_cb),
            ("close_reference_image_viewer", Gtk.STOCK_CLOSE, None, None,
            _("Close this window."),
            self._close_reference_image_viewer_cb),
        ])
    def _open_reference_image_file_cb(self, _action):
        """
        Ask the user for the name of the file then open it.
        """
        parent = self.get_toplevel()
        dlg = Gtk.FileChooserDialog(
            title=_("Open Image File"),
            parent=parent if isinstance(parent, Gtk.Window) else None,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK)
        )
        last_image_file = recollect.get("reference_image_viewer", "last_file")
        last_samples_dir = None if last_image_file is None else os.path.dirname(last_image_file)
        if last_samples_dir:
            dlg.set_current_folder(last_samples_dir)
        gff = Gtk.FileFilter()
        gff.set_name(_("Image Files"))
        gff.add_pixbuf_formats()
        dlg.add_filter(gff)
        if dlg.run() == Gtk.ResponseType.OK:
            filepath = dlg.get_filename()
            dlg.destroy()
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(filepath)
            except GLib.GError:
                msg = _("{}: Problem extracting image from file.").format(filepath)
                dialogue.MessageDialog(type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE, text=msg).run()
                return
            recollect.set("reference_image_viewer", "last_file", filepath)
            self.set_title(self.TITLE_TEMPLATE.format(None if filepath is None else os.path.relpath(filepath)))
            self.ref_image.set_pixbuf(pixbuf)
        else:
            dlg.destroy()
    def _close_reference_image_viewer_cb(self, _action):
        self.get_toplevel().destroy()

def pango_rgb_str(rgb, bits_per_channel=16):
    """
    Convert an rgb to a Pango colour description string
    """
    string = '#'
    for i in range(3):
        string += '{0:02X}'.format(rgb[i] >> (bits_per_channel - 8))
    return string

recollect.define("mixer", "hpaned_position", recollect.Defn(int, -1))
recollect.define("mixer", "vpaned_position", recollect.Defn(int, -1))

class PaintMixer(Gtk.VBox, actions.CAGandUIManager, dialogue.AskerMixin, dialogue.ReporterMixin):
    PAINT = None
    MATCHED_PAINT_LIST_VIEW = None
    PAINT_SERIES_MANAGER = None
    MIXED_PAINT_INFORMATION_DIALOGUE = None
    MIXTURE = None
    MIXED_PAINT = None
    UI_DESCR = """
    <ui>
        <menubar name="mixer_menubar">
            <menu action="mixer_file_menu">
                <menuitem action="print_mixer"/>
                <menuitem action="quit_mixer"/>
            </menu>
            <menu action="mixer_series_manager_menu">
                <menuitem action="mixer_load_paint_series"/>
            </menu>
            <menu action="reference_resource_menu">
                <menuitem action="open_reference_image_viewer"/>
            </menu>
        </menubar>
    </ui>
    """
    AC_HAVE_MIXTURE, AC_MASK = actions.ActionCondns.new_flags_and_mask(1)
    AC_HAVE_TARGET, AC_DONT_HAVE_TARGET, AC_TARGET_MASK = actions.ActionCondns.new_flags_and_mask(2)
    def __init__(self):
        Gtk.VBox.__init__(self)
        self.paint_series_manager = self.PAINT_SERIES_MANAGER()
        self.paint_series_manager.connect("add-paint-colours", self._add_colours_to_mixer_cb)
        actions.CAGandUIManager.__init__(self)
        self.action_groups.update_condns(actions.MaskedCondns(self.AC_DONT_HAVE_TARGET, self.AC_TARGET_MASK))
        # Components
        from . import standards
        self.standards_manager = standards.PaintStandardsManager()
        self.notes = entries.TextEntryAutoComplete(lexicon.GENERAL_WORDS_LEXICON)
        self.notes.connect("new-words", lexicon.new_general_words_cb)
        self.next_name_label = Gtk.Label(label=_("#???:"))
        self.current_target_colour = None
        self.current_colour_description = entries.TextEntryAutoComplete(lexicon.COLOUR_NAME_LEXICON)
        self.current_colour_description.connect("new-words", lexicon.new_paint_words_cb)
        self.mixpanel = gpaint.ColourMatchArea()
        self.mixpanel.set_size_request(240, 240)
        self.hcvw_display = gpaint.HCVDisplay()
        self.paint_colours = PaintPartsSpinButtonBox()
        self.paint_colours.connect("remove-paint", self._remove_paint_colour_cb)
        self.paint_colours.connect("contributions-changed", self._contributions_changed_cb)
        self.mixed_colours = self.MATCHED_PAINT_LIST_VIEW.MODEL()
        self.mixed_colours_view = self.MATCHED_PAINT_LIST_VIEW(self.mixed_colours)
        self.mixed_colours_view.action_groups.connect_activate("remove_selected_paints", self._remove_mixed_colours_cb)
        self.mixed_count = 0
        self.wheels = gpaint.HueWheelNotebook()
        self.wheels.set_size_request(360, 360)
        self.wheels.set_wheels_colour_info_acb(self._show_wheel_colour_details_cb)
        self.buttons = self.action_groups.create_action_button_box([
            "new_mixed_colour",
            "new_mixed_standard_colour",
            "accept_mixed_colour",
            "simplify_contributions",
            "reset_contributions",
            "remove_unused_paints"
        ])
        menubar = self.ui_manager.get_widget("/mixer_menubar")
        # Lay out components
        self.pack_start(menubar, expand=False, fill=True, padding=0)
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(_("Notes:")), expand=False, fill=True, padding=0)
        hbox.pack_start(self.notes, expand=True, fill=True, padding=0)
        self.pack_start(hbox, expand=False, fill=True, padding=0)
        hpaned = Gtk.HPaned()
        hpaned.pack1(self.wheels, resize=True, shrink=False)
        vbox = Gtk.VBox()
        vhbox = Gtk.HBox()
        vhbox.pack_start(self.next_name_label, expand=False, fill=True, padding=0)
        vhbox.pack_start(self.current_colour_description, expand=True, fill=True, padding=0)
        vbox.pack_start(vhbox, expand=False, fill=True, padding=0)
        vbox.pack_start(self.hcvw_display, expand=False, fill=True, padding=0)
        vbox.pack_start(gutils.wrap_in_frame(self.mixpanel, Gtk.ShadowType.ETCHED_IN), expand=True, fill=True, padding=0)
        hpaned.pack2(vbox, resize=True, shrink=False)
        vpaned = Gtk.VPaned()
        vpaned.pack1(hpaned, resize=True, shrink=False)
        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(_("Paints:")), expand=False, fill=True, padding=0)
        hbox.pack_start(self.paint_colours, expand=True, fill=True, padding=0)
        vbox.pack_start(hbox, expand=False, fill=True, padding=0)
        vbox.pack_start(self.buttons, expand=False, fill=True, padding=0)
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.mixed_colours_view), expand=True, fill=True, padding=0)
        vpaned.pack2(vbox, resize=True, shrink=False)
        self.pack_start(vpaned, expand=True, fill=True, padding=0)
        vpaned.set_position(recollect.get("mixer", "vpaned_position"))
        hpaned.set_position(recollect.get("mixer", "hpaned_position"))
        vpaned.connect("notify", self._paned_notify_cb)
        hpaned.connect("notify", self._paned_notify_cb)
        self.connect("key-press-event", self.handle_key_press_cb)
        msmm = self.ui_manager.get_widget("/mixer_menubar/mixer_series_manager_menu").get_submenu()
        msmm.prepend(self.paint_series_manager.open_menu_item)
        msmm.append(self.paint_series_manager.remove_menu_item)
        menubar.insert(self.standards_manager.menu, 2)
        self.show_all()
        self.recalculate_colour([])

    def handle_key_press_cb(self, widget, event):
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval in [Gdk.KEY_q, Gdk.KEY_Q]:
                widget._quit_mixer()
                return True
        return False

    def _paned_notify_cb(self, widget, parameter):
        if parameter.name == "position":
            if isinstance(widget, Gtk.HPaned):
                recollect.set("mixer", "hpaned_position", str(widget.get_position()))
            else:
                recollect.set("mixer", "vpaned_position", str(widget.get_position()))

    def populate_action_groups(self):
        """
        Set up the actions for this component
        """
        self.action_groups[actions.AC_DONT_CARE].add_actions([
            ("mixer_file_menu", None, _("File")),
            ("mixer_series_manager_menu", None, _("Paint Colour Series")),
            ("reference_resource_menu", None, _("Reference Resources")),
            ("remove_unused_paints", None, _("Remove Unused Paints"), None,
             _("Remove all unused paints from the mixer."),
             self._remove_unused_paints_cb
            ),
            ("mixer_load_paint_series", None, _("Load"), None,
             _("Load a paint series from a file."),
             lambda _action: self.paint_series_manager.add_paint_series()
            ),
            ("quit_mixer", Gtk.STOCK_QUIT, None, None,
             _("Quit this program."),
             lambda _action: self._quit_mixer()
            ),
            ("open_reference_image_viewer", None, _("Open Image Viewer"), None,
             _("Open a tool for viewing reference images."),
             self._open_reference_image_viewer_cb
            ),
            ("print_mixer", Gtk.STOCK_PRINT, None, None,
             _("Print a text description of the mixer."),
             self._print_mixer_cb
            ),
        ])
        self.action_groups[self.AC_HAVE_MIXTURE].add_actions([
            ("simplify_contributions", None, _("Simplify"), None,
            _("Simplify all paint contributions (by dividing by their greatest common divisor)."),
            self._simplify_contributions_cb),
            ("reset_contributions", None, _("Reset"), None,
            _("Reset all paint contributions to zero."),
            self._reset_contributions_cb),
        ])
        self.action_groups[self.AC_HAVE_MIXTURE|self.AC_HAVE_TARGET].add_actions([
            ("accept_mixed_colour", None, _("Accept"), None,
            _("Accept/finalise this colour and add it to the list of  mixed colours."),
            self._accept_mixed_colour_cb),
        ])
        self.action_groups[self.AC_DONT_HAVE_TARGET].add_actions([
            ("new_mixed_colour", None, _("New"), None,
             _("Start working on a new mixed colour."),
             self._new_mixed_colour_cb
            ),
            ("new_mixed_standard_colour", None, _("New (From Standards)"), None,
             _("Start working on a new mixed colour to replicate an existing standard."),
             lambda _action: self._new_mixed_standard_colour()
            ),
        ])
    def _show_wheel_colour_details_cb(self, _action, wheel):
        colour = wheel.popup_colour
        if hasattr(colour, "blobs"):
            self.MIXED_PAINT_INFORMATION_DIALOGUE(colour, self.mixed_colours.get_target_colour(colour)).show()
        elif isinstance(colour, vpaint.TargetColour):
            gpaint.TargetColourInformationDialogue(colour).show()
        else:
            gpaint.PaintColourInformationDialogue(colour).show()
        return True
    def __str__(self):
        paint_colours = self.paint_colours.get_colours()
        if len(paint_colours) == 0:
            return _("Empty Mix/Match Description")
        string = _("Paint Colours:\n")
        for pcol in paint_colours:
            string += "{0}: {1}: {2}\n".format(pcol.name, pcol.series.series_id.maker, pcol.series.series_id.name)
        num_mixed_colours = len(self.mixed_colours)
        if num_mixed_colours == 0:
            return string
        # Print the list in the current order chosen by the user
        string += _("Mixed Colours:\n")
        for mc in self.mixed_colours.get_colours():
            string += "{0}: {1}\n".format(mc.name, round(mc.value, 2))
            for cc, parts in mc.blobs:
                if hasattr(cc, "series"):
                    string += "\t {0}:\t{1}: {2}: {3}\n".format(parts, cc.name, cc.series.series_id.maker, cc.series.series_id.name)
                else:
                    string += "\t {0}:\t{1}\n".format(parts, cc.name)
        return string
    def pango_markup_chunks(self):
        """
        Format the palette description as a list of Pango markup chunks
        """
        paint_colours = self.paint_colours.get_paints()
        if len(paint_colours) == 0:
            return [cgi.escape(_("Empty Mix/Match Description"))]
        # TODO: add paint series data in here
        string = "<b>" + cgi.escape(_("Mix/Match Description:")) + "</b> "
        string += cgi.escape(time.strftime("%X: %A %x")) + "\n"
        if self.notes.get_text_length() > 0:
            string += "\n{0}\n".format(cgi.escape(self.notes.get_text()))
        chunks = [string]
        string = "<b>" + cgi.escape(_("Paint Colours:")) + "</b>\n\n"
        for pcol in paint_colours:
            string += "<span background=\"{0}\">\t</span> ".format(pango_rgb_str(pcol.rgb16))
            string += "{0}\n".format(cgi.escape(pcol.name))
        chunks.append(string)
        string = "<b>" + cgi.escape(_("Mixed Colours:")) + "</b>\n\n"
        for tmc in self.mixed_colours:
            mc = tmc[0]
            tc = tmc[1]
            string += "<span background=\"{0}\">\t</span>".format(pango_rgb_str(mc.rgb16))
            string += "<span background=\"{0}\">\t</span>".format(pango_rgb_str(mc.value_rgb.rgb16))
            string += "<span background=\"{0}\">\t</span>".format(pango_rgb_str(mc.hue_rgb.rgb16))
            string += " {0}: {1}\n".format(cgi.escape(mc.name), cgi.escape(mc.notes))
            string += "<span background=\"{0}\">\t</span>".format(pango_rgb_str(tc.rgb16))
            string += "<span background=\"{0}\">\t</span>".format(pango_rgb_str(tc.value_rgb.rgb16))
            string += "<span background=\"{0}\">\t</span> Target Colour\n".format(pango_rgb_str(tc.hue.rgb.rgb16))
            for blob in mc.blobs:
                string += "{0: 7d}:".format(blob.parts)
                string += "<span background=\"{0}\">\t</span>".format(pango_rgb_str(blob.paint.rgb16))
                string += " {0}\n".format(cgi.escape(blob.paint.name))
            chunks.append(string)
            string = "" # Necessary because we put header in the first chunk
        return chunks
    def _contributions_changed_cb(self, _widget, contributions):
        self.recalculate_colour(contributions)
    def recalculate_colour(self, contributions):
        if len(contributions) > 0:
            new_colour = self.MIXTURE(contributions)
            self.mixpanel.set_bg_colour(new_colour.rgb)
            self.hcvw_display.set_colour(new_colour)
            self.action_groups.update_condns(actions.MaskedCondns(self.AC_HAVE_MIXTURE, self.AC_MASK))
        else:
            self.mixpanel.set_bg_colour(None)
            self.hcvw_display.set_colour(None)
            self.action_groups.update_condns(actions.MaskedCondns(0, self.AC_MASK))
    def _accept_mixed_colour_cb(self,_action):
        self.simplify_parts()
        paint_contribs = self.paint_colours.get_contributions()
        if len(paint_contribs) < 1:
            return
        self.mixed_count += 1
        name = _("Mix #{:03d}").format(self.mixed_count)
        notes = self.current_colour_description.get_text()
        new_colour =  self.MIXED_PAINT(blobs=paint_contribs, name=name, notes=notes)
        target_name = _("Target #{:03d}").format(self.mixed_count)
        target_colour = vpaint.ModelTargetColour(target_name, self.current_target_colour, self.current_colour_description.get_text())
        self.mixed_colours.append_paint(new_colour, target_colour)
        self.wheels.add_paint(new_colour)
        self.reset_parts()
        self.paint_colours.set_sensitive(False)
        self.mixpanel.clear()
        self.current_colour_description.set_text("")
        self.wheels.add_target_colour(name, target_colour)
        self.current_target_colour = None
        self.hcvw_display.set_colour(None)
        self.hcvw_display.set_target_colour(None)
        self.wheels.unset_crosshair()
        self.paint_series_manager.unset_target_colour()
        self.action_groups.update_condns(actions.MaskedCondns(self.AC_DONT_HAVE_TARGET, self.AC_TARGET_MASK))
        self.next_name_label.set_text(_("#???:"))
        self.current_colour_description.set_text("")
    def _set_new_mixed_colour(self, *, description, colour):
        self.current_colour_description.set_text(description)
        self.current_target_colour = colour
        self.mixpanel.set_target_colour(self.current_target_colour)
        self.hcvw_display.set_target_colour(self.current_target_colour)
        self.wheels.set_crosshair(self.current_target_colour)
        self.paint_series_manager.set_target_colour(self.current_target_colour)
        self.action_groups.update_condns(actions.MaskedCondns(self.AC_HAVE_TARGET, self.AC_TARGET_MASK))
        self.next_name_label.set_text(_("#{:03d}:").format(self.mixed_count + 1))
        self.paint_colours.set_sensitive(True)
    def _new_mixed_colour_cb(self,_action):
        class Dialogue(NewMixedColourDialogue):
            COLOUR = self.PAINT.COLOUR
        dlg = Dialogue(self.mixed_count + 1, self.get_parent())
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            descr = dlg.colour_description.get_text()
            assert len(descr) > 0
            self._set_new_mixed_colour(description=descr, colour=dlg.colour_specifier.colour)
        dlg.destroy()
    def _new_mixed_standard_colour(self):
        standard_paint_id = self.standards_manager.ask_standard_paint_name()
        if standard_paint_id:
            standard_paint = self.standards_manager.get_standard_paint(standard_paint_id)
            if standard_paint:
                self._set_new_mixed_colour(description=standard_paint_id, colour=standard_paint.colour)
            else:
                self.inform_user(_("{}: unknown paint standard identifier").format(standard_paint_id))
    def reset_parts(self):
        self.paint_colours.reset_parts()
    def _reset_contributions_cb(self, _action):
        self.reset_parts()
    def simplify_parts(self):
        self.paint_colours.simplify_parts()
    def _simplify_contributions_cb(self, _action):
        self.simplify_parts()
    def add_paint(self, paint_colour):
        self.paint_colours.add_paint(paint_colour)
        self.wheels.add_paint(paint_colour)
    def del_paint(self, paint_colour):
        self.paint_colours.del_paint(paint_colour)
        self.wheels.del_paint(paint_colour)
    def del_mixed(self, mixed):
        self.mixed_colours.remove_colour(mixed)
        self.wheels.del_paint(mixed)
        self.wheels.del_target_colour(mixed.name)
    def _add_colours_to_mixer_cb(self, selector, colours):
        for pcol in colours:
            if not self.paint_colours.has_paint(pcol):
                self.add_paint(pcol)
    def _remove_paint_colour_cb(self, widget, colour):
        """
        Respond to a request from a paint colour to be removed
        """
        users = self.mixed_colours.get_paint_users(colour)
        if len(users) > 0:
            string = _("Colour: \"{0}\" is used in:\n").format(colour)
            for user in users:
                string += "\t{0}\n".format(user.name)
            dlg = dialogue.ScrolledMessageDialog(text=string)
            Gdk.beep()
            dlg.run()
            dlg.destroy()
        else:
            self.del_paint(colour)
    def _remove_mixed_colours_cb(self, _action):
        colours = self.mixed_colours_view.get_selected_colours()
        if len(colours) == 0:
            return
        msg = _("The following mixed colours are about to be deleted:\n")
        for colour in colours:
            msg += "\t{0}: {1}\n".format(colour.name, colour.notes)
        msg += _("and will not be recoverable. OK?")
        if self.ask_ok_cancel(msg):
            for colour in colours:
                self.del_mixed(colour)
    def _remove_unused_paints_cb(self, _action):
        paints = self.paint_colours.get_paints_with_zero_parts()
        for paint in paints:
            if len(self.mixed_colours.get_paint_users(paint)) == 0:
                self.del_paint(paint)
    def _print_mixer_cb(self, _action):
        """
        Print the mixer as simple text
        """
        # TODO: make printing more exotic
        printer.print_markup_chunks(self.pango_markup_chunks())
    def _open_reference_image_viewer_cb(self, _action):
        """
        Launch a window containing a reference image viewer
        """
        ReferenceImageViewer(self.get_toplevel()).show()
    def _quit_mixer(self):
        """
        Exit the program
        """
        # TODO: add checks for unsaved work in mixer before exiting
        Gtk.main_quit()
