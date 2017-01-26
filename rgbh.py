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
Implement types to represent red/green/blue data as a tuple and
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

if __name__ == "__main__":
    import doctest
    _ = lambda x: x

# Anonymous
RGB = collections.namedtuple("RGB", ["red", "green", "blue"])

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
        return array.array(cls.ARRAY_TYPECODE, *self.__components)
    def best_foreground_is_black(self, threshold=0.5):
        return (self.__components[0] * 0.299 + self.__components[1] * 0.587 + self.__components[2] * 0.114) > self.ONE * threshold
    def best_foreground(self, threshold=0.5):
        return self.BLACK if self.best_foreground_is_black(threshold) else self.WHITE
    def best_foreground_gdk_color(self, threshold=0.5):
        return Gdk.Color(0, 0, 0) if self.best_foreground_is_black(threshold) else Gdk.Color(BPC16.ONE, BPC16.ONE, BPC16.ONE)
    def best_foreground_gdk_rgba(self, threshold=0.5):
        return Gdk.RGBA(0.0, 0.0, 0.0, 1.0) if self.best_foreground_is_black(threshold) else Gdk.RGBA(1.0, 1.0, 1.0)
    def get_indices_value_order(self):
        """Return our rgb indices in descending order by value
        """
        if self.__components[0] > self.__components[1]:
            if self.__components[0] > self.__components[2]:
                if self.__components[1] > self.__components[2]:
                    return (0, 1, 2)
                else:
                    return (0, 2, 1)
            else:
                return (2, 0, 1)
        elif self.__components[1] > self.__components[2]:
            if self.__components[0] > self.__components[2]:
                return (1, 0, 2)
            else:
                return (1, 2, 0)
        else:
            return (2, 1, 0)
    @property
    def non_zero_components(self):
        """Return the number of non zero components
        """
        return 3 - self.__components.count(0)
    def rotated(self, delta_hue_angle):
        """
        Return a copy of ourself with the same value but the hue angle rotated
        by the specified amount and with the item types unchanged.
        NB chroma changes when less than 3 non zero components and in the
        case of 2 non zero components this change is undesirable and
        needs to be avoided by using a higher level wrapper function
        that is aware of item types and maximum allowed value per component.
        from .bab import mathx
        """
        def calc_ks(delta_hue_angle):
            a = math.sin(delta_hue_angle)
            b = math.sin(mathx.PI_120 - delta_hue_angle)
            c = a + b
            k1 = b / c
            k2 = a / c
            return (k1, k2)
        f = lambda c1, c2: self.ROUND(self.__components[c1] * k1 + self.__components[c2] * k2)
        if delta_hue_angle > 0:
            if delta_hue_angle > mathx.PI_120:
                k1, k2 = calc_ks(delta_hue_angle - mathx.PI_120)
                return self.__class__(f(2, 1), f(0, 2), f(1, 0))
            else:
                k1, k2 = calc_ks(delta_hue_angle)
                return self.__class__(f(0, 2), f(1, 0), f(2, 1))
        elif delta_hue_angle < 0:
            if delta_hue_angle < -mathx.PI_120:
                k1, k2 = calc_ks(abs(delta_hue_angle) - mathx.PI_120)
                return self.__class__(f(1, 2), f(2, 0), f(0, 1))
            else:
                k1, k2 = calc_ks(abs(delta_hue_angle))
                return self.__class__(f(0, 1), f(1, 2), f(2, 0))
        else:
            return self.__class__(*self)

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

class HueNG(collections.namedtuple("Hue", ["io", "other", "angle", "chroma_correction"])):
    RGB = None
    @classmethod
    def from_angle(cls, angle):
        if math.isnan(angle):
            return cls(io=None, other=cls.RGB.ONE, angle=angle, chroma_correction=1.0)
        assert abs(angle) <= math.pi
        def calc_other(oa):
            scale = math.sin(oa) / math.sin(mathx.PI_120 - oa)
            return cls.RGB.ROUND(cls.RGB.ONE * scale)
        aha = abs(angle)
        if aha <= mathx.PI_60:
            other = calc_other(aha)
            io = (0, 1, 2) if angle >= 0 else (0, 2, 1)
        elif aha <= mathx.PI_120:
            other = calc_other(mathx.PI_120 - aha)
            io = (1, 0, 2) if angle >= 0 else (2, 0, 1)
        else:
            other = calc_other(aha - mathx.PI_120)
            io = (1, 2, 0) if angle >= 0 else (2, 1, 0)
        a = cls.RGB.ONE
        b = other
        # avoid floating point inaccuracies near 1
        cc = 1.0 if a == b or b == 0 else a / math.sqrt(a * a + b * b - a * b)
        return cls(io=io, other=other, angle=mathx.Angle(angle), chroma_correction=cc)
    @classmethod
    def from_rgb(cls, rgb):
        # NB: we're assuming that rgb is of type self.RGB
        return cls.from_angle(Cartesian.from_rgb(rgb).get_angle())
    def __eq__(self, other):
        if math.isnan(self.angle):
            return math.isnan(other.angle)
        return self.angle.__eq__(other.angle)
    def __ne__(self, other):
        return not self.__eq__(other.angle)
    def __lt__(self, other):
        if math.isnan(self.angle):
            return not math.isnan(other.angle)
        return self.angle.__lt__(other.angle)
    def __le__(self, other):
        return self.__lt__(other.angle) or self.__eq__(other.angle)
    def __gt__(self, other):
        return not self.__le__(other.angle)
    def __ge__(self, other):
        return not self.__lt__(other.angle)
    def __sub__(self, other):
        diff = self.angle - other.angle
        if diff > math.pi:
            diff -= math.pi * 2
        elif diff < -math.pi:
            diff += math.pi * 2
        return diff
    @property
    def rgb_array(self):
        if math.isnan(self.angle):
            return array.array(self.RGB.ARRAY_TYPECODE, (self.RGB.ONE, self.RGB.ONE, self.RGB.ONE))
        result = array.array(self.RGB.ARRAY_TYPECODE, [self.RGB.ZERO, self.RGB.ZERO, self.RGB.ZERO])
        result[self.io[0]] = self.RGB.ONE
        result[self.io[1]] = self.other
        return result
    @property
    def rgb(self):
        if math.isnan(self.angle):
            return self.RGB.WHITE
        result = [self.RGB.ZERO, self.RGB.ZERO, self.RGB.ZERO]
        result[self.io[0]] = self.RGB.ONE
        result[self.io[1]] = self.other
        return self.RGB(*result)
    def to_gdk_rgba(self, alpha=1.0):
        return Gdk.RGBA(*([self.RGB.convert_chnl_value(chnl, RGBPN) for chnl in self.rgb] + [alpha]))
    def best_foreground_gdk_color(self, threshold=0.5):
        return self.rgb.best_foreground_gdk_color(threshold)
    def best_foreground_gdk_rgba(self, threshold=0.5):
        return self.rgb.best_foreground_gdk_rgba(threshold)
    def max_chroma_value(self):
        mct = self.RGB.ONE + self.other
        return mct / self.RGB.THREE if self.RGB.BITS_PER_CHANNEL is None else fractions.Fraction(mct, self.RGB.THREE)
    def max_chroma_for_total(self, total):
        if math.isnan(self.angle):
            return min(1.0, float(total) /self.RGB.ONE)
        mct = self.RGB.ONE + self.other
        if mct > total:
            return total / mct
        else:
            angle = self.angle if self.io[0] == 0 else (self.angle - mathx.PI_120 if self.io[0] == 1 else self.angle + mathx.PI_120)
            return ((self.RGB.THREE - total) / (2.0 * math.cos(angle))) * self.chroma_correction
    def max_chroma_for_value(self, value):
        return self.max_chroma_for_total(value * self.RGB.THREE)
    def rgb_array_with_total(self, req_total):
        """
        return the RGB for this hue with the specified component total
        NB if requested value is too big for the hue the returned value
        will deviate towards the weakest component on its way to white.
        Return: a tuple with proportion components of the same type
        as our rgb
        """
        if math.isnan(self.angle):
            val = self.RGB.ROUND(req_total / 3.0)
            return array.array(self.RGB.ARRAY_TYPECODE, (val, val, val))
        cur_total = self.RGB.ONE + self.other
        shortfall = req_total - cur_total
        result = array.array(self.RGB.ARRAY_TYPECODE, [self.RGB.ZERO, self.RGB.ZERO, self.RGB.ZERO])
        if shortfall == 0:
            result[self.io[0]] = self.RGB.ONE
            result[self.io[1]] = self.other
        elif shortfall < 0:
            result[self.io[0]] = self.RGB.ROUND(self.RGB.ONE * req_total / cur_total)
            result[self.io[1]] = self.RGB.ROUND(self.other * req_total / cur_total)
        else:
            result[self.io[0]] = self.RGB.ONE
            # it's simpler two work out the weakest component first
            result[self.io[2]] = self.RGB.ROUND((shortfall * self.RGB.ONE) / (2 * self.RGB.ONE - self.other))
            result[self.io[1]] = self.other + shortfall - result[self.io[2]]
        return result
    def rgb_with_value(self, value):
        """
        return the RGB for this hue with the specified value
        NB if requested value is too big for the hue the returned value
        will deviate towards the weakest component on its way to white.
        Return: a tuple with proportion components of the same type
        as our rgb
        """
        return self.RGB(*self.rgb_array_with_total(self.RGB.ROUND(value * max(self.rgb) * 3)))
    @property
    def is_grey(self):
        return math.isnan(self.angle)
    def rotated_by(self, delta_angle):
        return self.__class__.from_angle(self.angle + delta_angle)
    def get_xy_for_chroma(self, chroma):
        assert chroma > 0 and chroma <= 1.0
        hypot = chroma * self.RGB.ONE / self.chroma_correction
        return Cartesian(hypot * math.cos(self.angle), hypot * math.sin(self.angle), self.RGB)

class Hue8(HueNG):
    RGB = RGB8

class Hue16(HueNG):
    RGB = RGB16

class HuePN(HueNG):
    RGB = RGBPN

SIN_60 = math.sin(mathx.PI_60)
SIN_120 = math.sin(mathx.PI_120)
COS_120 = -0.5 # math.cos(mathx.PI_120) is slightly out


class Cartesian:
    __slots__ = ("x", "y", "rgb_cls")
    X_VECTOR = (1.0, COS_120, COS_120)
    Y_VECTOR = (0.0, SIN_120, -SIN_120)
    @classmethod
    def from_rgb(cls, rgb):
        """Return an Cartesian instance derived from the specified rgb.
        """
        x = sum(cls.X_VECTOR[i] * rgb[i] for i in range(3))
        y = sum(cls.Y_VECTOR[i] * rgb[i] for i in range(1, 3))
        return cls(x=x, y=y, rgb_cls=rgb.__class__)
    def __init__(self, x, y, rgb_cls):
        self.x = x
        self.y = y
        self.rgb_cls = rgb_cls
    def __iter__(self):
        return (coord for coord in (self.x, self.y))
    def __mul__(self, factor):
        return self.__class__(self.x * factor, self.y * factor, self.rgb_cls)
    def get_angle(self):
        if self.x == 0.0 and self.y == 0.0:
            return float("nan")
        else:
            return math.atan2(self.y, self.x)
    def get_hypot(self):
        """Return our hypotenuse
        """
        return math.hypot(self.x, self.y)
    def get_simplest_rgb(self):
        """Return the RGB with at most 2 non-zero components that matches our x and y.
        """
        a = self.x / COS_120
        b = self.y / SIN_120
        if self.y > 0.0:
            if a > b:
                frgb = (0.0, ((a + b) / 2), ((a - b) / 2))
            else:
                frgb = ((self.x - b * COS_120), b, 0.0)
        elif self.y < 0.0:
            if a > -b:
                frgb = (0.0, ((a + b) / 2), ((a - b) / 2))
            else:
                frgb = ((self.x + b * COS_120), 0.0, -b)
        elif self.x < 0.0:
            ha = a / 2
            frgb = (0.0, ha, ha)
        else:
            frgb = (self.x, 0.0, 0.0)
        return self.rgb_cls(*(self.rgb_cls.ROUND(c) for c in frgb))

class RGBManipulator(object):
    def __init__(self, rgb):
        self.set_rgb(rgb)
    def set_rgb(self, rgb):
        self._rgb_cls = rgb.__class__
        self.__set_rgb(rgb.rgbpn)
        self.__last_hue = self.hue
    def __set_rgb(self, rgb):
        self.__rgb = rgb
        self.value = self.__rgb.get_value()
        self.xy = Cartesian.from_rgb(self.__rgb)
        self.__base_rgb = self.xy.get_simplest_rgb()
        self.hue = HuePN.from_angle(self.xy.get_angle())
        self.chroma = min(self.xy.get_hypot() * self.hue.chroma_correction, 1.0)
    def _min_value_for_current_HC(self):
        return self.__base_rgb.get_value()
    def _max_value_for_current_HC(self):
        return self.__base_rgb.get_value() + 1.0 - max(self.__base_rgb)
    def get_rgb(self, rgbt=None):
        if rgbt is None:
            rgbt = self._rgb_cls
        return rgbt(*[rgbt.ROUND(c * rgbt.ONE) for c in self.__rgb])
    def _set_from_value(self, new_value):
        new_chroma = self.hue.max_chroma_for_value(new_value)
        new_base_rgb = self.hue.get_xy_for_chroma(new_chroma).get_simplest_rgb()
        delta = new_value - new_base_rgb.get_value()
        self.__set_rgb(RGBPN(*[c + delta for c in new_base_rgb]))
    def _set_from_chroma(self, new_chroma):
        ratio = new_chroma / self.chroma
        new_base_rgb = (self.xy * ratio).get_simplest_rgb()
        delta = min(1.0 - max(new_base_rgb), self.value - new_base_rgb.get_value())
        if delta > 0.0:
            self.__set_rgb(RGBPN(*[c + delta for c in new_base_rgb]))
        else:
            self.__set_rgb(new_base_rgb)
    def decr_value(self, deltav):
        if self.value <= 0.0:
            return False
        new_value = max(0.0, self.value - deltav)
        min_value = self._min_value_for_current_HC()
        if new_value == 0.0:
            self.__set_rgb(RGBPN(0.0, 0.0, 0.0))
        elif new_value < min_value:
            self._set_from_value(new_value)
        else:
            delta = new_value - min_value
            self.__set_rgb(RGBPN(*[c + delta for c in self.__base_rgb]))
        return True
    def incr_value(self, deltav):
        if self.value >= 1.0:
            return False
        new_value = min(1.0, self.value + deltav)
        max_value = self._max_value_for_current_HC()
        if new_value >= 1.0:
            self.__set_rgb(RGBPN(1.0, 1.0, 1.0))
        elif new_value > max_value:
            self._set_from_value(new_value)
        else:
            delta = new_value - self._min_value_for_current_HC()
            self.__set_rgb(RGBPN(*[c + delta for c in self.__base_rgb]))
        return True
    def decr_chroma(self, deltac):
        if self.chroma <= 0.0:
            return False
        self._set_from_chroma(max(0.0, self.chroma - deltac))
        return True
    def incr_chroma(self, deltac):
        if self.chroma >= 1.0:
            return False
        if self.hue.is_grey:
            if self.value <= 0.0 or self.value >= 1.0:
                if self.__last_hue.is_grey:
                    # any old hue will do
                    new_base_rgb = HuePN.from_angle(0.5).get_xy_for_chroma(deltac).get_simplest_rgb()
                else:
                    new_base_rgb = self.__last_hue.get_xy_for_chroma(deltac).get_simplest_rgb()
                if self.value <= 0.0:
                    self.__set_rgb(new_base_rgb)
                else:
                    delta = 1.0 - max(new_base_rgb)
                    self.__set_rgb(RGBPN(*[c + delta for c in new_base_rgb]))
            else:
                max_chroma = self.__last_hue.max_chroma_for_value(self.value)
                new_chroma = min(deltac, max_chroma)
                if self.__last_hue.is_grey:
                    # any old hue will do
                    new_base_rgb = HuePN.from_angle(0.5).get_xy_for_chroma(new_chroma).get_simplest_rgb()
                else:
                    new_base_rgb = self.__last_hue.get_xy_for_chroma(new_chroma).get_simplest_rgb()
                # delta should be greater than or equal to zero
                delta = self.value - new_base_rgb.get_value()
                self.__set_rgb(RGBPN(*[c + delta for c in new_base_rgb]))
            self.__last_hue = self.hue
        else:
            self._set_from_chroma(min(1.0, self.chroma + deltac))
        return True
    def rotate_hue(self, deltah):
        if self.hue.is_grey:
            return False # There is no hue to rotate
        # keep same chroma
        new_base_rgb = self.hue.rotated_by(deltah).get_xy_for_chroma(self.chroma).get_simplest_rgb()
        # keep same value if possible (otherwise as close as possible)
        max_delta = 1.0 - max(new_base_rgb)
        delta = min(max_delta, self.value - new_base_rgb.get_value())
        if delta > 0.0:
            self.__set_rgb(RGBPN(*[c + delta for c in new_base_rgb]))
        else:
            self.__set_rgb(new_base_rgb)
        self.__last_hue = self.hue
        return True
