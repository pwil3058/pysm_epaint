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

"""Manage various paint colour standards
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
from ..gtx import gutils
from ..gtx import icons
from ..gtx import recollect
from ..gtx import tlview

from . import gpaint
from . import pedit
from . import vpaint

from .. import CONFIG_DIR_PATH, SYS_BASE_DIR_PATH

__all__ = []
__author__ = "Peter Williams <pwil3058@gmail.com>"

STANDARDS_FILES_FILE_PATH = os.path.join(CONFIG_DIR_PATH, "paint_standards_files")
SYS_STANDARDS_DIR_PATH = os.path.join(SYS_BASE_DIR_PATH, "standards")

if not os.path.exists(STANDARDS_FILES_FILE_PATH):
    with open(STANDARDS_FILES_FILE_PATH, "w") as f_obj:
        for item in os.listdir(SYS_STANDARDS_DIR_PATH):
            path = os.path.join(SYS_STANDARDS_DIR_PATH, item)
            if os.path.isfile(path):
                f_obj.write(path + "\n")

def read_standards_file_names():
    standards_file_names = []
    if os.path.isfile(STANDARDS_FILES_FILE_PATH):
        for line in open(STANDARDS_FILES_FILE_PATH, 'r').readlines():
            sf_name = line.strip()
            if len(line) == 0:
                continue
            standards_file_names.append(sf_name)
    return standards_file_names

def write_standards_file_names(sf_names):
    fobj = open(STANDARDS_FILES_FILE_PATH, 'w')
    for sf_name in sf_names:
        fobj.write(sf_name)
        fobj.write(os.linesep)
    fobj.close()

recollect.define("paint_standards_manager", "last_file", recollect.Defn(str, ""))

STANDARD_ID = collections.namedtuple("STANDARD_ID", ["sponsor", "name"])

class PaintStandard:
    # No i18n for these strings
    OWNER_LABEL = "Sponsor"
    NAME_LABEL = "Standard"
    PAINT = None
    class ParseError(Exception):
        pass
    def __init__(self, sponsor, name, paints=None):
        self.standard_id = STANDARD_ID(sponsor=sponsor, name=name)
        self.__paints = {}
        if paints:
            for paint in paints:
                self.add_paint(paint)
    def __lt__(self, other):
        if self.standard_id.sponsor < other.standard_id.sponsor:
            return True
        elif self.standard_id.sponsor > other.standard_id.sponsor:
            return False
        return self.standard_id.name < other.standard_id.name
    def add_paint(self, paint):
        self.__paints[paint.name] = paint
    def definition_text(self):
        string = "{0}: {1}\n".format(self.OWNER_LABEL, self.standard_id.sponsor)
        string += "{0}: {1}\n".format(self.NAME_LABEL, self.standard_id.name)
        for paint in sorted(self.__paints.values(), key=lambda x: x.name):
            string += "{0}\n".format(repr(paint))
        return string
    def iter_names(self, ordered=True):
        if ordered:
            return (name for name in sorted(self.__paints.keys()))
        else:
            return self.__paints.keys()
    def iter_paints(self, ordered=True):
        if ordered:
            return (self.__paints[name] for name in sorted(self.__paints.keys()))
        else:
            return self.__paints.values()
    def iter_standard_paints(self, ordered=True):
        return (StandardPaint(self, paint) for paint in self.iter_paints(ordered))
    def get_paint(self, name):
        return self.__paints.get(name, None)
    def get_standard_paint(self, name):
        paint = self.__paints.get(name, None)
        return None if paint is None else StandardPaint(self, paint)
    @classmethod
    def fm_definition(cls, definition_text):
        lines = definition_text.splitlines()
        if len(lines) < 2:
            raise cls.ParseError(_("Too few lines: {0}.".format(len(lines))))
        sponsor_name = None
        standard_name = None
        for line in lines[:2]:
            match = re.match("^Sponsor:\s+(\S.*)\s*$", line)
            if match:
                sponsor_name = match.group(1)
            else:
                match = re.match("^Standard:\s+(\S.*)\s*$", line)
                if match:
                    standard_name = match.group(1)
        if not sponsor_name:
            if not standard_name:
                raise cls.ParseError(_("Neither sponsor nor standard name found."))
            else:
                raise cls.ParseError(_("Sponsor not found."))
        elif not standard_name:
            raise cls.ParseError(_("Standard name not found."))
        return cls(sponsor=sponsor_name, name=standard_name, paints=cls.paints_fm_definition(lines[2:]))

def generate_paint_list_spec(view, model):
    """Generate the specification for a paint colour list
    """
    return tlview.ViewSpec(
        properties={},
        selection_mode=Gtk.SelectionMode.SINGLE,
        columns=gpaint.paint_list_column_specs(model)
    )

class StandardPaintColourInformationDialogue(gpaint.PaintColourInformationDialogue):
    """A dialog to display the detailed information for a paint colour
    """
    TITLE_FMT_STR = _("Standard Paint Colour: {}")
    RECOLLECT_SECTION = "standard_paint_colour_information"

class SelectStandardPaintListView(gpaint.PaintListView):
    MODEL = None
    PAINT_INFO_DIALOGUE = StandardPaintColourInformationDialogue
    SPECIFICATION = generate_paint_list_spec
    UI_DESCR = """
    <ui>
        <popup name="paint_list_popup">
            <menuitem action="set_target_in_mixer"/>
            <menuitem action="show_paint_details"/>
        </popup>
    </ui>
    """
    AC_TARGET_SETTABLE = actions.ActionCondns.new_flag()
    def populate_action_groups(self):
        """Populate action groups ready for UI initialization.
        """
        self.get_selection().set_mode(Gtk.SelectionMode.NONE)
        gpaint.PaintListView.populate_action_groups(self)
        self.action_groups[self.AC_CLICKED_ON_ROW|self.AC_TARGET_SETTABLE].add_actions(
            [
                ("set_target_in_mixer", Gtk.STOCK_APPLY, _("Set As Target"), None,
                 _("Set the target colour in the mixer to clicked standard paint's colour."),
                ),
            ],
        )
    def set_target_setable(self, setable):
        if setable:
            self.action_groups.update_condns(actions.MaskedCondns(self.AC_TARGET_SETTABLE, self.AC_TARGET_SETTABLE))
        else:
            self.action_groups.update_condns(actions.MaskedCondns(0, self.AC_TARGET_SETTABLE))

class StandardsHueWheelNotebook(gpaint.HueWheelNotebook):
    PAINT_INFO_DIALOGUE = StandardPaintColourInformationDialogue

class StandardPaintSelector(Gtk.VBox):
    """
    A widget for adding paint colours to the mixer
    """
    SELECT_STANDARD_PAINT_LIST_VIEW = SelectStandardPaintListView
    RECOLLECT_SECTION = "paint_standard_selector"
    def __init__(self, paint_standard):
        try:
            recollect.define(self.RECOLLECT_SECTION, "hpaned_position", recollect.Defn(int, 400))
            recollect.define(self.RECOLLECT_SECTION, "last_size", recollect.Defn(str, "(780, 480)"))
        except recollect.DuplicateDefn:
            pass
        Gtk.VBox.__init__(self)
        # components
        self.wheels = StandardsHueWheelNotebook(popup="/colour_wheel_I_popup")
        #self.wheels.set_wheels_add_paint_acb(self._add_wheel_colour_to_mixer_cb)
        self.standard_paints_view = self.SELECT_STANDARD_PAINT_LIST_VIEW()
        self.standard_paints_view.set_size_request(240, 360)
        model = self.standard_paints_view.get_model()
        for paint in paint_standard.iter_paints():
            model.append_paint(paint)
            self.wheels.add_paint(paint)
        maker = Gtk.Label(label=_("Sponsor: {0}".format(paint_standard.standard_id.sponsor)))
        sname = Gtk.Label(label=_("Standard: {0}".format(paint_standard.standard_id.name)))
        # make connections
        self.standard_paints_view.action_groups.connect_activate("set_target_in_mixer", self._set_target_in_mixer_cb)
        # lay the components out
        self.pack_start(sname, expand=False, fill=True, padding=0)
        self.pack_start(maker, expand=False, fill=True, padding=0)
        hpaned = Gtk.HPaned()
        hpaned.pack1(self.wheels, resize=True, shrink=False)
        hpaned.pack2(gutils.wrap_in_scrolled_window(self.standard_paints_view), resize=True, shrink=False)
        self.pack_start(hpaned, expand=True, fill=True, padding=0)
        hpaned.set_position(recollect.get(self.RECOLLECT_SECTION, "hpaned_position"))
        hpaned.connect("notify", self._hpaned_notify_cb)
        self.show_all()
    def unselect_all(self):
        self.standard_paints_view.get_selection().unselect_all()
    def set_target_setable(self, setable):
        self.standard_paints_view.set_target_setable(setable)
    def _hpaned_notify_cb(self, widget, parameter):
        if parameter.name == "position":
            recollect.set(self.RECOLLECT_SECTION, "hpaned_position", str(widget.get_position()))
    def _set_target_in_mixer_cb(self, _action):
        self.emit("set_target_colour", self.standard_paints_view.get_clicked_paint())
GObject.signal_new("set_target_colour", StandardPaintSelector, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))

class PaintStandardsManager(GObject.GObject, dialogue.ReporterMixin, dialogue.AskerMixin):
    STANDARD_PAINT_SELECTOR = StandardPaintSelector
    PAINT_STANDARD_COLLECTION = None
    def __init__(self):
        GObject.GObject.__init__(self)
        self.__standards_dict = dict()
        self._load_standards_data()
        open_menu, remove_menu = self._build_submenus()
        # Open
        self.__open_item = Gtk.MenuItem(_("Open"))
        self.__open_item.set_submenu(open_menu)
        self.__open_item.set_tooltip_text(_("Open a paint series paint selector."))
        self.__open_item.show()
        # Remove
        self.__remove_item = Gtk.MenuItem(_("Remove"))
        self.__remove_item.set_submenu(remove_menu)
        self.__remove_item.set_tooltip_text(_("Remove a paint standards from the application."))
        self.__remove_item.show()
    @property
    def open_menu_item(self):
        return self.__open_item
    @property
    def remove_menu_item(self):
        return self.__remove_item
    def set_target_setable(self, setable):
        for item in self.__standards_dict.values():
            item["selector"].set_target_setable(setable)
    def _add_standard_from_file(self, filepath):
        # Check and see if this file is already loaded
        for standard, sdata in self.__standards_dict.items():
            if filepath == sdata["filepath"]:
                if self.ask_ok_cancel(_("File \"{0}\" is already loaded. Reload?").format(filepath), _("Provides standard \"{0.standard_id.sponsor}: {0.standard_id.name}\".").format(standard)):
                    self._remove_paint_standard(standard)
                    break
                else:
                    return None
        # We let the clients handle any exceptions
        fobj = open(filepath, "r")
        text = fobj.read()
        fobj.close()
        standard = self.PAINT_STANDARD_COLLECTION.fm_definition(text)
        # All OK so we can add this standard to our dictionary
        selector = self.STANDARD_PAINT_SELECTOR(standard)
        selector.connect("set_target_colour", self._set_target_in_mixer_cb)
        self.__standards_dict[standard] = { "filepath" : filepath, "selector" : selector }
        return standard
    def _generate_lexicon(self):
        self.__lexicon = Gtk.ListStore(str)
        for standard in self.__standards_dict.keys():
            for standard_paint_name in standard.iter_names():
                self.__lexicon.append([standard_paint_name])
    def ask_standard_paint_name(self, prompt=_("Standard Paint Id:")):
        return self.ask_text_auto_complete(prompt=prompt, lexicon=self.__lexicon, learn=False)
    def get_standard_paint(self, standard_paint_id):
        for standard in self.__standards_dict.keys():
            standard_paint = standard.get_paint(standard_paint_id)
            if standard_paint is not None:
                return standard_paint
        # Nothing found so try case insensitive search of names
        uspid = standard_paint_id.upper()
        for standard in self.__standards_dict.keys():
            for standard_paint in standard.iter_paints():
                if uspid == standard_paint.name.upper():
                    return standard_paint
        return None
    def _load_standards_data(self):
        assert len(self.__standards_dict) == 0
        io_errors = []
        format_errors = []
        for filepath in read_standards_file_names():
            try:
                self._add_standard_from_file(filepath)
            except IOError as edata:
                io_errors.append(edata)
                continue
            except PaintStandard.ParseError as edata:
                format_errors.append((edata, filepath))
                continue
        if io_errors or format_errors:
            msg = _("The following errors occured loading paint standards data:\n")
            for edata in io_errors:
                msg += "\t{0}: {1}\n".format(edata.filename, edata.strerror)
            for edata, filepath in format_errors:
                msg += "\t{0}: Format Error: {1}\n".format(filepath, str(edata))
            self.alert_user(msg)
            # Remove the offending files from the saved list
            write_standards_file_names([value["filepath"] for value in self.__standards_dict.values()])
        self._generate_lexicon()
    def _build_submenus(self):
        open_menu = Gtk.Menu()
        remove_menu = Gtk.Menu()
        for standard in sorted(self.__standards_dict.keys()):
            label = "{0.sponsor}: {0.name}".format(standard.standard_id)
            for menu, cb in [(open_menu, self._open_paint_standard_cb), (remove_menu, self._remove_paint_standard_cb)]:
                menu_item = Gtk.MenuItem(label)
                menu_item.connect("activate", cb, standard)
                menu_item.show()
                menu.append(menu_item)
        return (open_menu, remove_menu)
    def _rebuild_submenus(self):
        open_menu, remove_menu = self._build_submenus()
        self.__open_item.set_submenu(open_menu)
        self.__remove_item.set_submenu(remove_menu)
    def add_paint_standard(self):
        dlg = Gtk.FileChooserDialog(
            title="Select Paint Standards Description File",
            parent=None,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK)
        )
        last_paint_file = recollect.get("paint_standards_manager", "last_file")
        last_paint_dir = None if last_paint_file is None else os.path.dirname(last_paint_file)
        if last_paint_dir:
            dlg.set_current_folder(last_paint_dir)
        response = dlg.run()
        filepath = dlg.get_filename()
        dlg.destroy()
        if response != Gtk.ResponseType.OK:
            return
        try:
            standard = self._add_standard_from_file(filepath)
        except IOError as edata:
            return self.report_io_error(edata)
        except PaintStandard.ParseError as edata:
            return self.alert_user(_("Format Error:  {}: {}").format(edata, filepath))
        if standard is None:
            return
        # All OK this standard is in our dictionary
        last_paint_file = recollect.set("paint_standards_manager", "last_file", filepath)
        write_standards_file_names([value["filepath"] for value in self.__standards_dict.values()])
        self._rebuild_submenus()
        self._generate_lexicon()
        self._open_paint_standard(standard)
    def _open_paint_standard_cb(self, _widget, standard):
        return self._open_paint_standard(standard)
    def _open_paint_standard(self, standard):
        sdata = self.__standards_dict[standard]
        presenter = sdata.get("presenter", None)
        if presenter is not None:
            presenter.present()
            return
        # put it in a window and show it
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        last_size = recollect.get(self.STANDARD_PAINT_SELECTOR.RECOLLECT_SECTION, "last_size")
        if last_size:
            window.set_default_size(*eval(last_size))
        window.set_icon_from_file(icons.APP_ICON_FILE)
        window.set_title(_("Paint Standard: {0.sponsor}: {0.name}").format(standard.standard_id))
        window.add(sdata["selector"])
        window.connect("destroy", self._destroy_selector_cb, standard)
        window.connect("size-allocate", self._selector_size_allocation_cb)
        sdata["presenter"] = window
        window.show()
        sdata["selector"].unselect_all()
        return True
    def _selector_size_allocation_cb(self, widget, allocation):
        recollect.set(self.STANDARD_PAINT_SELECTOR.RECOLLECT_SECTION, "last_size", "({0.width}, {0.height})".format(allocation))
    def _destroy_selector_cb(self, widget, standard):
        del self.__standards_dict[standard]["presenter"]
        widget.remove(self.__standards_dict[standard]["selector"])
        widget.destroy()
    def _remove_paint_standard_cb(self, widget, standard):
        self._remove_paint_standard(standard)
    def _remove_paint_standard(self, standard):
        sde = self.__standards_dict[standard]
        del self.__standards_dict[standard]
        write_standards_file_names([value["filepath"] for value in self.__standards_dict.values()])
        self._rebuild_submenus()
        self._generate_lexicon()
        if "presenter" in sde:
            sde["presenter"].destroy()
        if "selector" in sde:
            sde["selector"].destroy()
    def _set_target_in_mixer_cb(self, widget, standard_paint):
        # pass the parcel :-)
        self.emit("set_target_colour", standard_paint)
GObject.signal_new("set_target_colour", PaintStandardsManager, GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))


class PaintStandardEditor(pedit.PaintCollectionEditor):
    PAINT_EDITOR = None
    PAINT_LIST_NOTEBOOK = None
    PAINT_COLLECTION = None
    RECOLLECT_SECTION = "stds_editor"
    FILE_NAME_PROMPT = _("Paint Standard Description File:")
    LABEL = _("Paint Standards Editor")

    def load_fm_file(self, filepath):
        try:
            with open(filepath, "r") as fobj:
                text = fobj.read()
        except IOError as edata:
            return self.report_io_error(edata)
        try:
            standard = self.PAINT_COLLECTION.fm_definition(text)
        except self.PAINT_COLLECTION.ParseError as edata:
            return self.alert_user(_("Format Error:  {}: {}").format(edata, filepath))
        # All OK so clear the paint editor and ditch the current colours
        self.paint_editor.reset()
        self._set_current_extant_paint(None)
        self.paint_colours.clear()
        # and load the new ones
        for paint in standard.iter_paints():
            self.paint_colours.add_paint(paint)
        self.proprietor_name.set_text(standard.standard_id.sponsor)
        self.collection_name.set_text(standard.standard_id.name)
        self.set_file_path(filepath)
        self.saved_hash = hashlib.sha1(text.encode()).digest()
        self.set_status_indicator(clean=True)

    def get_definition_text(self):
        """
        Get the text sefinition of the current standard
        """
        sponsor = self.proprietor_name.get_text()
        name = self.collection_name.get_text()
        standard = self.PAINT_COLLECTION(sponsor=sponsor, name=name, paints=self.paint_colours.iter_paints())
        return standard.definition_text()
