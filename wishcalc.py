#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""wishcalc.py

    Copyright 2017, 2018, 2019 MC-6312 <mc6312@gmail.com>

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
from wccommon import *
from wcitemed import *


class MainWnd():
    PERCENT_RANGE = 4

    CLIPBOARD_DATA = 'wishcalc2_clipboard_data'

    def destroy(self, widget, data=None):
        if self.wishCalc is not None and self:
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
        self.wishCalc = None

        #
        # основное окно
        #
        self.window = uibldr.get_object('wndMain')

        self.headerbar = uibldr.get_object('headerbar')

        icon = resldr.load_pixbuf_icon_size('wishcalc.svg', Gtk.IconSize.DIALOG, 'calc')
        self.window.set_icon(icon)

        #
        # список желаемого
        #

        # иконки
        nmiconsizeix = Gtk.IconSize.MENU
        nmiconsize = Gtk.IconSize.lookup(nmiconsizeix)[1]

        self.iconNMok = resldr.load_pixbuf('nmiconok.svg', nmiconsize, nmiconsize)
        self.iconNMempty = resldr.load_pixbuf('nmiconempty.svg', nmiconsize, nmiconsize)

        self.iconNMunk = resldr.load_pixbuf('nmiconunk.svg', nmiconsize, nmiconsize)
        self.iconNM6m = resldr.load_pixbuf('nmicon6m.svg', nmiconsize, nmiconsize)
        self.iconNM12m = resldr.load_pixbuf('nmicon12m.svg', nmiconsize, nmiconsize)
        self.iconNM18m = resldr.load_pixbuf('nmicon18m.svg', nmiconsize, nmiconsize)
        self.iconNM36m = resldr.load_pixbuf('nmicon36m.svg', nmiconsize, nmiconsize)

        self.iconPercent = list(map(lambda i: resldr.load_pixbuf('nmicon_p%d.svg' % i, nmiconsize, nmiconsize), range(self.PERCENT_RANGE)))

        self.importanceIcons = ImportanceIcons(nmiconsizeix)

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
        self.itemEditor = ItemEditorDlg(self.window, resldr,
            self.cfg.itemEditorWindow, self.importanceIcons)

        # меню "товарных" команд - для вызова контекстного меню на списке товаров
        self.mnuItem = uibldr.get_object('mnuItem').get_submenu()

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
        self.widgetsItemCopyPaste = get_ui_widgets(uibldr,
            ('mnuItemCopy', 'btnItemCopy'))
            # эти - всегда будут доступны, т.к. возможна вставка при невыбранном элементе
            #, 'mnuItemPaste', 'btnItemPaste'))

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
        #print('loaded:', self.cfg.mainWindow)
        self.load_window_state()
        self.itemEditor.load_window_state()
        #print('load_window_state called:', self.cfg.mainWindow)

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)


        uibldr.connect_signals(self)

        #
        # первоначальное заполнение списка
        #
        if not self.load_wishlist(wlfname):
            exit(1)

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

    def wishlist_pop_up_menu(self, event):
        """Открытие всплывающего меню на списке товаров."""

        # костылинг особенностей поведения GTK под разными бэкендами (X11/Wayland/...)
        # см. документацию по обработке Gtk.Menu.popup()

        if event is None:
            etime = Gtk.get_current_event_time ()
        else:
            etime = event.time

        self.mnuItem.popup(None, None, None, None, 3, etime)

    def on_wishlistview_button_press_event(self, widget, event):
        if event.button == 3:
            # сначала принудительно выбираем элемент дерева, на котором торчит указатель мыша

            ep = self.wishlistview.get_path_at_pos(event.x, event.y)
            if ep is not None:
                self.wishlistviewsel.select_path(ep[0])

            # и таки открываем менюху
            self.wishlist_pop_up_menu(event)
            return True

    def on_wishlistview_popup_menu(self, widget):
        self.wishlist_pop_up_menu(None)

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

            if self.load_wishlist(fname):
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

        set_widgets_sensitive(self.widgetsItemCopyPaste, bsens)
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
            """Обновление полей элементов TreeStore на основе соответствующих
            значений полей экземпляров WishCalc.Item.

            Возвращает кортеж из двух элементов:
            1. экземпляр Gtk.TreeIter, указывающий на элемент дерева,
               который должен стать активным после обновления всего дерева;
            2. целое число - значение поля WishCalc.Item.importance,
               максимальное для "вложенных" ветвей."""

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
                        needsicon = self.iconPercent[int((item.availCash / float(item.sum)) * self.PERCENT_RANGE)]
                    else:
                        needs = str(item.needTotal) if item.needTotal else ''
                        needsicon = self.iconNMempty

                itemname = markup_escape_text(item.name)

                nchildren = self.wishlist.iter_n_children(itr)
                if nchildren > 1:
                    itemname = '%s (%d шт.)' % (itemname, nchildren)

                infobuf = ['<b>%s</b>' % itemname]
                infomonths = ''

                if item.needMonths == 0:
                    needmonths = '-'
                elif item.needMonths is None:
                    needmonths = '-'
                else:
                    needmonths = str(item.needMonths)

                    if item.needMonths > 36:
                        infomonths = 'трёх лет.\nС твоими мозгами что-то не так, сильно не так!'
                        needsicon = self.iconNM36m
                    elif item.needMonths > 18:
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
                    infomonthtxt = '<b>На накопление %sнужно более %s</b>' %\
                        ('' if not item.needTotal else '%d бабла ' % item.needTotal,
                        infomonths)
                elif item.sum <= 0:
                    infomonthtxt = '<b>Ценник не указан. Время накопления - неизвестно...</b>'
                else:
                    infomonthtxt = ''

                if infomonthtxt:
                    infobuf += ['', infomonthtxt]

                importance = item.importance
                if importance == 0:
                    importance = item.childImportance

                self.wishlist.set(itr,
                    (WishCalc.COL_NAME,
                        WishCalc.COL_COST,
                        WishCalc.COL_NEEDED, WishCalc.COL_NEED_ICON,
                        WishCalc.COL_NEED_MONTHS, WishCalc.COL_INFO,
                        WishCalc.COL_QUANTITY, WishCalc.COL_SUM,
                        WishCalc.COL_IMPORTANCE),
                    (item.name,
                        str(item.cost) if item.cost else '?',
                        needs,
                        needsicon,
                        needmonths,
                        '\n'.join(infobuf),
                        str(item.quantity),
                        str(item.sum) if item.cost else '?',
                        self.importanceIcons.icons[importance]
                        ))

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

    def item_copy(self, btn):
        itrsel = self.get_selected_item_iter()

        if itrsel is None:
            return

        # кладём выбранный элемент с подэлементами в clipboard в виде JSON
        # пока вот так, ручками и костыльно

        itemdict = self.wishCalc.get_item(itrsel).get_fields_dict()

        subitems = self.wishCalc.items_to_list(itrsel)
        if subitems:
            itemdict[WishCalc.Item.ITEMS] = subitems

        self.clipboard.set_text(json.dumps({self.CLIPBOARD_DATA:itemdict},
            ensure_ascii=False, indent='  '),
            -1)

    def item_paste(self, btn):
        def __paste_item():
            tmps = self.clipboard.wait_for_text()
            if tmps is None:
                # нету там нифига - молча ничего не делаем
                return

            try:
                tmpd = json.loads(tmps)
            except json.JSONDecodeError:
                # поломатый JSON - опять молча ничего не делаем
                return
                #return 'неподдерживаемый формат содержимого буфера обмена'

            if self.CLIPBOARD_DATA not in tmpd:
                # не наши данные - тоже молча ничего не делаем
                return
                #return 'буфер обмена не содержит данных, поддерживаемых %s' % TITLE

            itemdict = tmpd[self.CLIPBOARD_DATA]

            # таки пытаемся уже чего-то вставить
            item = WishCalc.Item()
            try:
                item.set_fields_dict(itemdict)

                itrsel = self.get_selected_item_iter()
                if itrsel is None:
                    # ничего не выбрано - вставляем элемент в конец списка
                    parent = None
                else:
                    # иначе - после выбранного элемента на его уровне
                    parent = self.wishlist.iter_parent(itrsel)

                inserteditr = self.wishCalc.store.insert_after(parent, itrsel,
                    self.wishCalc.make_store_row(item))

                # рекурсивно добавляем подэлементы, если они есть
                if WishCalc.Item.ITEMS in itemdict:
                    self.wishCalc.load_subitems(inserteditr,
                        itemdict[WishCalc.Item.ITEMS], [])

            except Exception as ex:
                # пока - так
                return str(ex)

            self.refresh_wishlistview(item)

        es = __paste_item()

        if es:
            msg_dialog(self.window, 'Вставка из буфера обмена',
                'Ошибка: %s' % es)

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
                #print(itr, moveref)
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
