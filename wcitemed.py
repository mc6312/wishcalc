#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" wcitemed.py

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

import webbrowser

from wccommon import *
from wcdata import *


class ItemEditorDlg():
    """Обвязка диалогового окна редактора товара.

    Ибо как-то некрасиво в одной куче держать обработчики событий
    основного окна и прочие"""

    def __init__(self, parentwnd, resldr, cfgWinState, colorLabels):
        """parentwnd    - родительское окно,
        resldr          - экземпляр *ResourceLoader,
        cfgWinState     - экземпляр класса для сохранения состояния окна,
        colorLabels     - экземпляр класса ColorLabelIcons."""

        self.windowState = cfgWinState

        uibldr = resldr.load_gtk_builder('wishcalc_itemeditor.ui')

        self.dlgItemEditor = uibldr.get_object('dlgItemEditor')
        self.dlgItemEditor.set_transient_for(parentwnd)
        self.dlgItemEditor.set_skip_pager_hint(True)
        self.dlgItemEditor.set_skip_taskbar_hint(True)

        self.itemnameentry = uibldr.get_object('itemnameentry')

        self.costlabel, self.costentry, self.quantitylabel = get_ui_widgets(uibldr,
            ('costlabel', 'itemcostentry', 'quantitylabel'))

        self.itemcostentry = uibldr.get_object('itemcostentry')
        self.itemquantityentry = uibldr.get_object('itemquantityentry')

        self.itemincartchk = uibldr.get_object('itemincartchk')
        self.itempaidchk = uibldr.get_object('itempaidchk')

        self.itemimportancecbox = uibldr.get_object('itemimportancecbox')
        itemimportancelstore = uibldr.get_object('itemimportancelstore')

        for icon in colorLabels.icons:
            itemimportancelstore.append((icon,))

        self.iteminfoentry = uibldr.get_object('iteminfoentry')
        self.iteminfoentrybuf = self.iteminfoentry.get_buffer()

        self.itemurlentry = uibldr.get_object('itemurlentry')
        self.btnEdItemOpenURL = uibldr.get_object('btnEdItemOpenURL')

        self.btnItemSave = uibldr.get_object('btnItemSave')

        # буфер - присваивается из метода edit()
        self.tempItem = WishCalc.Item()

        self.blocksSave = set() # список виджетов, блокирующих btnItemSave

        uibldr.connect_signals(self)

    def load_window_state(self):
        self.windowState.set_window_state(self.dlgItemEditor)

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        self.windowState.wnd_configure_event(wnd, event)

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""

        self.windowState.wnd_state_event(widget, event)

    E_NOVAL = 'Не указано значение'
    E_BADVAL = 'Неправильное значение'

    def block_save_button(self, widget, isblocks):
        if isblocks:
            self.blocksSave.add(widget)
        elif widget in self.blocksSave:
            self.blocksSave.remove(widget)

        self.btnItemSave.set_sensitive(len(self.blocksSave) == 0)

    def ied_show_entry_error(self, entry, emsg=None):
        show_entry_error(entry, emsg)
        self.block_save_button(entry, emsg)

    def itemnameentry_changed(self, entry):
        self.tempItem.name = normalize_str(entry.get_text())

        self.ied_show_entry_error(entry,
            None if self.tempItem.name else self.E_NOVAL)

    def itemcostentry_changed(self, entry):
        self.tempItem.cost = str_to_int_range(entry.get_text())

        self.ied_show_entry_error(entry,
            None if self.tempItem.cost is not None else self.E_BADVAL)

    def itemquantityentry_value_changed(self, sbtn):
        self.tempItem.quantity = int(sbtn.get_value())

    def itemimportancecbox_changed(self, cbox):
        self.tempItem.importance = cbox.get_active()

    def itemurlentry_changed(self, entry):
        self.tempItem.url = normalize_str(entry.get_text())

        # проверяем только на непустое значение ради сраной кнопки
        # проверку правильности формата URL оставим браузеру, и ниибёт
        self.btnEdItemOpenURL.set_sensitive(self.tempItem.url != '')

    def set_paid_chk_sensitive(self):
        self.itempaidchk.set_sensitive(self.tempItem.incart)

    def itemincartchk_toggled(self, chkbox):
        self.tempItem.incart = chkbox.get_active()

        if not self.tempItem.incart:
            self.tempItem.paid = False
            self.itempaidchk.set_active(False)

        self.set_paid_chk_sensitive()

    def itempaidchk_toggled(self, chkbox):
        self.tempItem.paid = chkbox.get_active()

    def on_btnEdItemOpenURL_clicked(self, btn):
        webbrowser.open_new_tab(self.tempItem.url)

    def edit(self, item, hasChildren):
        """Редактирование товара.

        item        - экземпляр WishCalc.Item или None.
                      В последнем случае создаётся новый экземпляр
                      описания товара;
        hasChildren - булевское значение, True, если есть дочерние элементы.

        Возвращает None, если редактирование отменено (нажата кнопка
        "Отмена"), или экземпляр WishCalc.Item с новыми или изменёнными
        данными."""

        if item is None:
            dtitle = 'Новый товар'
            self.tempItem = WishCalc.Item()
        else:
            dtitle = 'Изменение товара'
            self.tempItem = item.new_copy()

        self.dlgItemEditor.set_title(dtitle)

        self.itemnameentry.set_text(self.tempItem.name)

        self.itemcostentry.set_text(str(self.tempItem.cost) if not hasChildren else '')

        self.itemquantityentry.set_value(self.tempItem.quantity)

        self.itemimportancecbox.set_active(self.tempItem.importance)

        # для групп товаров цена считается при вызове recalculate(),
        # и виджет должен быть скрыт;
        # но количество можно указывать

        self.costentry.set_sensitive(not hasChildren)
        self.costentry.set_visible(not hasChildren)

        self.itemincartchk.set_active(self.tempItem.incart)
        self.itempaidchk.set_active(False if not self.tempItem.incart else self.tempItem.paid)
        self.set_paid_chk_sensitive()

        self.quantitylabel.set_visible(not hasChildren)

        self.costlabel.set_text('Количество:' if hasChildren else 'Цена:')

        #self.costbox.set_sensitive(not hasChildren)

        self.iteminfoentrybuf.set_text(self.tempItem.info)
        self.itemurlentry.set_text(self.tempItem.url)

        self.blocksSave.clear()
        # пинаем обработчики, чтоб при пустых полях иконки высветились и т.п.
        for entry in (self.itemnameentry, self.itemcostentry, self.itemurlentry):
            entry.emit('changed')

        self.itemnameentry.grab_focus()

        self.dlgItemEditor.show()
        try:
            while True:
                # гоняем диалог, пока не получим правильные данные
                # или пока не нажмут кнопку "Отмена"

                r = self.dlgItemEditor.run()

                if r != Gtk.ResponseType.OK:
                    # нажата кнопка "Отмена" или диалог просто закрыт
                    return None

                #
                # вообще, кнопка "сохранить" блокируется, если в важных
                # полях фигня, потому проверки ниже торчат только на
                # случай подстраховки от моего склероза
                #

                # поле изменяется из обработчика itemnameentry_changed()
                if not self.tempItem.name:
                    continue

                # поле изменяется из обработчика itemcostentry_changed()
                if self.tempItem.cost is None:
                    continue

                # поле изменяется из обработчика itemquantityentry_changed()
                if self.tempItem.quantity is None:
                    continue

                # в этом поле может быть произвольный текст, его проверять не нужно -
                # забираем прямо так
                self.tempItem.info = normalize_text(self.iteminfoentrybuf.get_text(self.iteminfoentrybuf.get_start_iter(),
                    self.iteminfoentrybuf.get_end_iter(), False))

                # itemurlentry_changed() проверяет только на непустое значение,
                # чтоб кнопку перехода на сайт (раз)блокировать,
                # соответственно, поле item.url тут не проверяем и не трогаем

                self.tempItem.calculate_sum()
                return WishCalc.Item.new_copy(self.tempItem)

        finally:
            self.dlgItemEditor.hide()


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    from wcconfig import *

    cfg = Config()
    importanceIcons = ImportanceIcons(Gtk.IconSize.MENU)
    resldr = get_resource_loader()
    itemEditor = ItemEditorDlg(None,
        resldr,
        cfg.itemEditorWindow,
        importanceIcons)
    itemEditor.edit(None, False)
    print(itemEditor.tempItem)
