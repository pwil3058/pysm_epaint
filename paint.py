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

class RGB(rgbh.RGB16):
    __slots__ = ()
    def __add__(self, other):
        """
        Add two RGB values together
        """
        return RGB(red=self.red + other.red, green=self.green + other.green, blue=self.blue + other.blue)
    def __sub__(self, other):
        """
        Subtract one RGB value from another
        """
        return RGB(red=self.red - other.red, green=self.green - other.green, blue=self.blue - other.blue)
    def __mul__(self, mul):
        """
        Multiply all components by a fraction preserving component type
        """
        return RGB(*(self.ROUND(self[i] * mul) for i in range(3)))
    def __truediv__(self, div):
        """
        Divide all components by a value
        """
        return RGB(*(self.ROUND(self[i] / div) for i in range(3)))
    def __str__(self):
        return "RGB(0x{0:X}, 0x{1:X}, 0x{2:X})".format(*self)
    @staticmethod
    def rotated(rgb, delta_hue_angle):
        return RGB(*rgbh.RGB16.rotated(rgb, delta_hue_angle))

class Hue(rgbh.Hue16):
    pass

# The "ideal" palette is one that contains the full range at full strength
IDEAL_RGB_COLOURS = [RGB.WHITE, RGB.MAGENTA, RGB.RED, RGB.YELLOW, RGB.GREEN, RGB.CYAN, RGB.BLUE, RGB.BLACK]
IDEAl_COLOUR_NAMES = ["WHITE", "MAGENTA", "RED", "YELLOW", "GREEN", "CYAN", "BLUE", "BLACK"]

class HCV:
    def __init__(self, rgb):
        self.rgb = RGB(*rgb)
        self.value = self.rgb.get_value()
        xy = rgbh.Cartesian.from_rgb(self.rgb)
        self.hue = Hue.from_angle(xy.get_angle())
        self.chroma = xy.get_hypot() * self.hue.chroma_correction / RGB.ONE
    def __getattr__(self, attr_name):
        return getattr(self.rgb, attr_name)
    @property
    def hue_rgb(self):
        return RGB(*self.hue.rgb)
    @property
    def value_rgb(self):
        return RGB.WHITE * self.value
    def hue_rgb_for_value(self, value=None):
        if value is None:
            # i.e. same hue and value but without any unnecessary grey
            value = self.value
        return RGB(*self.hue.rgb_with_value(value))
    def zero_chroma_rgb(self):
        # get the rgb for the grey which would result from this colour
        # having white or black (whichever is quicker) added until the
        # chroma value is zero (useful for displaying chroma values)
        if self.hue.is_grey():
            return self.value_rgb
        mcv = self.hue.max_chroma_value()
        dc = 1.0 - self.chroma
        if dc != 0.0:
            return RGB.WHITE * ((self.value - mcv * self.chroma) / dc)
        elif mcv < 0.5:
            return RGB.BLACK
        else:
            return RGB.WHITE
    def chroma_side(self):
        # Is it darker or lighter than max chroma for the hue?
        if sum(self.rgb) > sum(self.hue.rgb):
            return RGB.WHITE
        else:
            return RGB.BLACK
    def get_rotated_rgb(self, delta_hue_angle):
        """
        Return a copy of our rgb rotated by the given amount but with
        the same value and without unavoidable chroma change.
        from .bab import mathx
        >>> HCV((10, 10, 0)).get_rotated_rgb(-mathx.PI_60)
        RGB(red=20, green=0, blue=0)
        """
        if RGB.ncomps(self.rgb) == 2:
            # we have no grey so only add grey if necessary to maintain value
            hue = Hue.from_angle(self.hue.angle + delta_hue_angle)
            return RGB(*hue.rgb_with_value(self.value))
        else:
            # Simple rotation is the correct solution for 1 or 3 components
            return RGB.rotated(self.rgb, delta_hue_angle)
    def __str__(self):
        string = "(HUE = {0}, ".format(str(self.hue.rgb))
        string += "VALUE = {0}, ".format(round(self.value, 2))
        string += "CHROMA = {0})".format(round(self.chroma, 2))
        return string

class HCVW(HCV):
    def __init__(self, rgb):
        HCV.__init__(self, rgb)
        xy = rgbh.Cartesian.from_rgb(self.rgb)
        self.warmth = fractions.Fraction.from_float(xy.x / RGB.ONE)
    @property
    def warmth_rgb(self):
        return (RGB.CYAN * (1 - self.warmth) + RGB.RED * (1 + self.warmth)) / 2
    def __getattr__(self, attr_name):
        return getattr(self.rgb, attr_name)
    def __str__(self):
        string = "(HUE = {0}, ".format(str(self.hue.rgb))
        string += "VALUE = {0}, ".format(round(self.value, 2))
        string += "CHROMA = {0}, ".format(round(self.chroma, 2))
        string += "WARMTH = {0})".format(round(self.warmth, 2))
        return string

class NamedColour(collections.namedtuple("NamedColour", ["name", "colour"])):
    def __getattr__(self, attr_name):
        return getattr(self.colour, attr_name)
    def __repr__(self):
        fmt_str = "NamedColour(name=\"{0}\", colour={1})"
        return fmt_str.format(re.sub('"', r'\"', self.name), repr(self.colour))
    def __str__(self):
        return self.name
    def __len__(self):
        return len(self.name)


WHITE, MAGENTA, RED, YELLOW, GREEN, CYAN, BLUE, BLACK = [NamedColour(name, HCVW(rgb)) for name, rgb in zip(IDEAl_COLOUR_NAMES, IDEAL_RGB_COLOURS)]
IDEAL_COLOURS = [WHITE, MAGENTA, RED, YELLOW, GREEN, CYAN, BLUE, BLACK]

class Paint:
    COLOUR = None
    CHARACTERISTICS = None
    def __init__(self, name, rgb, **kwargs):
        self.name = name
        self.colour = self.COLOUR(rgb)
        self.characteristics = self.CHARACTERISTICS(**kwargs)
    def __getattr__(self, attr_name):
        try:
            return getattr(self.colour, attr_name)
        except AttributeError:
            return getattr(self.characteristics, attr_name)
    def set_rgb(self, rgb):
        self.colour = self.COLOUR(rgb)
    def set_characteristic(self, c_name, c_value):
        setattr(self.characteristics, c_name, c_value)

class ModelPaintCharacteristics(pchar.Characteristics):
    NAMES = ("transparency", "finish")

class ModelPaint(Paint):
    COLOUR = HCV
    CHARACTERISTICS = ModelPaintCharacteristics
    def __repr__(self):
        fmt_str = "ModelPaint(name=\"{0}\", rgb={1}, transparency=\"{2}\", finish=\"{3}\")"
        return fmt_str.format(re.sub('"', r'\"', self.name), self.rgb, self.transparency, self.finish)

class ArtPaintCharacteristics(pchar.Characteristics):
    NAMES = ("transparency", "permanence")

class ArtPaint(Paint):
    COLOUR = HCVW
    CHARACTERISTICS = ArtPaintCharacteristics
    def __repr__(self):
        fmt_str = "ModelPaint(name=\"{0}\", rgb={1}, transparency=\"{2}\", permanence=\"{3}\")"
        return fmt_str.format(re.sub('"', r'\"', self.name), self.rgb, self.transparency, self.permanence)

SERIES_ID = collections.namedtuple("SERIES_ID", ["maker", "name"])

class SeriesPaint(collections.namedtuple("SeriesPaint", ["series", "paint"])):
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
        self.paints = {}
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
        if isinstance(paint, SeriesPaint):
            self.paints[paint.name] = SeriesPaint(self, paint.paint)
        else:
            self.paints[paint.name] = SeriesPaint(self, paint)
    def definition_text(self):
        # No i18n for these strings
        string = "Manufacturer: {0}\n".format(self.series_id.maker)
        string += "Series: {0}\n".format(self.series_id.name)
        for paint in sorted(self.paints.values(), key=lambda x: x.name):
            string += "{0}\n".format(repr(paint.paint))
        return string
    @property
    def paint_colours(self): # replace with __iter__
        return self.paints
    @classmethod
    def fm_definition(cls, definition_text):
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
                colours = []
                for line in lines[2:]:
                    match = MODEL_NC_MATCHER.match(line)
                    if not match:
                        raise cls.ParseError(_("Badly formed definition: {0}.").format(line))
                    name = eval(match.group(1))
                    rgb = eval(match.group(2))
                    series.add_paint(ModelPaint(name, rgb, transparency=match.group(3), finish=match.group(4)))
            elif ART_NC_MATCHER.match(lines[2]):
                colours = []
                for line in lines[2:]:
                    match = ART_NC_MATCHER.match(line)
                    if not match:
                        raise cls.ParseError(_("Badly formed definition: {0}.").format(line))
                    name = eval(match.group(1))
                    rgb = eval(match.group(2))
                    series.add_paint(ModelPaint(name, rgb, transparency=match.group(3), permanence=match.group(4)))
            else:
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
        rgb = RGB.BLACK # TODO: use PAINT to get this
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

if __name__ == "__main__":
    doctest.testmod()
