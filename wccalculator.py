#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" wccalculator.py

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


from gtktools import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf


class Calculator():
    CALC_ICON_NAME = 'accessories-calculator'
    ERROR_ICON_POS = Gtk.EntryIconPosition.SECONDARY
    ERROR_ICON_NAME = 'dialog-error'

    def __init__(self, resldr, entry, primaryicon):
        uibldr = resldr.load_gtk_builder('wishcalc_calculator.ui')

        self.popover = uibldr.get_object('popoverCalculator')

        self.calcentry = uibldr.get_object('calcentry')
        self.calcentry.connect('key-release-event', self.calcentry_key_release_event)

        self.popover.set_default_widget(self.calcentry)

        self.entry = entry
        self.entryiconpos = Gtk.EntryIconPosition.PRIMARY if primaryicon else Gtk.EntryIconPosition.SECONDARY
        self.entry.set_icon_from_icon_name(self.entryiconpos, self.CALC_ICON_NAME)
        self.entry.set_icon_sensitive(self.entryiconpos, True)
        self.entry.set_icon_activatable(self.entryiconpos, True)

        self.entry.connect('icon-release', self.entry_icon_release)
        self.entry.connect('key-release-event', self.entry_key_release_event)

        uibldr.connect_signals(self)

    def __check_expression(self, expr):
        # кривой костыль для борьбы с дырами безопасности в eval()

        for c in expr:
            if c not in '0123456789.+-*/()':
                return False

        return True

    def show_error(self, iserror):
        self.calcentry.set_icon_from_icon_name(self.ERROR_ICON_POS, self.ERROR_ICON_NAME if iserror else None)
        self.calcentry.set_icon_sensitive(self.ERROR_ICON_POS, iserror)

    def calculate(self):
        expr = self.calcentry.get_text().strip()

        if expr:
            if not self.__check_expression(expr):
                self.show_error(True)
            else:
                try:
                    r = int(round(eval(expr)))

                    self.entry.set_text(str(r))
                    self.popover.hide()
                    self.entry.grab_focus()
                except Exception as ex:
                    self.show_error(True)

    def computebtn_clicked(self, btn):
        self.calculate()

    def calcentry_key_release_event(self, widget, event):
        if event.keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter}:
            self.calculate()
            return True

        return False

    def entry_icon_release(self, entry, pos, event):
        if pos == self.entryiconpos:
            self.run()

    def entry_key_release_event(self, widget, event):
        if event.keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter} and event.state & Gdk.ModifierType.CONTROL_MASK:
            self.run()
            return True

        return False

    def run(self):
        self.calcentry.set_text(self.entry.get_text())
        self.show_error(False)

        self.popover.set_relative_to(self.entry)
        self.popover.show()
        self.calcentry.grab_focus()


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    def wnd_destroy(widget):
        Gtk.main_quit()

    def run_calc(button):
        calc.run(entry)

    resldr = get_resource_loader()

    window = Gtk.Window(title='Тест %s' % Calculator.__name__)
    window.connect('destroy', wnd_destroy)

    window.set_border_width(120)

    box = Gtk.HBox(spacing=WIDGET_SPACING)
    window.add(box)

    entry = Gtk.Entry()
    entry.set_text('666')
    box.pack_start(entry, False, False, 0)

    button = Gtk.Button.new_with_label('Calc')
    button.connect('clicked', run_calc)
    box.pack_end(button, False, False, 0)

    calc = Calculator(resldr, entry, True)

    window.show_all()
    Gtk.main()
