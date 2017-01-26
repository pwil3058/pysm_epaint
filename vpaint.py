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

from . import pchar
from . import rgbh

if __name__ == "__main__":
    import doctest
    _ = lambda x: x

class HCV:
    RGB = rgbh.RGB16
    # The "ideal" palette is one that contains the full range at full strength
    IDEAL_RGB_COLOURS = [RGB.WHITE, RGB.MAGENTA, RGB.RED, RGB.YELLOW, RGB.GREEN, RGB.CYAN, RGB.BLUE, RGB.BLACK]
    def __init__(self, rgb):
        self.__rgb = rgb.converted_to(self.RGB)
        self.__value = self.__rgb.get_value()
        xy = rgbh.Cartesian.from_rgb(self.__rgb)
        class Hue(rgbh.HueNG):
            RGB = self.RGB
        self.__hue = Hue.from_angle(xy.get_angle())
        self.__chroma = xy.get_hypot() * self.__hue.chroma_correction / self.RGB.ONE
        if self.RGB.BITS_PER_CHANNEL is None:
            self.__warmth = xy.x / self.RGB.ONE
        else:
            self.__warmth = fractions.Fraction(self.RGB.ROUND(xy.x), self.RGB.ONE)
    def __getattr__(self, attr_name):
        return getattr(self.__rgb, attr_name)
    def __getitem__(self, index):
        return self.rgb[index]
    @property
    def chroma(self):
        return self.__chroma
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
        return self.__hue.rgb_with_value(self.__value if value is None else value)
    def zero_chroma_rgb(self):
        # get the rgb for the grey which would result from this colour
        # having white or black (whichever is quicker) added until the
        # chroma value is zero (useful for displaying chroma values)
        if self.__hue.is_grey:
            return self.__value_rgb
        mcv = self.__hue.max_chroma_value()
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
            return hue.rgb_with_value(self.__value)
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

class Paint:
    COLOUR = None
    CHARACTERISTICS = None
    def __init__(self, name, rgb, **kwargs):
        self.__name = name # NB: this is readonly so it can be used as dict() key
        self.colour = self.COLOUR(rgb)
        self.characteristics = self.CHARACTERISTICS(**kwargs)
    @property
    def name(self):
        return self.__name
    def __getattr__(self, attr_name):
        try:
            return getattr(self.colour, attr_name)
        except AttributeError:
            return getattr(self.characteristics, attr_name)
    def set_rgb(self, rgb):
        self.colour = self.COLOUR(rgb)
    def set_characteristics(self, **kwargs):
        for c_name, c_value in kwargs.items():
            setattr(self.characteristics, c_name, c_value)
    def __ne__(self, other):
        if self.__name != other.__name:
            return True
        elif self.colour.rgb != other.colour.rgb:
            return True
        else:
            return self.characteristics != other.characteristics
    def __repr__(self):
        fmt_str = self.__class__.__name__ + "(name=\"{0}\", rgb={1}{2})"
        ename = re.sub('"', r'\"', self.__name)
        ergb = repr(self.colour.rgb)
        echaracteristics = ""
        for name in self.CHARACTERISTICS.NAMES:
            value = getattr(self.characteristics, name)
            echaracteristics += ", {0}=\"{1}\"".format(name, str(value))
        return fmt_str.format(ename, ergb, echaracteristics)


class ModelPaint(Paint):
    COLOUR = HCV
    class CHARACTERISTICS(pchar.Characteristics):
        NAMES = ("transparency", "finish")

class ArtPaint(Paint):
    COLOUR = HCVW
    class CHARACTERISTICS(pchar.Characteristics):
        NAMES = ("transparency", "permanence")

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

MODEL_NC_MATCHER = re.compile(r'^NamedColour\(name=(".+"), rgb=(.+), transparency="(.+)", finish="(.+)"\)$')
ART_NC_MATCHER = re.compile(r'^NamedColour\(name=(".+"), rgb=(.+), transparency="(.+)", permanence="(.+)"\)$')

class PaintSeries:
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
        # No i18n for these strings
        string = "Manufacturer: {0}\n".format(self.series_id.maker)
        string += "Series: {0}\n".format(self.series_id.name)
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
        from .rgbh import RGB8, RGB16, RGBPN
        lines = definition_text.splitlines()
        if len(lines) < 2:
            raise cls.ParseError(_("Too few lines: {0}.".format(len(lines))))
        match = re.match("^Manufacturer:\s+(\S.*)\s*$", lines[0])
        if not match:
            raise cls.ParseError(_("Manufacturer not found."))
        mfkr_name = match.group(1)
        match = re.match("^Series:\s+(\S.*)\s*$", lines[1])
        if not match:
            raise cls.ParseError(_("Series name not found."))
        series_name = match.group(1)
        series = cls(maker=mfkr_name, name=series_name)
        if len(lines) > 2:
            old_model_matcher = re.compile("(^[^:]+):\s+(RGB\([^)]+\)), (Transparency\([^)]+\)), (Finish\([^)]+\))$")
            old_art_matcher = re.compile('(^[^:]+):\s+(RGB\([^)]+\)), (Transparency\([^)]+\)), (Permanence\([^)]+\))$')
            if old_model_matcher.match(lines[2]):
                # Old format
                # TODO: remove support for old paint series format
                RGB = collections.namedtuple("RGB", ["red", "green", "blue"])
                colours = []
                for line in lines[2:]:
                    match = old_model_matcher.match(line)
                    if not match:
                        raise cls.ParseError(_("Badly formed definition: {0}.").format(line))
                    # Old data files were wx and hence 8 bits per channel
                    # so we need to convert them to 16 bist per channel
                    rgb = [channel << 8 for channel in eval(match.group(2))]
                    series.add_paint(ModelPaint(match.group(1), rgb, eval(match.group(3)), eval(match.group(4))))
            elif old_art_matcher.match(lines[2]):
                # Old format
                # TODO: remove support for old paint series format
                RGB = collections.namedtuple("RGB", ["red", "green", "blue"])
                colours = []
                for line in lines[2:]:
                    match = old_art_matcher.match(line)
                    if not match:
                        raise cls.ParseError(_("Badly formed definition: {0}.").format(line))
                    # Old data files were wx and hence 8 bits per channel
                    # so we need to convert them to 16 bist per channel
                    rgb = [channel << 8 for channel in eval(match.group(2))]
                    series.add_paint(ArtPaint(match.group(1), rgb, eval(match.group(3)), eval(match.group(4))))
            elif MODEL_NC_MATCHER.match(lines[2]):
                RGB = ModelPaint.COLOUR.RGB
                colours = []
                for line in lines[2:]:
                    match = MODEL_NC_MATCHER.match(line)
                    if not match:
                        raise cls.ParseError(_("Badly formed definition: {0}.").format(line))
                    name = eval(match.group(1))
                    rgb = eval(match.group(2))
                    series.add_paint(ModelPaint(name, rgb, transparency=match.group(3), finish=match.group(4)))
            elif ART_NC_MATCHER.match(lines[2]):
                RGB = ArtPaint.COLOUR.RGB
                colours = []
                for line in lines[2:]:
                    match = ART_NC_MATCHER.match(line)
                    if not match:
                        raise cls.ParseError(_("Badly formed definition: {0}.").format(line))
                    name = eval(match.group(1))
                    rgb = eval(match.group(2))
                    series.add_paint(ArtPaint(name, rgb, transparency=match.group(3), permanence=match.group(4)))
            else:
                RGB = ModelPaint.COLOUR.RGB
                for line in lines[2:]:
                    try:
                        series.add_paint(eval(line))
                    except TypeError as edata:
                        raise cls.ParseError(_("Badly formed definition: {0}. ({1})").format(line, str(edata)))
        return series

BLOB = collections.namedtuple("BLOB", ["colour", "parts"])

class Mixture:
    PAINT = None
    def __init__(self, blobs):
        rgb = self.PAINT.COLOUR.RGB.BLACK
        self.characteristics = self.PAINT.CHARACTERISTICS()
        parts = 0
        for blob in blobs:
            parts += blob.parts
            rgb += blob.colour.rgb * blob.parts
            self.characteristics += blob.colour.characteristics * blob.parts
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
            string += _("\t{0} Part(s): {1}\n").format(blob.parts, blob.colour)
        return string
    def __str__(self):
        return _("Mixed Colour: ") + Colour.__str__(self) + self._components_str()
    def contains_colour(self, colour):
        for blob in self.blobs:
            if blob.colour == colour:
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
    PAINT = ModelPaint

class MixedModelPaint(MixedPaint):
    MIXTURE = ModelMixture

class ArtMixture(Mixture):
    PAINT = ArtPaint

class MixedArtPaint(MixedPaint):
    MIXTURE = ArtMixture
