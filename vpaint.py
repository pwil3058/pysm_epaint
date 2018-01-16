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

"""
Virtual paint library
"""

import collections
import math
import re
import fractions

from ..bab import mathx

from ..gtx import rgb_math

from . import pchar
from . import rgbh

class HCV:
    RGB = rgbh.RGB16
    # The "ideal" palette is one that contains the full range at full strength
    IDEAL_RGB_COLOURS = [RGB.WHITE, RGB.MAGENTA, RGB.RED, RGB.YELLOW, RGB.GREEN, RGB.CYAN, RGB.BLUE, RGB.BLACK]
    def __init__(self, rgb):
        self.__rgb = rgb.converted_to(self.RGB)
        self.__value = self.__rgb.get_value()
        xy = rgb_math.rgb_to_xy(self.__rgb)
        class Hue(rgbh.HueNG):
            RGB = self.RGB
        self.__hue = Hue.from_xy(*xy)
        self.__chroma = math.hypot(*xy) * self.__hue.chroma_correction / self.RGB.ONE
        if self.RGB.BITS_PER_CHANNEL is None:
            self.__warmth = xy.x / self.RGB.ONE
        else:
            self.__warmth = fractions.Fraction(self.RGB.ROUND(xy.x), self.RGB.ONE)
    def __getattr__(self, attr_name):
        try:
            return getattr(self.__rgb, attr_name)
        except AttributeError:
            return getattr(self.__hue, attr_name)
    def __getitem__(self, index):
        return self.rgb[index]
    @property
    def chroma(self):
        return self.__chroma
    @property
    def greyness(self):
        return 1.0 - self.__chroma
    @property
    def hue(self):
        return self.__hue
    @property
    def hue_rgb(self):
        return self.__hue.rgb
    @property
    def rgb(self):
        return self.__rgb
    @property
    def value(self):
        return self.__value
    @property
    def value_rgb(self):
        return self.RGB.WHITE * self.__value
    def hue_rgb_for_value(self, value=None):
        # value == None means same hue and value but without any unnecessary grey
        return self.__hue.max_chroma_rgb_with_value(self.__value if value is None else value)
    def zero_chroma_rgb(self):
        # get the rgb for the grey which would result from this colour
        # having white or black (whichever is quicker) added until the
        # chroma value is zero (useful for displaying chroma values)
        if self.__hue.is_grey:
            return self.value_rgb
        mcv = self.__hue.max_chroma_value
        dc = 1.0 - self.__chroma
        if dc != 0.0:
            return self.RGB.WHITE * ((self.__value - mcv * self.__chroma) / dc)
        elif mcv < 0.5:
            return self.RGB.BLACK
        else:
            return self.RGB.WHITE
    def chroma_side(self):
        # Is it darker or lighter than max chroma for the hue?
        if sum(self.__rgb) > sum(self.__hue.rgb):
            return self.RGB.WHITE
        else:
            return self.RGB.BLACK
    def get_rotated_rgb(self, delta_hue_angle):
        """
        Return a copy of our rgb rotated by the given amount but with
        the same value and without unavoidable chroma change.
        from .bab import mathx
        """
        if self.__rgb.non_zero_components == 2:
            # we have no grey so only add grey if necessary to maintain value
            hue = self.__hue.rotated_by(delta_hue_angle)
            return hue.max_chroma_rgb_with_value(self.__value)
        else:
            # Simple rotation is the correct solution for 1 or 3 components
            return self.__rgb.rotated(delta_hue_angle)
    def __str__(self):
        string = "(HUE = {0}, ".format(str(self.__hue.rgb))
        string += "VALUE = {0}, ".format(round(self.__value, 2))
        string += "CHROMA = {0})".format(round(self.__chroma, 2))
        return string
    def __repr__(self):
        return self.__class__.__name__ + "(rgb={})".format(repr(self.__rgb))

class HCVW(HCV):
    @property
    def warmth(self):
        return self._HCV__warmth
    @property
    def warmth_rgb(self):
        return (self.RGB.CYAN * (1 - self._HCV__warmth) + self.RGB.RED * (1 + self._HCV__warmth)) / 2
    def __str__(self):
        string = "(HUE = {0}, ".format(str(self._HCV__hue.rgb))
        string += "VALUE = {0}, ".format(round(self._HCV__value, 2))
        string += "CHROMA = {0}, ".format(round(self._HCV__chroma, 2))
        string += "WARMTH = {0})".format(round(self._HCV__warmth, 2))
        return string


WHITE, MAGENTA, RED, YELLOW, GREEN, CYAN, BLUE, BLACK = [HCVW(rgb) for rgb in HCVW.IDEAL_RGB_COLOURS]
IDEAL_COLOURS = [WHITE, MAGENTA, RED, YELLOW, GREEN, CYAN, BLUE, BLACK]

EXTRA = collections.namedtuple("EXTRAS", ["name", "prompt_text", "default_value"])

class Paint:
    COLOUR = None
    CHARACTERISTICS = None
    EXTRAS = []
    def __init__(self, name, rgb, **kwargs):
        self.__name = name.strip() # NB: this is readonly so it can be used as dict() key
        self.colour = self.COLOUR(rgb)
        self.__extras = {extra.name: kwargs.pop(extra.name, extra.default_value).strip() for extra in self.EXTRAS}
        self.characteristics = self.CHARACTERISTICS(**kwargs)
    @property
    def name(self):
        return self.__name
    def __getattr__(self, attr_name):
        try:
            return getattr(self.colour, attr_name)
        except AttributeError:
            try:
                return getattr(self.characteristics, attr_name)
            except AttributeError:
                try:
                    return self.__extras[attr_name]
                except KeyError:
                    raise AttributeError(_("{}: unknown attribute for {}").format(attr_name, self.__class__.__name__))
    def set_rgb(self, rgb):
        self.colour = self.COLOUR(rgb)
    def set_characteristics(self, **kwargs):
        for c_name, c_value in kwargs.items():
            setattr(self.characteristics, c_name, c_value)
    def set_extras(self, **kwargs):
        for e_name, e_value in kwargs.items():
            if e_name in self.__extras:
                self.__extras[e_name] = e_value.strip()
            else:
                raise AttributeError(_("{}: unknown attribute for {}").format(e_name, self.__class__.__name__))
    def get_extras(self):
        return self.__extras.copy()
    def get_named_extra(self, e_name):
        return self.__extras.get(e_name, None)
    def __ne__(self, other):
        if self.__name != other.__name:
            return True
        elif self.colour.rgb != other.colour.rgb:
            return True
        elif self.__extras != other.__extras:
            return True
        else:
            return self.characteristics != other.characteristics
    def _format_data(self):
        fmt_str = "(name=\"{0}\", rgb={1}{2})"
        ename = re.sub('"', r'\"', self.__name)
        ergb = repr(self.colour.rgb)
        kwargs_str = ""
        for name in self.CHARACTERISTICS.NAMES:
            value = getattr(self.characteristics, name)
            kwargs_str += ", {0}=\"{1}\"".format(name, str(value))
        for e_name, e_value in self.__extras.items():
            kwargs_str += ", {0}=\"{1}\"".format(e_name, re.sub('"', r'\"', e_value))
        return fmt_str.format(ename, ergb, kwargs_str)
    def paint_spec(self):
        return "PaintSpec" + self._format_data()
    def __repr__(self):
        return self.__class__.__name__ + self._format_data()


class TargetColour:
    COLOUR = None
    def __init__(self, name, rgb, description):
        self.__name = name.strip() # NB: this is readonly so it can be used as dict() key
        self.colour = self.COLOUR(rgb)
        self.description = description.strip()
    @property
    def name(self):
        return self.__name
    def __getattr__(self, attr_name):
        try:
            return getattr(self.colour, attr_name)
        except AttributeError:
            raise AttributeError(_("{}: unknown attribute for {}").format(attr_name, self.__class__.__name__))
