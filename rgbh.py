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

"""Implement types to represent red/green/blue data as a tuple and
map to painterly attributes such as value (lightness/darkness),
chroma (opposite of greyness) and hue (as an angle with red = 0).
"""

import collections
import math
import array
import fractions

from gi.repository import Gdk

from ..bab.decorators import classproperty
from ..bab import mathx

from ..gtx import rgb_math


class ConversionMixin:
    @classmethod
    def convert_chnl_value(cls, chnl_value, to_cls):
        return to_cls.ROUND((chnl_value * to_cls.ONE) / cls.ONE )

# 8 bits per channel specific constants
class BPC8(ConversionMixin):
    ZERO = 0
    BITS_PER_CHANNEL = 8
    ONE = (1 << BITS_PER_CHANNEL) - 1
    TWO = ONE * 2
    THREE = ONE * 3
    SIX = ONE * 6
    ARRAY_TYPECODE = "B"
    @classmethod
    def ROUND(cls, x):
        return int(x + 0.5)

# 16 bits per channel specific constants
class BPC16(ConversionMixin):
    ZERO = 0
    BITS_PER_CHANNEL = 16
    ONE = (1 << BITS_PER_CHANNEL) - 1
    TWO = ONE * 2
    THREE = ONE * 3
    SIX = ONE * 6
    ARRAY_TYPECODE = "H"
    @classmethod
    def ROUND(cls, x):
        return int(x + 0.5)

# Proportion (i.e. real numbers in the range 0 to 1.0) channel constants
class PROPN_CHANNELS(ConversionMixin):
    ZERO = 0.0
    BITS_PER_CHANNEL = None
    ONE = 1.0
    TWO = ONE * 2
    THREE = ONE * 3
    SIX = ONE * 6
    ARRAY_TYPECODE = "f"
    @classmethod
    def ROUND(cls, x):
        return float(x)

class RGBNG: # NB: We don't want most of list/tuple operations so use a wrapper
    __slots__ = ("__components")
    def __init__(self, red, green, blue):
        self.__components = (red, green, blue)
    @classmethod
    def from_prgb(cls, prgb):
        return cls(*(cls.ROUND(c * cls.ONE) for c in prgb))
    @property
    def red(self):
        return self.__components[0]
    @property
    def green(self):
        return self.__components[1]
    @property
    def blue(self):
        return self.__components[2]
    @property
    def rgb8(self):
        return self.converted_to(RGB8)
    @property
    def rgb16(self):
        return self.converted_to(RGB16)
    @property
    def rgbpn(self):
        return self.converted_to(RGBPN)
    @property
    def gdk_color(self):
        if self.BITS_PER_CHANNEL is None:
            return Gdk.Color.from_floats(*self.__components)
        elif self.BITS_PER_CHANNEL == 16:
            return Gdk.Color(*self.__components)
        else:
            return Gdk.Color(*self.converted_to(RGB16))
    @property
    def cairo_rgb(self):
        return self.converted_to(RGBPN)
    def __eq__(self, other):
        return self.__components == other.__components
    def __ne__(self, other):
        return self.__components != other.__components
    def __getitem__(self, index):
        return self.__components[index]
    def __iter__(self):
        return (component for component in self.__components)
    def __len__(self):
        return len(self.__components)
    def __add__(self, other):
        return self.__class__(*(mine + others for mine, others in zip(self.__components, other)))
        #return self.__class__(red=self.red + other.red, green=self.green + other.green, blue=self.blue + other.blue)
    def __sub__(self, other):
        return self.__class__(*(mine - others for mine, others in zip(self.__components, other)))
        #return self.__class__(red=self.red - other.red, green=self.green - other.green, blue=self.blue - other.blue)
    def __mul__(self, mul):
        return self.__class__(*(self.ROUND(component * mul) for component in self.__components))
    def __truediv__(self, div):
        return self.__class__(*(self.ROUND(component / div) for component in self.__components))
    def __str__(self):
        return self._format_str.format(self)
    def __repr__(self):
        return str(self)
    def count(self, value):
        return self.__components.count(value)
    def get_value(self):
        total = sum(self)
        return total / self.THREE if self.BITS_PER_CHANNEL is None else fractions.Fraction(total, self.THREE)
    def converted_to(self, rgbt):
        if rgbt.ONE == self.ONE:
            return rgbt(*self.__components)
        else:
            return rgbt(*[rgbt.ROUND((component * rgbt.ONE) / self.ONE) for component in self.__components])
    def as_array(self):
        return array.array(self.ARRAY_TYPECODE, self.__components)
    def best_foreground_is_black(self, threshold=0.5):
        return (self.__components[0] * 0.299 + self.__components[1] * 0.587 + self.__components[2] * 0.114) > self.ONE * threshold
    def best_foreground(self, threshold=0.5):
        return self.BLACK if self.best_foreground_is_black(threshold) else self.WHITE
    def best_foreground_gdk_color(self, threshold=0.5):
        return Gdk.Color(0, 0, 0) if self.best_foreground_is_black(threshold) else Gdk.Color(BPC16.ONE, BPC16.ONE, BPC16.ONE)
    def best_foreground_gdk_rgba(self, threshold=0.5):
        return Gdk.RGBA(0.0, 0.0, 0.0, 1.0) if self.best_foreground_is_black(threshold) else Gdk.RGBA(1.0, 1.0, 1.0)
    @property
    def non_zero_components(self):
        """Return the number of non zero components
        """
        return 3 - self.__components.count(0)
    def rotated(self, delta_hue_angle):
        return self.__class__(*[self.ROUND(c) for c in rgb_math.rotate_rgb(self.__components, delta_hue_angle)])


class ColourConstantsMixin:
    """Constants for the three primary colours, three secondary
    colours, black and white for the derived RGB type
    """
    @classproperty
    def BLACK(cls):
        return cls(cls.ZERO, cls.ZERO, cls.ZERO)
    @classproperty
    def RED(cls):
        return cls(cls.ONE, cls.ZERO, cls.ZERO)
    @classproperty
    def GREEN(cls):
        return cls(cls.ZERO, cls.ONE, cls.ZERO)
    @classproperty
    def BLUE(cls):
        return cls(cls.ZERO, cls.ZERO, cls.ONE)
    @classproperty
    def YELLOW(cls):
        return cls(cls.ONE, cls.ONE, cls.ZERO)
    @classproperty
    def CYAN(cls):
        return cls(cls.ZERO, cls.ONE, cls.ONE)
    @classproperty
    def MAGENTA(cls):
        return cls(cls.ONE, cls.ZERO, cls.ONE)
    @classproperty
    def WHITE(cls):
        return cls(cls.ONE, cls.ONE, cls.ONE)
    @classproperty
    def _format_str(cls):
        s = cls.__name__ + "("
        if cls.BITS_PER_CHANNEL is None:
            s += "red={0.red:.8f}, green={0.green:.8f}, blue={0.blue:.8f})"
        else:
            s += "red=0x{{0.red:X}}, green=0x{{0.green:X}}, blue=0x{{0.blue:X}})".format(cls.BITS_PER_CHANNEL / 4)
        return s

class RGB8(RGBNG, BPC8, ColourConstantsMixin):
    def get_value(self):
        return fractions.Fraction(sum(self), self.THREE)
    def to_gdk_rgba(self, alpha=1.0):
        return self.converted_to(RGPN).to_gtk_rba(alpha=alpha)
    @property
    def rgb8(self):
        return self

class RGB16(RGBNG, BPC16, ColourConstantsMixin):
    def get_value(self):
        return fractions.Fraction(sum(self), self.THREE)
    def to_gdk_rgba(self, alpha=1.0):
        return self.converted_to(RGPN).to_gtk_rba(alpha=alpha)
    @property
    def rgb16(self):
        return self

class RGBPN(RGBNG, PROPN_CHANNELS, ColourConstantsMixin):
    def get_value(self):
        return sum(self) / self.THREE
    def to_gdk_rgba(self, alpha=1.0):
        return Gdk.RGBA(red=self.red, green=self.green, blue=self.blue, alpha=alpha)
    @property
    def rgbpn(self):
        return self
    @property
    def cairo_rgb(self):
        return self

class HueNG(rgb_math.HueAngle):
    """A hue angle with an associated RGB type which will be the return
    type for RGB related functions and whose ARRAY_TYPECODE will be the
    default for RGB array related functions
    """
    RGB = None

    @property
    def rgb_array(self):
        return self.max_chroma_rgb_array()

    @property
    def rgb(self):
        return self.max_chroma_rgb

    @property
    def max_chroma_rgb(self):
        return self.RGB.from_prgb(self.max_chroma_prgb)

    def max_chroma_rgb_array(self, typecode=None):
        return rgb_math.HueAngle.max_chroma_rgb_array(self, typecode if typecode else self.RGB.ARRAY_TYPECODE)

    def to_gdk_rgba(self, alpha=1.0):
        return Gdk.RGBA(*([self.RGB.convert_chnl_value(chnl, RGBPN) for chnl in self.rgb] + [alpha]))

    def best_foreground_gdk_color(self, threshold=0.5):
        return self.rgb.best_foreground_gdk_color(threshold)

    def best_foreground_gdk_rgba(self, threshold=0.5):
        return self.rgb.best_foreground_gdk_rgba(threshold)

    def max_chroma_rgb_with_value(self, value):
        """
        return the RGB for this hue with the specified value and the
        maximum chroma achievable for the combination.
        NB if requested value is too big for the hue the returned value
        will deviate towards the weakest component on its way to white.
        """
        return self.RGB.from_prgb(self.max_chroma_prgb_with_value(value))

    def max_chroma_rgb_array_with_value(self, req_value, array_type_code=None):
        return rgb_math.max_chroma_rgb_array_with_value(self, req_value, array_type_code if array_type_code else self.RGB.ARRAY_TYPECODE)

class Hue8(HueNG):
    RGB = RGB8

class Hue16(HueNG):
    RGB = RGB16

class HuePN(HueNG):
    RGB = RGBPN
