# Copyright: Peter Williams (2012) - All rights reserved
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License only.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Paint characteristics not related to colour
"""

import collections

from gi.repository import Gtk

__all__ = []
__author__ = "Peter Williams <pwil3058@gmail.com>"


class BadMappedFloatValue(Exception):
    pass


CHARACTERISTIC = collections.namedtuple("CHARACTERISTIC", ["abbrev", "descr", "rval"])


class MappedFloat:
    MAP = None
    def __init__(self, ival=0.0):
        if isinstance(ival, str):
            self.val = None
            for mapi in self.MAP:
                if ival == mapi.abbrev or ival == mapi.descr:
                    self.val = mapi.rval
                    break
            if self.val is None:
                try:
                    self.val = float(ival)
                except ValueError:
                    raise BadMappedFloatValue(_("Unrecognized characteristic value: {0}").format(ival))
        else: # assume it's a real value in the mapped range
            self.val = ival
    def __str__(self):
        rval = round(self.val, 0)
        for mapi in self.MAP:
            if rval == mapi.rval:
                return mapi.abbrev
        raise  BadMappedFloatValue(_("Invalid characteristic: {0}").format(self.val))
    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__, self.val)
    def description(self):
        rval = round(self.val, 0)
        for mapi in self.MAP:
            if rval == mapi.rval:
                return mapi.descr
        raise  BadMappedFloatValue(_("Invalid characteristic: {0}").format(self.val))
    # Enough operators to facilitate weighted averaging
    def __mul__(self, multiplier):
        return self.__class__(self.val * multiplier)
    def __iadd__(self, other):
        self.val += other.val
        return self
    def __itruediv__(self, divisor):
        self.val /= divisor
        return self
    # And sorting (Python 3.0 compatible)
    def __lt__(self, other):
        return self.val < other.val
    def __le__(self, other):
        return self.val <= other.val
    def __gt__(self, other):
        return self.val > other.val
    def __ge__(self, other):
        return self.val >= other.val
    def __eq__(self, other):
        return self.val == other.val
    def __ne__(self, other):
        return self.val != other.val


class MappedFloatChoice(Gtk.ComboBoxText):
    MFDC = None
    def __init__(self):
        Gtk.ComboBoxText.__init__(self)
        for choice in ("{0}\t- {1}".format(item[0], item[1]) for item in self.MFDC.MAP):
            self.append_text(choice)
    def get_selection(self):
        index = self.get_active()
        characteristic = self.MFDC.MAP[index if index >= 0 else None]
        return self.MFDC(characteristic.abbrev)
    def set_selection(self, mapped_float):
        abbrev = str(mapped_float)
        for index, characteristic in enumerate(self.MFDC.MAP):
            if abbrev == characteristic.abbrev:
                self.set_active(index if index is not None else -1)
                return
        raise BadMappedFloatValue(_("Invalid characteristic: {0}").format(mapped_float))


class Permanence(MappedFloat):
    MAP = (
            CHARACTERISTIC("AA", _("Extremely Permanent"), 4.0),
            CHARACTERISTIC("A", _("Permanent"), 3.0),
            CHARACTERISTIC("B", _("Moderately Durable"), 2.0),
            CHARACTERISTIC("C", _("Fugitive"), 1.0),
        )


class PermanenceChoice(MappedFloatChoice):
    PROMPT_TEXT = _("Permanence:")
    MFDC = Permanence


class Finish(MappedFloat):
    MAP = (
            CHARACTERISTIC("G", _("Gloss"), 4.0),
            CHARACTERISTIC("SG", _("Semi-gloss"), 3.0),
            CHARACTERISTIC("SF", _("Semi-flat"), 2.0),
            CHARACTERISTIC("F", _("Flat"), 1.0),
        )


class FinishChoice(MappedFloatChoice):
    PROMPT_TEXT = _("Finish:")
    MFDC = Finish


class Transparency(MappedFloat):
    MAP = (
            CHARACTERISTIC("O", _("Opaque"), 1.0),
            CHARACTERISTIC("SO", _("Semi-opaque"), 2.0),
            CHARACTERISTIC("ST", _("Semi-transparent"), 3.0),
            CHARACTERISTIC("T", _("Transparent"), 4.0),
            CHARACTERISTIC("C", _("Clear"), 5.0),
        )

    def to_alpha(self):
        return (5.0 - self.val) / 4.0


class TransparencyChoice(MappedFloatChoice):
    PROMPT_TEXT = _("Transparency:")
    MFDC = Transparency


class Fluorescence(MappedFloat):
    MAP = (
        CHARACTERISTIC("NF", _("Nonfluorescent"), 1.0),
        CHARACTERISTIC("SN", _("Semi-nonfluorescent"), 1.0),
        CHARACTERISTIC("SF", _("Semi-fluorescent"), 3.0),
        CHARACTERISTIC("Fl", _("Fluorescent"), 4.0),
    )

class FluorescenceChoice(MappedFloatChoice):
    PROMPT_TEXT = _("Fluorescence:")
    MFDC = Fluorescence

class Metallic(MappedFloat):
    MAP = (
        CHARACTERISTIC("NM", _("Non-mellatic"), 1.0),
        CHARACTERISTIC("SN", _("Semi-nonf-mellatic"), 1.0),
        CHARACTERISTIC("SM", _("Semi-mellatic"), 3.0),
        CHARACTERISTIC("M", _("Mellatic"), 4.0),
    )

class MetallicChoice(MappedFloatChoice):
    PROMPT_TEXT = _("Metallic:")
    MFDC = Metallic

CHARACTERISTIC_CHOOSERS = {
    "permanence" : PermanenceChoice,
    "finish" : FinishChoice,
    "transparency" : TransparencyChoice,
    "fluorescence" : FluorescenceChoice,
    "metallic" : MetallicChoice
}

def cell_column_header(characteristic, length=1):
    return "{}.".format(CHARACTERISTIC_CHOOSERS[characteristic].PROMPT_TEXT[0:length])

class Characteristics:
    NAMES = list()
    def __init__(self, **kwargs):
        if len(kwargs):
            assert len(self.NAMES) == len(kwargs) # all or nothing
            for name in self.NAMES:
                setattr(self, name, kwargs[name])
        else:
            for name in self.NAMES:
                self.__dict__[name] = CHARACTERISTIC_CHOOSERS[name].MFDC()
    def __setattr__(self, attr_name, value):
        assert attr_name in self.NAMES, "{}: Unknown characteristic".format(attr_name)
        mfdc = CHARACTERISTIC_CHOOSERS[attr_name].MFDC
        self.__dict__[attr_name] = value if isinstance(value, mfdc) else mfdc(value)
    def __iter__(self):
        return (getattr(self, name) for name in self.NAMES)
    # Enough operators to facilitate weighted averaging
    def __mul__(self, multiplier):
        result = self.__class__()
        for name in self.NAMES:
            result.__dict__[name] = getattr(self, name) * multiplier
        return result
    def __iadd__(self, other):
        for name in self.NAMES:
            self.__dict__[name] += getattr(other, name)
        return self
    def __itruediv__(self, divisor):
        for name in self.NAMES:
            self.__dict__[name] /= divisor
        return self
    def __neq__(self, other):
        for name in self.NAMES:
            if getattr(self, name) != getattr(other, name):
                return True
        return False
    def __eq__(self, other):
        for name in self.NAMES:
            if getattr(self, name) != getattr(other, name):
                return False
        return True
    def get_kwargs(self):
        return { name : str(getattr(self, name)) for name in self.NAMES}

class Choosers(collections.OrderedDict):
    def __init__(self, names):
        items = ((name, CHARACTERISTIC_CHOOSERS[name]()) for name in names)
        collections.OrderedDict.__init__(self, items)
    def set_selections(self, **kwargs):
        for key, value in kwargs.items():
            self[key].set_selection(value)
    def get_kwargs(self):
        return { key : str(value.get_selection()) for key, value in self.items()}
    @property
    def all_active(self):
        for chooser in self.values():
            if chooser.get_active() == -1:
                return False
        return True
