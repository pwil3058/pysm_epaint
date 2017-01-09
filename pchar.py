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
    DEFAULT = 0.0
    MAP = None
    def __init__(self, ival=None):
        if ival is None:
            self.val = self.DEFAULT
        elif isinstance(ival, str):
            self.val = None
            for mapi in self.MAP:
                if ival == mapi.abbrev or ival == mapi.descr:
                    self.val = mapi.rval
                    break
            if self.val is None:
                try:
                    self.val = float(ival)
                except ValueError:
                    raise self.BadValue(_("Unrecognized characteristic value: {0}").format(ival))
        else: # assume it's a real value in the mapped range
            self.val = ival
    def __str__(self):
        rval = round(self.val, 0)
        for mapi in self.MAP:
            if rval == mapi.rval:
                return mapi.abbrev
        raise  self.BadValue(_("Invalid characteristic: {0}").format(self.val))
    def description(self):
        rval = round(self.val, 0)
        for mapi in self.MAP:
            if rval == mapi.rval:
                return mapi.descr
        raise  self.BadValue(_("Invalid characteristic: {0}").format(self.val))
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
        raise paint.MappedFloat.BadValue()


class Permanence(MappedFloat):
    MAP = (
            CHARACTERISTIC("AA", _("Extremely Permanent"), 4.0),
            CHARACTERISTIC("A", _("Permanent"), 3.0),
            CHARACTERISTIC("B", _("Moderately Durable"), 2.0),
            CHARACTERISTIC("C", _("Fugitive"), 1.0),
        )

    def __repr__(self):
        return "Permanence({0})".format(self.val)


class PermanenceChoice(MappedFloatChoice):
    MFDC = Permanence


class Finish(MappedFloat):
    MAP = (
            CHARACTERISTIC("G", _("Gloss"), 4.0),
            CHARACTERISTIC("SG", _("Semi-gloss"), 3.0),
            CHARACTERISTIC("SF", _("Semi-flat"), 2.0),
            CHARACTERISTIC("F", _("Flat"), 1.0),
        )

    def __repr__(self):
        return "Finish({0})".format(self.val)


class FinishChoice(MappedFloatChoice):
    MFDC = Finish


class Transparency(MappedFloat):
    MAP = (
            CHARACTERISTIC("O", _("Opaque"), 1.0),
            CHARACTERISTIC("SO", _("Semi-opaque"), 2.0),
            CHARACTERISTIC("ST", _("Semi-transparent"), 3.0),
            CHARACTERISTIC("T", _("Transparent"), 4.0),
            CHARACTERISTIC("C", _("Clear"), 5.0),
        )

    def __repr__(self):
        return "Transparency({0})".format(self.val)

    def to_alpha(self):
        return (5.0 - self.val) / 4.0


class TransparencyChoice(MappedFloatChoice):
    MFDC = Transparency
