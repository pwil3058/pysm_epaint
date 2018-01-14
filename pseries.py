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

"""Manage/Display Paint Series Data
"""

__all__ = []
__author__ = "Peter Williams <pwil3058@gmail.com>"

import collections
import hashlib
import os
import re

from gi.repository import GObject
from gi.repository import Gtk

from ..gtx import actions
from ..gtx import dialogue
from ..gtx import icons
from ..gtx import gutils
from ..gtx import recollect

from . import gpaint
from . import pedit

from .. import SYS_DATA_DIR_PATH
from .. import CONFIG_DIR_PATH

IDEAL_PAINTS_FILE_PATH = os.sep.join([SYS_DATA_DIR_PATH, "ideal.psd"])
SERIES_FILES_FILE_PATH = os.sep.join([CONFIG_DIR_PATH, "paint_series_files"])

def read_series_file_names():
    series_file_names = []
    if os.path.isfile(SERIES_FILES_FILE_PATH):
        for line in open(SERIES_FILES_FILE_PATH, "r").readlines():
            sf_name = line.strip()
            if len(line) == 0:
                continue
            series_file_names.append(sf_name)
    elif os.path.isfile(IDEAL_PAINTS_FILE_PATH):
        series_file_names.append(IDEAL_PAINTS_FILE_PATH)
    return series_file_names

def write_series_file_names(sf_names):
    fobj = open(SERIES_FILES_FILE_PATH, "w")
    for sf_name in sf_names:
        fobj.write(sf_name)
        fobj.write(os.linesep)
    fobj.close()

SERIES_ID = collections.namedtuple("SERIES_ID", ["maker", "name"])

class SeriesPaint(collections.namedtuple("SeriesPaint", ["series", "paint"])):
    @property
    def id(self):
        return (self.series, self.paint.name)
    def __getattr__(self, attr_name):
        return getattr(self.paint, attr_name)
    def __str__(self):
        return self.name + " ({0}: {1})".format(*self.series.series_id)
    def __len__(self):
        return len(str(self))
    def __repr__(self):
        return "SeriesPaint(series={}, paint={})".format(self.series.series_id, repr(self.paint))

class PaintSeries:
    # No i18n for these strings
    OWNER_LABEL = "Manufacturer"
    NAME_LABEL = "Series"
    class ParseError(Exception):
        pass
    def __init__(self, maker, name, paints=None):
        self.series_id = SERIES_ID(maker=maker, name=name)
        self.__paints = {}
        if paints:
            for paint in paints:
                self.add_paint(paint)
    def __lt__(self, other):
        if self.series_id.maker < other.series_id.maker:
            return True
        elif self.series_id.maker > other.series_id.maker:
            return False
        return self.series_id.name < other.series_id.name
    def add_paint(self, paint):
        self.__paints[paint.name] = paint
    def definition_text(self):
        string = "{0}: {1}\n".format(self.OWNER_LABEL, self.series_id.maker)
        string += "{0}: {1}\n".format(self.NAME_LABEL, self.series_id.name)
        for paint in sorted(self.__paints.values(), key=lambda x: x.name):
            string += "{0}\n".format(repr(paint))
        return string
    def iter_names(self):
        return self.__paints.keys()
    def iter_paints(self):
        return self.__paints.values()
    def iter_series_paints(self):
        return (SeriesPaint(self, value) for value in self.__paints.values())
    def get_paint(self, name):
        return self.__paints.get(name, None)
    def get_series_paint(self, name):
        paint = self.__paints.get(name, None)
        return None if paint is None else SeriesPaint(self, paint)
    @classmethod
    def fm_definition(cls, definition_text):
        lines = definition_text.splitlines()
        if len(lines) < 2:
            raise cls.ParseError(_("Too few lines: {0}.".format(len(lines))))
        mfkr_name = None
        series_name = None
        for line in lines[:2]:
            match = re.match("^Manufacturer:\s+(\S.*)\s*$", line)
            if match:
                mfkr_name = match.group(1)
            else:
                match = re.match("^Series:\s+(\S.*)\s*$", line)
                if match:
                    series_name = match.group(1)
        if not mfkr_name:
            if not series_name:
                raise cls.ParseError(_("Neither manufacturer nor series name found."))
            else:
                raise cls.ParseError(_("Manufacturer not found."))
        elif not series_name:
            raise cls.ParseError(_("Series name not found."))
        return cls(maker=mfkr_name, name=series_name, paints=cls.paints_fm_definition(lines[2:]))

class PaintSeriesEditor(pedit.PaintCollectionEditor):
    PAINT_EDITOR = None
    PAINT_LIST_NOTEBOOK = None
    PAINT_COLLECTION = None
    RECOLLECT_SECTION = "editor"
    FILE_NAME_PROMPT = _("Paint Series Description File:")
    LABEL = _("Paint Series Editor")

    def load_fm_file(self, filepath):
        try:
            with open(filepath, "r") as fobj:
                text = fobj.read()
        except IOError as edata:
            return self.report_io_error(edata)
        try:
            series = self.PAINT_COLLECTION.fm_definition(text)
        except self.PAINT_COLLECTION.ParseError as edata:
            return self.alert_user(_("Format Error:  {}: {}").format(edata, filepath))
        # All OK so clear the paint editor and ditch the current colours
        self.paint_editor.reset()
        self._set_current_extant_paint(None)
        self.paint_colours.clear()
        # and load the new ones
        for paint in series.iter_paints():
            self.paint_colours.add_paint(paint)
        self.proprietor_name.set_text(series.series_id.maker)
        self.collection_name.set_text(series.series_id.name)
        self.set_file_path(filepath)
        self.saved_hash = hashlib.sha1(text.encode()).digest()
        self.set_status_indicator(clean=True)

    def get_definition_text(self):
        maker = self.proprietor_name.get_text()
        name = self.collection_name.get_text()
        series = self.PAINT_COLLECTION(maker=maker, name=name, paints=self.paint_colours.iter_paints())
        return series.definition_text()

recollect.define("paint_colour_selector", "hpaned_position", recollect.Defn(int, 400))
recollect.define("paint_colour_selector", "last_size", recollect.Defn(str, "(780, 480)"))

class PaintSelector(Gtk.VBox):
    """
    A widget for adding paint colours to the mixer
    """
    SELECT_PAINT_LIST_VIEW = None
    def __init__(self, paint_series):
        Gtk.VBox.__init__(self)
        # components
        self.wheels = gpaint.HueWheelNotebook(popup="/colour_wheel_AI_popup")
        self.wheels.set_wheels_add_paint_acb(self._add_wheel_colour_to_mixer_cb)
        self.paint_colours_view = self.SELECT_PAINT_LIST_VIEW()
        self.paint_colours_view.set_size_request(240, 360)
        model = self.paint_colours_view.get_model()
        for paint in paint_series.iter_series_paints():
            model.append_paint(paint)
            self.wheels.add_paint(paint)
        maker = Gtk.Label(label=_("Manufacturer: {0}".format(paint_series.series_id.maker)))
        sname = Gtk.Label(label=_("Series Name: {0}".format(paint_series.series_id.name)))
        # make connections
        self.paint_colours_view.action_groups.connect_activate("add_paints_to_mixer", lambda _action: self._add_selected_paints_to_mixer())
        self.paint_colours_view.action_groups.connect_activate("add_paint_to_mixer", lambda _action: self._add_clicked_paint_to_mixer())
        # lay the components out
        self.pack_start(sname, expand=False, fill=True, padding=0)
        self.pack_start(maker, expand=False, fill=True, padding=0)
        hpaned = Gtk.HPaned()
        hpaned.pack1(self.wheels, resize=True, shrink=False)
        hpaned.pack2(gutils.wrap_in_scrolled_window(self.paint_colours_view), resize=True, shrink=False)
        self.pack_start(hpaned, expand=True, fill=True, padding=0)
        hpaned.set_position(recollect.get("paint_colour_selector", "hpaned_position"))
        hpaned.connect("notify", self._hpaned_notify_cb)
        self.show_all()
    def unselect_all(self):
        self.paint_colours_view.get_selection().unselect_all()
    def set_target_colour(self, target_colour):
        if target_colour is None:
            self.wheels.unset_crosshair()
        else:
            self.wheels.set_crosshair(target_colour)
    def unset_target_colour(self):
        self.wheels.unset_crosshair()
    def _hpaned_notify_cb(self, widget, parameter):
        if parameter.name == "position":
            recollect.set("paint_colour_selector", "hpaned_position", str(widget.get_position()))
    def _add_selected_paints_to_mixer(self):
        """
        Add the currently selected colours to the mixer.
        """
        self.emit("add-paint-colours", self.paint_colours_view.get_selected_paints())
    def _add_clicked_paint_to_mixer(self):
        """
        Add the currently selected colours to the mixer.
        """
        self.emit("add-paint-colours", [self.paint_colours_view.get_clicked_paint()])
    def _add_wheel_colour_to_mixer_cb(self, _action, wheel):
        """
        Add the currently selected colours to the mixer.
        """
        self.emit("add-paint-colours", [wheel.popup_colour])
GObject.signal_new("add-paint-colours", PaintSelector, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))

recollect.define("paint_series_selector", "last_file", recollect.Defn(str, os.path.join(SYS_DATA_DIR_PATH, 'ideal.psd')))

class PaintSeriesManager(GObject.GObject, dialogue.ReporterMixin, dialogue.AskerMixin):
    PAINT_SELECTOR = None
    PAINT_COLLECTION = None
    def __init__(self):
        GObject.GObject.__init__(self)
        self.__target_colour = None
        self.__series_dict = dict()
        self._load_series_data()
        open_menu, remove_menu = self._build_submenus()
        # Open
        self.__open_item = Gtk.MenuItem(_("Open"))
        self.__open_item.set_submenu(open_menu)
        self.__open_item.set_tooltip_text(_("Open a paint series paint selector."))
        self.__open_item.show()
        # Remove
        self.__remove_item = Gtk.MenuItem(_("Remove"))
        self.__remove_item.set_submenu(remove_menu)
        self.__remove_item.set_tooltip_text(_("Remove a paint series from the application."))
        self.__remove_item.show()
    @property
    def open_menu_item(self):
        return self.__open_item
    @property
    def remove_menu_item(self):
        return self.__remove_item
    def set_target_colour(self, colour):
        self.__target_colour = colour
        for sdata in self.__series_dict.values():
            sdata["selector"].set_target_colour(colour)
    def unset_target_colour(self):
        self.__target_colour = None
        for sdata in self.__series_dict.values():
            sdata["selector"].unset_target_colour()
    def _add_series_from_file(self, filepath):
        # Check and see if this file is already loaded
        for series, sdata in self.__series_dict.items():
            if filepath == sdata["filepath"]:
                if self.ask_ok_cancel(_("File \"{0}\" is already loaded. Reload?").format(filepath), _("Provides series \"{0.series_id.maker}: {0.series_id.name}\".").format(series)):
                    self._remove_paint_series(series)
                    break
                else:
                    return None
        # We let the clients handle any exceptions
        fobj = open(filepath, "r")
        text = fobj.read()
        fobj.close()
        series = self.PAINT_COLLECTION.fm_definition(text)
        # All OK so we can add this series to our dictionary
        selector = self.PAINT_SELECTOR(series)
        selector.set_target_colour(self.__target_colour)
        selector.connect("add-paint-colours", self._add_colours_to_mixer_cb)
        self.__series_dict[series] = { "selector" : selector, "filepath" : filepath }
        return series
    def _load_series_data(self):
        assert len(self.__series_dict) == 0
        io_errors = []
        format_errors = []
        for filepath in read_series_file_names():
            try:
                self._add_series_from_file(filepath)
            except IOError as edata:
                io_errors.append(edata)
                continue
            except self.PAINT_COLLECTION.ParseError as edata:
                format_errors.append((edata, filepath))
                continue
        if io_errors or format_errors:
            msg = _("The following errors occured loading paint series data:\n")
            for edata in io_errors:
                msg += "\t{0}: {1}\n".format(edata.filename, edata.strerror)
            for edata, filepath in format_errors:
                msg += "\t{0}: Format Error: {1}\n".format(filepath, str(edata))
            self.alert_user(msg)
            # Remove the offending files from the saved list
            write_series_file_names([value["filepath"] for value in self.__series_dict.values()])
    def _build_submenus(self):
        open_menu = Gtk.Menu()
        remove_menu = Gtk.Menu()
        for series in sorted(self.__series_dict.keys()):
            label = "{0.maker}: {0.name}".format(series.series_id)
            for menu, cb in [(open_menu, self._open_paint_series_cb), (remove_menu, self._remove_paint_series_cb)]:
                menu_item = Gtk.MenuItem(label)
                menu_item.connect("activate", cb, series)
                menu_item.show()
                menu.append(menu_item)
        return (open_menu, remove_menu)
    def _rebuild_submenus(self):
        open_menu, remove_menu = self._build_submenus()
        #self.__open_item.remove_submenu()
        self.__open_item.set_submenu(open_menu)
        #self.__remove_item.remove_submenu()
        self.__remove_item.set_submenu(remove_menu)
    def add_paint_series(self):
        dlg = Gtk.FileChooserDialog(
            title="Select Paint Series Description File",
            parent=None,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK)
        )
        last_paint_file = recollect.get("paint_series_selector", "last_file")
        last_paint_dir = None if last_paint_file is None else os.path.dirname(last_paint_file)
        if last_paint_dir:
            dlg.set_current_folder(last_paint_dir)
        response = dlg.run()
        filepath = dlg.get_filename()
        dlg.destroy()
        if response != Gtk.ResponseType.OK:
            return
        try:
            series = self._add_series_from_file(filepath)
        except IOError as edata:
            return self.report_io_error(edata)
        except self.PAINT_COLLECTION.ParseError as edata:
            return self.alert_user(_("Format Error:  {}: {}").format(edata, filepath))
        if series is None:
            return
        # All OK this series is in our dictionary
        last_paint_file = recollect.set("paint_series_selector", "last_file", filepath)
        write_series_file_names([value["filepath"] for value in self.__series_dict.values()])
        self._rebuild_submenus()
        self._open_paint_series(series)
    def _open_paint_series_cb(self, widget, series):
        return self._open_paint_series(series)
    def _open_paint_series(self, series):
        sdata = self.__series_dict[series]
        presenter = sdata.get("presenter", None)
        if presenter is not None:
            presenter.present()
            return
        # put it in a window and show it
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        last_size = recollect.get("paint_colour_selector", "last_size")
        if last_size:
            window.set_default_size(*eval(last_size))
        window.set_icon_from_file(icons.APP_ICON_FILE)
        window.set_title(_("Paint Series: {0.maker}: {0.name}").format(series.series_id))
        window.add(sdata["selector"])
        window.connect("destroy", self._destroy_selector_cb, series)
        window.connect("size-allocate", self._selector_size_allocation_cb)
        sdata["presenter"] = window
        window.show()
        sdata["selector"].unselect_all()
        return True
    def _selector_size_allocation_cb(self, widget, allocation):
        recollect.set("paint_colour_selector", "last_size", "({0.width}, {0.height})".format(allocation))
    def _destroy_selector_cb(self, widget, series):
        del self.__series_dict[series]["presenter"]
        widget.remove(self.__series_dict[series]["selector"])
        widget.destroy()
    def _remove_paint_series_cb(self, _widget, series):
        self._remove_paint_series(series)
    def _remove_paint_series(self, series):
        sde = self.__series_dict[series]
        del self.__series_dict[series]
        write_series_file_names([value["filepath"] for value in self.__series_dict.values()])
        self._rebuild_submenus()
        if "presenter" in sde:
            sde["presenter"].destroy()
        sde["selector"].destroy()
    def _add_colours_to_mixer_cb(self, widget, paint_colours):
        # pass the parcel :-)
        self.emit("add-paint-colours", paint_colours)
GObject.signal_new("add-paint-colours", PaintSeriesManager, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
