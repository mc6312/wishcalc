#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""wishcalc.py

    Copyright 2017, 2018 MC-6312 <mc6312@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>."""


from gtktools import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.GLib import markup_escape_text

import webbrowser
import os.path
import sys

from warnings import warn

from wcdata import *
from wcconfig import *


TITLE = 'WishCalc'
SUB_TITLE = 'Калькулятор загребущего нищеброда'

VERSION = '2.1.1'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)
COPYRIGHT = '(c) 2017-2019 MC-6312'
URL = 'https://github.com/mc6312/wishcalc'


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


class ItemEditorDlg():
    """Обвязка диалогового окна редактора товара.

    Ибо как-то некрасиво в одной куче держать обработчики событий
    основного окна и прочие"""

    def __init__(self, parentwnd, resldr):
        """parentwnd    - родительское окно,
        resldr          - экземпляр *ResourceLoader"""

        uibldr = resldr.load_gtk_builder('wishcalc_itemeditor.ui')

        self.dlgItemEditor = uibldr.get_object('dlgItemEditor')
        self.dlgItemEditor.set_transient_for(parentwnd)

        self.itemnameentry = uibldr.get_object('itemnameentry')
        self.itemcostentry = uibldr.get_object('itemcostentry')
        self.iteminfoentry = uibldr.get_object('iteminfoentry')
        self.iteminfoentrybuf = self.iteminfoentry.get_buffer()
        self.itemurlentry = uibldr.get_object('itemurlentry')
        self.btnEdItemOpenURL = uibldr.get_object('btnEdItemOpenURL')
        self.btnItemSave = uibldr.get_object('btnItemSave')

        # буфер - присваивается из метода edit()
        self.tempItem = WishCalc.Item()

        self.blocksSave = set() # список виджетов, блокирующих btnItemSave

        uibldr.connect_signals(self)

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
        self.tempItem.name = normalize_str(self.itemnameentry.get_text())

        self.ied_show_entry_error(self.itemnameentry,
            None if self.tempItem.name else self.E_NOVAL)

    def itemcostentry_changed(self, entry):
        self.tempItem.cost = cost_str_to_int(self.itemcostentry.get_text())

        self.ied_show_entry_error(self.itemcostentry,
            None if self.tempItem.cost is not None else self.E_BADVAL)

    def itemurlentry_changed(self, entry):
        self.tempItem.url = normalize_str(self.itemurlentry.get_text())

        # проверяем только на непустое значение ради сраной кнопки
        # проверку правильности формата URL оставим браузеру, и ниибёт
        self.btnEdItemOpenURL.set_sensitive(self.tempItem.url != '')

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

        self.itemcostentry.set_text(str(self.tempItem.cost))
        # для групп товаров цена считается при вызове recalculate()!
        self.itemcostentry.set_sensitive(not hasChildren)

        self.iteminfoentrybuf.set_text(self.tempItem.info)
        self.itemurlentry.set_text(self.tempItem.url)

        self.blocksSave.clear()
        # пинаем обработчики, чтоб при пустых полях иконки высветились и т.п.
        for entry in (self.itemnameentry, self.itemcostentry, self.itemurlentry):
            entry.emit('changed')

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

                # в этом поле может быть произвольный текст, его проверять не нужно -
                # забираем прямо так
                self.tempItem.info = normalize_text(self.iteminfoentrybuf.get_text(self.iteminfoentrybuf.get_start_iter(),
                    self.iteminfoentrybuf.get_end_iter(), False))

                # itemurlentry_changed() проверяет только на непустое значение,
                # чтоб кнопку перехода на сайт (раз)блокировать,
                # соответственно, поле item.url тут не проверяем и не трогаем

                return WishCalc.Item.new_copy(self.tempItem)

        finally:
            self.dlgItemEditor.hide()


class MainWnd():
    WishCalc.COL_ITEMINDEX, WishCalc.COL_NAME, WishCalc.COL_COST, WishCalc.COL_COST_ERROR, WishCalc.COL_NEEDED, \
    WishCalc.COL_NEEDICON, WishCalc.COL_NEEDMONTHS, WishCalc.COL_INFO = range(8)

    PERCENT_RANGE = 4

    def destroy(self, widget, data=None):
        self.save_wishlist()
        self.cfg.save()
        Gtk.main_quit()

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        self.cfg.mainWindow.wnd_configure_event(wnd, event)

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""

        self.cfg.mainWindow.wnd_state_event(widget, event)

    def load_window_state(self):
        """Загрузка и установка размера и положения окна"""

        self.cfg.mainWindow.set_window_state(self.window)

    def __init__(self, wlfname):
        #
        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'wishcalc.ui')

        self.windowStateLoaded = False
        self.cfg = Config()

        #
        # основное окно
        #
        self.window = uibldr.get_object('wndMain')
        self.window.connect('destroy', self.destroy)

        self.headerbar = uibldr.get_object('headerbar')

        icon = resldr.load_pixbuf_icon_size('wishcalc.svg', Gtk.IconSize.DIALOG, 'calc')
        self.window.set_icon(icon)

        #
        # список желаемого
        #

        nmiconsizeix = Gtk.IconSize.MENU
        nmiconsize = Gtk.IconSize.lookup(nmiconsizeix)[1]

        self.iconNMok = resldr.load_pixbuf('nmiconok.svg', nmiconsize, nmiconsize)
        self.iconNMempty = resldr.load_pixbuf('nmiconempty.svg', nmiconsize, nmiconsize)

        self.iconNMunk = resldr.load_pixbuf('nmiconunk.svg', nmiconsize, nmiconsize)
        self.iconNM6m = resldr.load_pixbuf('nmicon6m.svg', nmiconsize, nmiconsize)
        self.iconNM12m = resldr.load_pixbuf('nmicon12m.svg', nmiconsize, nmiconsize)
        self.iconNM18m = resldr.load_pixbuf('nmicon18m.svg', nmiconsize, nmiconsize)

        self.iconPercent = list(map(lambda i: resldr.load_pixbuf('nmicon_p%d.svg' % i, nmiconsize, nmiconsize), range(self.PERCENT_RANGE)))

        # TreeStore используется как хранилище данных во время работы
        # в первом столбце (WishCalc.COL_ITEM_OBJ) хранится ссылка
        # на экземпляр WishCalc.Item (см. wcdata.py)
        #self.wishlist = uibldr.get_object('wishlist')
        # внимание! это поле будет присвоено в конце конструктора при загрузке файла!

        self.wishlistview = uibldr.get_object('wishlistview')
        self.wishlistview.set_tooltip_column(WishCalc.COL_INFO)

        self.wishlistviewsel = uibldr.get_object('wishlistviewsel')

        #
        # наличность и остаток
        #
        self.cashentry = uibldr.get_object('cashentry')
        self.refillentry = uibldr.get_object('refillentry')
        self.remainsentry = uibldr.get_object('remainsentry')

        #
        # редактор товара
        #
        self.itemEditor = ItemEditorDlg(self.window, resldr)

        #
        # виджеты, свойство "sensitive" которых зависит от состояния списка
        #
        # вот это вот (и соотв. setup_widgets_sensitive()) возможно
        # придётся переделывать через actions
        self.widgetsItemEditing = get_ui_widgets(uibldr,
            ('mnuItemEdit', 'btnItemEdit', 'mnuItemPurchased', 'btnItemPurchased',
             'mnuItemAddSubItem', 'btnItemAddSubItem',
             'mnuItemOpenURL', 'btnItemOpenURL', 'mnuItemRemove', 'btnItemRemove'))
        self.widgetsItemMoveUp = get_ui_widgets(uibldr,
            ('mnuItemMoveUp', 'btnItemMoveUp',
             'mnuItemMoveToTop', 'btnItemMoveToTop'))
        self.widgetsItemMoveDown = get_ui_widgets(uibldr,
            ('mnuItemMoveDown', 'btnItemMoveDown',
             'mnuItemMoveToBottom', 'btnItemMoveToBottom'))
        self.widgetsItemOpenURL = get_ui_widgets(uibldr,
            ('mnuItemOpenURL', 'btnItemOpenURL'))

        # а вот оно будет рулиться НЕ из setup_widgets_sensitive()!
        self.widgetsRefillCash = get_ui_widgets(uibldr,
            ('mnuRefillCash', 'btnRefillCash'))

        #
        #
        #
        self.popoverFileCommentEditor = uibldr.get_object('popoverFileCommentEditor')
        self.filecommententry = uibldr.get_object('filecommententry')

        # потому что чортово Glade ентого не умеет, падло...
        self.popoverFileCommentEditor.set_default_widget(uibldr.get_object('btnFCEntryDone'))

        #
        # ыбаутбокс
        #
        self.dlgAbout = uibldr.get_object('dlgAbout')
        self.dlgAbout.set_logo(resldr.load_pixbuf('wishcalc_logo.svg', 128, 128))
        self.dlgAbout.set_program_name(TITLE)
        self.dlgAbout.set_comments(SUB_TITLE)
        self.dlgAbout.set_version('v%s' % VERSION)
        self.dlgAbout.set_copyright(COPYRIGHT)
        self.dlgAbout.set_website(URL)
        self.dlgAbout.set_website_label(URL)

        #
        # диалог открытия файла
        #
        self.dlgFileOpen = uibldr.get_object('dlgFileOpen')

        #
        # диалог сохранения файла
        #
        self.dlgFileSaveAs = uibldr.get_object('dlgFileSaveAs')

        #
        # !!!
        #
        self.window.show_all()

        self.cfg.load()
        self.load_window_state()

        uibldr.connect_signals(self)

        #
        # первоначальное заполнение списка
        #
        self.load_wishlist(wlfname)

        self.wishlist_is_loaded()

        self.setup_widgets_sensitive()

    def about_program(self, widget):
        self.dlgAbout.show()
        self.dlgAbout.run()
        self.dlgAbout.hide()

    def refresh_window_title(self):
        self.headerbar.set_title('%s: %s' % (TITLE_VERSION,
            os.path.splitext(os.path.split(self.wishCalc.filename)[1])[0]))

        self.headerbar.set_subtitle(SUB_TITLE if not self.wishCalc.comment else self.wishCalc.comment)

    def on_wishlistview_drag_end(self, wgt, ctx):
        self.refresh_wishlistview()

    def wishlist_is_loaded(self):
        """Этот метод должен вызываться после успешной загрузки
        файла (т.е. если load_wishlist() не рухнул с исключением)."""

        self.wishlist = self.wishCalc.store

        # обязательно заменяем TreeStore загруженной!
        self.wishlistview.set_model(self.wishlist)
        #...и надеемся, что предыдущий экземпляр будет укоцан потрохами PyGObject и питоньей сборкой мусора...

        self.refresh_wishlistview()

        self.refresh_totalcash_view()
        self.refillentry.set_text(str(self.wishCalc.refillCash))
        self.refresh_remains_view()

        self.refresh_window_title()

    def file_save(self, mnu):
        self.save_wishlist()

    def file_save_as(self, mnu):
        self.dlgFileSaveAs.select_filename(self.wishCalc.filename)
        r = self.dlgFileSaveAs.run()
        self.dlgFileSaveAs.hide()

        if r == Gtk.ResponseType.OK:
            self.wishCalc.filename = self.dlgFileSaveAs.get_filename()
            if self.save_wishlist():
                self.refresh_window_title()

    def file_open(self, mnu):
        self.dlgFileOpen.select_filename(self.wishCalc.filename)
        r = self.dlgFileOpen.run()
        self.dlgFileOpen.hide()

        if r == Gtk.ResponseType.OK:
            fname = self.dlgFileOpen.get_filename()
            if os.path.samefile(fname, self.wishCalc.filename):
                return

            if self.wishlist.iter_n_children(None) > 0:
                self.save_wishlist()

            if load_wishlist(self.window, fname):
                self.wishlist_is_loaded()

    def file_edit_comment(self, mnu):
        self.filecommententry.set_text(self.wishCalc.comment)
        self.popoverFileCommentEditor.show()

    def filecommententry_changed(self, entry):
        self.wishCalc.comment = normalize_text(entry.get_text())

    def filecommententry_editing_done(self, btn):
        self.refresh_window_title()
        self.popoverFileCommentEditor.hide()

    def setup_widgets_sensitive(self):
        itr = self.get_selected_item_iter()

        if itr is None:
            bsens = False
            bcanmoveup = False
            bcanmovedown = False
            bcanopenurl = False
        else:
            ix = self.wishlist.get_path(itr).get_indices()[-1]
            lastix = self.wishlist.iter_n_children(self.wishlist.iter_parent(itr)) - 1

            bsens = True

            bcanmoveup = ix > 0
            bcanmovedown = ix < lastix

            bcanopenurl = self.wishCalc.get_item(itr).url != ''

        set_widgets_sensitive(self.widgetsItemEditing, bsens)
        set_widgets_sensitive(self.widgetsItemMoveUp, bsens & bcanmoveup)
        set_widgets_sensitive(self.widgetsItemMoveDown, bsens & bcanmovedown)
        set_widgets_sensitive(self.widgetsItemOpenURL, bsens & bcanopenurl)

    def wishlistviewsel_changed(self, selection):
        self.setup_widgets_sensitive()

    def refresh_totalcash_view(self):
        self.cashentry.set_text(str(self.wishCalc.totalCash))

    def refresh_wishlistview(self, selitem=None):
        """Перерасчёт списка товаров, обновление содержимого TreeView.

        selitem - None или экземпляр WishCalc.Item, в последнем случае
                  после обновления TreeView в нём должен быть подсвечен
                  элемент дерева, содержащий соотв. Item."""

        self.wishCalc.recalculate()

        # получается, что проходим по TreeStore второй раз (после recalculate)
        # ну да и хрен с ним пока...

        def __refresh_node(parentitr):
            itr = self.wishlist.iter_children(parentitr)

            __itersel = None

            while itr is not None:
                item = self.wishlist.get_value(itr, WishCalc.COL_ITEM_OBJ)

                if item is selitem:
                    __itersel = itr

                if item.needCash == 0:
                    needs = 'хватает'
                    needsicon = self.iconNMok
                elif item.needCash is None:
                    needs = '?'
                    needsicon = self.iconNMunk
                else:
                    if item.availCash > 0:
                        needs = str(item.needCash)
                        needsicon = self.iconPercent[int((item.availCash / float(item.cost)) * self.PERCENT_RANGE)]
                    else:
                        needs = str(item.needTotal) if item.needTotal else ''
                        needsicon = self.iconNMempty

                infobuf = ['<b>%s</b>' % markup_escape_text(item.name)]
                infomonths = ''

                if item.needMonths == 0:
                    needmonths = '-'
                elif item.needMonths is None:
                    needmonths = '-'
                else:
                    needmonths = str(item.needMonths)

                    if item.needMonths > 18:
                        infomonths = 'полутора лет.\nУ тебя с головой всё в порядке?'
                        needsicon = self.iconNM18m
                    elif item.needMonths > 12:
                        infomonths = 'года.\nМожет, лучше забить?'
                        needsicon = self.iconNM12m
                    elif item.needMonths > 6:
                        infomonths = 'полугода.\nТебе точно это надо?'
                        needsicon = self.iconNM6m

                if item.info:
                    infobuf += ['', markup_escape_text(item.info)]

                if infomonths:
                    infobuf += ['', '<b>На накопление %sнужно более %s</b>' %\
                                ('' if not item.needTotal else '%d бабла ' % item.needTotal,
                                infomonths)]

                self.wishlist.set(itr,
                    (WishCalc.COL_NAME,
                        WishCalc.COL_COST, WishCalc.COL_COST_ERROR,
                        WishCalc.COL_NEEDED, WishCalc.COL_NEED_ICON,
                        WishCalc.COL_NEED_MONTHS, WishCalc.COL_INFO),
                    (item.name,
                        str(item.cost) if item.cost else '?',
                        None,
                        needs,
                        needsicon,
                        needmonths,
                        '\n'.join(infobuf)))

                __subsel = __refresh_node(itr)
                if __subsel is not None:
                    __itersel = __subsel

                itr = self.wishlist.iter_next(itr)

            return __itersel

        itersel = __refresh_node(None)

        # вертаем выбор взад
        if itersel is not None:
            path = self.wishlist.get_path(itersel)
            self.wishlistviewsel.select_path(path)
            self.wishlistview.set_cursor(path, None, False)

        self.setup_widgets_sensitive()

        self.refresh_totalcash_view()
        self.refresh_remains_view()

    def __do_edit_item(self, newitem, newaschild=False):
        """Вызов редактора описания товара.

        newitem     - булевское значение:
                      False, если нужно отредактировать выбранный
                      товар,
                      True, если нужно создать новый товар;
        newaschild   - используется только если newitem==True;
                      булевское значение:
                      False - новый товар добавляется на том же уровне
                      дерева, что и выбранный товар (или на верхнем уровне,
                      если ничего не выбрано);
                      True - новый товар добавляется как дочерний
                      к выбранному."""

        itrsel = self.get_selected_item_iter()

        if newitem:
            item = None
        else:
            if itrsel is None:
                return

            item = self.wishCalc.get_item(itrsel)

        item = self.itemEditor.edit(item,
            False if itrsel is None else self.wishlist.iter_n_children(itrsel) > 0)

        if item is not None:
            if not newitem:
                # заменяем существующий экземпляр изменённым
                self.wishCalc.replace_item(itrsel, item)
            else:
                # добавляем новый
                if newaschild:
                    parent = itrsel
                else:
                    parent = self.wishlist.iter_parent(itrsel) if itrsel is not None else None

                self.wishCalc.append_item(parent, item)

                if parent is not None:
                    # принудительно разворачиваем ветвь, иначе TreeView не изменит selection
                    path = self.wishlist.get_path(parent)
                    self.wishlistview.expand_row(path, False)

            self.refresh_wishlistview(item)

    def wl_row_activated(self, treeview, path, col):
        self.__do_edit_item(False)

    def get_selected_item_iter(self):
        """Возвращает Gtk.TreeIter если в TreeView выбрана строка,
        иначе None."""
        return self.wishlistviewsel.get_selected()[1]

    def item_edit(self, btn):
        self.__do_edit_item(False)

    def item_add(self, btn):
        self.__do_edit_item(True)

    def item_add_subitem(self, btn):
        self.__do_edit_item(True, True)

    def item_open_url(self, btn):
        itr = self.get_selected_item_iter()
        if itr:
            item = self.wishCalc.get_item(itr)
            if item.url:
                webbrowser.open_new_tab(item.url)

    def __delete_item(self, ispurchased):
        """Удаление товара из списка.
        Если ispurchased == True, товар считается купленным, и его цена
        вычитается из суммы доступных наличных."""

        itr = self.get_selected_item_iter()
        if not itr:
            return

        nchildren = self.wishlist.iter_n_children(itr)

        sitem = ('группу товаров (из %d)' % nchildren) if nchildren else 'товар'

        spchsd = '' if not ispurchased\
            else ' купленный' if nchildren == 0\
                else ' купленную'

        item = self.wishCalc.get_item(itr)

        msgwhat = 'Удалить%s %s "%s"?' % (spchsd, sitem, item.name)

        if msg_dialog(self.window, 'Удаление',
            msgwhat,
            buttons=Gtk.ButtonsType.YES_NO) == Gtk.ResponseType.YES:

            self.wishCalc.item_delete(itr, ispurchased)
            self.refresh_wishlistview()

    def item_purchased(self, btn):
        self.__delete_item(True)

    def item_delete(self, btn):
        self.__delete_item(False)

    def __move_selected_item(self, down, onepos):
        """Перемещение выбранного элемента списка товаров.

        down        - направление: вперёд (в конец) или назад (в начало)
        onepos      - если True - перемещает элемент на одну позицию
                      в направлении, указанном параметром down,
                      иначе, соответственно, в конец или в начало."""

        itr = self.get_selected_item_iter()
        if itr is not None:
            movefunc = self.wishlist.move_before if (down ^ onepos) else self.wishlist.move_after

            if onepos:
                moveref = self.wishlist.iter_next(itr) if down else self.wishlist.iter_previous(itr)
                print(itr, moveref)
            else:
                moveref = None

            movefunc(itr, moveref)

            self.refresh_wishlistview()

    def item_up(self, btn):
        self.__move_selected_item(False, True)

    def item_down(self, btn):
        self.__move_selected_item(True, True)

    def item_to_top(self, btn):
        self.__move_selected_item(False, False)

    def item_to_bottom(self, btn):
        self.__move_selected_item(True, False)

    def cost_changed(self, crt, path, text):
        itr = self.wishlist.get_iter(path)

        cost = cost_str_to_int(text)

        if cost is None:
            self.wishlist.set_value(itr, WishCalc.COL_COST, '')
            self.wishlist.set_value(itr, WishCalc.COL_COST_ERROR, self.iconError)
        else:
            item = self.wishCalc.get_item(itr)

            if item.cost != cost:
                item.cost = cost

                text = '?' if cost <= 0 else str(cost)
                # патамушта на входе могло быть вещественное, а мы признаём только целые

                self.wishlist.set_value(itr, WishCalc.COL_COST, text)
                self.wishlist.set_value(itr, WishCalc.COL_COST_ERROR, None)
                self.refresh_wishlistview()

    def get_cash_entry_changes(self, entry, errormsg):
        try:
            cash = int(entry.get_text())
            if cash < 0:
                cash = 0

            show_entry_error(entry)
            return cash

        except ValueError:
            show_entry_error(entry, errormsg)
            return None

    def cashentry_changed(self, entry):
        """Изменение поля доступной суммы"""

        v = self.get_cash_entry_changes(entry, 'Доступная сумма указана неправильно')
        if v is not None:
            self.wishCalc.totalCash = v
            self.refresh_wishlistview()

    def refillentry_changed(self, entry):
        """Изменение поля суммы ежемесячных пополнений"""

        v = self.get_cash_entry_changes(entry, 'Сумма ежемесячных пополнений указана неправильно')
        if v is not None:
            self.wishCalc.refillCash = v
            self.refresh_wishlistview()
            bsens = v > 0
        else:
            bsens = False

        set_widgets_sensitive(self.widgetsRefillCash, bsens)

    def do_refill_cash(self, btn):
        if self.wishCalc.refillCash > 0:
            self.wishCalc.totalCash += self.wishCalc.refillCash
            self.refresh_wishlistview()

    def refresh_remains_view(self):
        self.remainsentry.set_text(str(self.wishCalc.totalRemain) if self.wishCalc.totalRemain > 0 else 'нет')

    def save_wishlist(self):
        """Сохранение списка.
        Возвращает булевское значение (True в случае успеха)."""

        try:
            self.wishCalc.save()
            return True
        except Exception as ex:
            msg_dialog(self.window, TITLE, 'Ошибка сохранения файла "%s":\n%s' % (self.wishCalc.filename, str(ex)))
            return False

    def load_wishlist(self, filename):
        """Загрузка списка.
        Возвращает булевское значение (успех/отказ)."""

        try:
            wishcalc = WishCalc(filename)
            wishcalc.load()

            # если раньше не рухнуло с исключением - можно:
            self.wishCalc = wishcalc

            return True

        except Exception as ex:
            msg_dialog(self.window, TITLE, 'Ошибка загрузки файла "%s":\n%s' % (filename, str(ex)))
            return False

    def main(self):
        Gtk.main()


def main(args):
    if len(args) > 1:
        wlfname = os.path.abspath(args[1])
    else:
        wlfname = os.path.join(os.path.split(sys.argv[0])[0], 'wishlist.json')

    MainWnd(wlfname).main()

    return 0

if __name__ == '__main__':
    exit(main(sys.argv))
