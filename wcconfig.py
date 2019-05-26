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
    MAXIMIZED = 'maximized'

    class WinPos():
        """Класс для хранения положения и размеров окна."""

        __slots__ = 'x', 'y', 'width', 'height'

        def __init__(self, x=0, y=0, width=0, height=0):
            self.x = x
            self.y = y
            self.width = width
            self.height = height

        def todict(self):
            d = dict()

            for vname in self.__slots__:
                v = getattr(self, vname)
                if v:
                    d[vname] = v

            return d

        def fromdict(self, d):
            for vname in self.__slots__:
                setattr(self, vname, d[vname] if vname in d else 0)

        def __repr__(self):
            # для отладки

            return '%s(x=%s, y=%s, width=%s, height=%s)' % (self.__class__.__name__,
                self.x, self.y, self.width, self.height)

    def __init__(self):
        self.sizepos = self.WinPos()
        self.oldsizepos = self.WinPos()
        self.maximized = False

        self.__lockcnt = 0

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        if self.__lockcnt:
            return

        # реальные размеры и положение - в event неправильные!
        ww, wh = wnd.get_size()
        wx, wy = wnd.get_position()

        # сохраняем старое положение для борьбы с поведением GTK,
        # который вызывает configure-event с "максимизированным"
        # размером перед вызовом window-state-event
        # авось, поможет...
        self.oldsizepos = self.sizepos
        #self.sizepos = self.WinPos(event.x, event.y, event.width, event.height)
        self.sizepos = self.WinPos(wx, wy, ww, wh)

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""

        if self.__lockcnt:
            return

        self.maximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)

        #if self.maximized:
        #    self.sizepos = self.oldsizepos

        #print('wnd_state_event (maximized=%s)' % self.maximized)

    def __lock(self):
        self.__lockcnt += 1

    def __unlock(self):
        if self.__lockcnt > 0:
            self.__lockcnt -= 1

    def set_window_state(self, window):
        """Установка положения/размера окна"""

        self.__lock()

        #print('set_window_state: %s' % self.sizepos)

        if self.sizepos.x is not None:
            window.move(self.sizepos.x, self.sizepos.y)

            # все равно GTK не даст меньше допустимого съёжить
            window.resize(self.sizepos.width, self.sizepos.height)

        if self.maximized:
            window.maximize()

        flush_gtk_events() # грязный хакЪ, дабы окно смогло поменять размер

        self.__unlock()

    def fromdict(self, d):
        self.sizepos.fromdict(d)

        self.maximized = d[self.MAXIMIZED] if self.MAXIMIZED in d else False

    def todict(self):
        d = dict()

        if self.maximized:
            d[self.MAXIMIZED] = self.maximized

        d.update(self.sizepos.todict())

        return d

    def __repr__(self):
        # для отладки

        return '%s(sizepos=%s, oldsizepos=%s, maximized=%s)' % (self.__class__.__name__,
            self.sizepos, self.oldsizepos, self.maximized)


class Config():
    MAINWINDOW = 'mainwindow'
    ITEMEDITORWINDOW = 'itemeditorwindow'
    CFGFN = 'settings.json'
    CFGAPP = 'wishcalc'

    def __init__(self):
        self.mainWindow = WindowState()
        self.itemEditorWindow = WindowState()

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

                if self.ITEMEDITORWINDOW in d:
                    self.itemEditorWindow.fromdict(d[self.ITEMEDITORWINDOW])

    def save(self):
        tmpd = {self.MAINWINDOW:self.mainWindow.todict(),
            self.ITEMEDITORWINDOW:self.itemEditorWindow.todict()}

        with open(self.configPath, 'w+', encoding=JSON_ENCODING) as f:
            json.dump(tmpd, f, ensure_ascii=False, indent='  ')

    def __repr__(self):
        # для отладки

        return '%s(configDir="%s", configPath="%s", mainWindow=%s, itemEditorWindow=%s)' % (self.__class__.__name__,
            self.configDir, self.configPath, self.mainWindow, self.itemEditorWindow)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    cfg = Config()
    cfg.load()
    #cfg.save()

    print(cfg)
