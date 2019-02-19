#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" wcconfig.py

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

from gi.repository import Gtk, Gdk

import xdg.BaseDirectory
import json
import os.path


JSON_ENCODING = 'utf-8'


class WindowState():
    X = 'x'
    Y = 'y'
    WIDTH = 'width'
    HEIGHT = 'height'
    MAXIMIZED = 'maximized'

    def __init__(self):
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.maximized = False

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        if not self.maximized:
            self.x = event.x
            self.y = event.y

            self.width = event.width
            self.height = event.height

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""

        self.maximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)

    def set_window_state(self, window):
        """Установка положения/размера окна"""

        if self.x is not None:
            window.move(self.x, self.y)

            # все равно GTK не даст меньше допустимого съёжить
            window.resize(self.width, self.height)

        if self.maximized:
            window.maximize()

        flush_gtk_events() # грязный хакЪ, дабы окно смогло поменять размер

    def fromdict(self, d):
        def __fromdict(d, vname, fallback=0):
            return d[vname] if vname in d else fallback

        self.x = __fromdict(d, self.X)
        self.y = __fromdict(d, self.Y)
        self.width = __fromdict(d, self.WIDTH)
        self.height = __fromdict(d, self.HEIGHT)
        self.maximized = __fromdict(d, self.MAXIMIZED)

    def todict(self):
        d = dict()

        if self.x:
            d[self.X] = self.x

        if self.Y:
            d[self.Y] = self.y

        if self.width:
            d[self.WIDTH] = self.width

        if self.height:
            d[self.HEIGHT] = self.height

        if self.maximized:
            d[self.MAXIMIZED] = self.maximized

        return d

    def __repr__(self):
        # для отладки

        return '%s(x=%s, y=%s, width=%s, height=%s, maximized=%s)' % (self.__class__.__name__,
            self.x, self.y, self.width, self.height, self.maximized)


class Config():
    MAINWINDOW = 'mainwindow'
    CFGFN = 'settings.json'
    CFGAPP = 'wishcalc'

    def __init__(self):
        self.mainWindow = WindowState()

        # определяем каталог для настроек
        # или принудительно создаём, если его ещё нет
        self.configDir = xdg.BaseDirectory.save_config_path(self.CFGAPP)

        self.configPath = os.path.join(self.configDir, self.CFGFN)
        # вот сейчас самого файла может ещё не быть!

    def load(self):
        if os.path.exists(self.configPath):
            with open(self.configPath, 'r', encoding=JSON_ENCODING) as f:
                d = json.load(f)

                if self.MAINWINDOW in d:
                    self.mainWindow.fromdict(d[self.MAINWINDOW])

    def save(self):
        tmpd = {self.MAINWINDOW:self.mainWindow.todict()}

        with open(self.configPath, 'w+', encoding=JSON_ENCODING) as f:
            json.dump(tmpd, f, ensure_ascii=False, indent='  ')

    def __repr__(self):
        # для отладки

        return '%s(configDir="%s", configPath="%s", mainWindow=%s)' % (self.__class__.__name__,
            self.configDir, self.configPath, self.mainWindow)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    cfg = Config()
    cfg.load()
    cfg.save()

    print(cfg)
