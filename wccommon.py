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

VERSION = '2.6.0'

TITLE_VERSION = '%s v%s' % (TITLE, VERSION)
COPYRIGHT = '(c) 2017-2020 MC-6312'
URL = 'https://github.com/mc6312/wishcalc'


from gtktools import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf, InterpType
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


if __name__ == '__main__':
    print('[debugging %s]' % __file__)
