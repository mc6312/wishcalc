#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" wccommon.py

    This file is part of WishCalc.

    WishCalc is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    WishCalc is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with WishCalc.  If not, see <http://www.gnu.org/licenses/>."""


TITLE = 'WishCalc'
SUB_TITLE = 'Калькулятор загребущего нищеброда'

VERSION = '2.3.5'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)
COPYRIGHT = '(c) 2017-2019 MC-6312'
URL = 'https://github.com/mc6312/wishcalc'


from gtktools import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf
import cairo

from math import pi

from collections import namedtuple


iconError = load_system_icon('dialog-error', Gtk.IconSize.MENU)


def show_entry_error(entry, msg=None):
    """Установка состояния индикации ошибки в виджете класса
    Gtk.Entry.

    entry   - виджет,
    msg     - строка с сообщением об ошибке, если в поле ввода
              неправильное значение
              пустая строка или None, если ошибки нет."""

    entry.set_icon_from_pixbuf(Gtk.EntryIconPosition.SECONDARY,
        iconError if msg else None)
    entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY,
        msg if msg else None) # подстраховка для случая msg == ''


class ImportanceIcons():
    """Класс, создающий и хранящий список GdkPixbuf для отображения
    цветовых меток."""

    COLORS = (
        None,
        (0.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (1.0, 0.6, 0.0),
        (1.0, 0.0, 0.0),
        )

    MIN = 0
    MAX = len(COLORS) - 1

    def __init__(self, iconSize):
        """Создание списка икон (экземпляров GdkPixbuf.Pixbuf).

        Параметры:
            iconSize    - константа Gtk.IconSize.*.

        Поля:
            icons       - список экземпляров colorlabelicon."""

        _ok, self.iconSizePx, ih = Gtk.IconSize.lookup(iconSize)
        # прочие возвращённые значения фпень - у нас тут иконки строго квадратные

        self.icons = []

        sctx = Gtk.StyleContext.new()
        _ok, borderclr = sctx.lookup_color('theme_text_color')

        if not _ok:
            borderclr = (0.0, 0.0, 0.0)
        else:
            # потому что lookup_color возвращает Gdk.RGBA, а не кортеж
            borderclr = (borderclr.red, borderclr.green, borderclr.blue)

        for color in self.COLORS:
            self.icons.append(self.__create_icon(color, borderclr))

    def __create_icon(self, color, bordercolor):
        """Создаёт и возвращает экземпляр GdkPixbuf.Pixbuf заданного цвета.

        color   - значение цвета заполнения или None,
        sctx    - значение цвета каймы.
        Оба цветовых параметра - кортежи из трёх или четырёх вещественных
        чисел (R, G, B)/(R, G, B, A)."""

        csurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.iconSizePx, self.iconSizePx)

        cc = cairo.Context(csurf)

        center = self.iconSizePx / 2.0
        radius = center * 0.6
        circle = 2 * pi

        alpha = 1.0 if color is not None else 0.4

        cc.set_source(cairo.SolidPattern(*bordercolor[:3], alpha))

        cc.arc(center, center, radius, 0.0, circle)

        cc.set_line_width(1.0)
        cc.stroke_preserve()

        radius1 = radius - 0.5

        if color is not None:
            patn = cairo.SolidPattern(*color)

            cc.set_source(patn)
            cc.arc(center, center, radius1, 0.0, circle)
            cc.fill()

        return Gdk.pixbuf_get_from_surface(csurf, 0, 0, self.iconSizePx, self.iconSizePx)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    labels = ImportanceIcons(Gtk.IconSize.MENU)
