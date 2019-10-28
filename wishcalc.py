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

from random import choice as random_choice

from warnings import warn

from wcdata import *
from wcconfig import *
from wccommon import *
from wcitemed import *


class MainWnd():
    PERCENT_RANGE = 4

    CLIPBOARD_DATA = 'wishcalc2_clipboard_data'

    def destroy(self, widget):
        Gtk.main_quit()

    def before_exit(self):
        if self.wishCalc is not None:
            if self.wishCalc.filename:
                self.save_wishlist()
            elif self.wishCalc.store.iter_n_children(None) > 0:
                self.file_save_as(None)

        self.cfg.save()

    def wndMain_delete_event(self, wnd, event):
        self.before_exit()

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

        icon = resldr.load_pixbuf_icon_size('images/wishcalc.svg', Gtk.IconSize.DIALOG, 'calc')
        self.window.set_icon(icon)

        #
        # список желаемого
        #

        # иконки
        nmiconsizeix = Gtk.IconSize.MENU
        nmiconsize = Gtk.IconSize.lookup(nmiconsizeix)[1]

        self.iconNMok = resldr.load_pixbuf('images/nmiconok.svg', nmiconsize, nmiconsize)
        self.iconNMempty = resldr.load_pixbuf('images/nmiconempty.svg', nmiconsize, nmiconsize)

        self.iconNMincart = resldr.load_pixbuf('images/nmiconincart.svg', nmiconsize, nmiconsize)
        self.iconNMchildrenincart = resldr.load_pixbuf('images/nmiconchildrenincart.svg', nmiconsize, nmiconsize)
        self.iconNMnotincart = resldr.load_pixbuf('images/nmiconnotincart.svg', nmiconsize, nmiconsize)

        self.iconNMunk = resldr.load_pixbuf('images/nmiconunk.svg', nmiconsize, nmiconsize)
        self.iconNM6m = resldr.load_pixbuf('images/nmicon6m.svg', nmiconsize, nmiconsize)
        self.iconNM12m = resldr.load_pixbuf('images/nmicon12m.svg', nmiconsize, nmiconsize)
        self.iconNM18m = resldr.load_pixbuf('images/nmicon18m.svg', nmiconsize, nmiconsize)
        self.iconNM36m = resldr.load_pixbuf('images/nmicon36m.svg', nmiconsize, nmiconsize)

        self.iconPercent = list(map(lambda i: resldr.load_pixbuf('images/nmicon_p%d.svg' % i, nmiconsize, nmiconsize), range(self.PERCENT_RANGE)))

        self.importanceIcons = []
        for iximpicon in range(IMPORTANCE_LEVELS):
            self.importanceIcons.append(resldr.load_pixbuf('images/impicon%.2d.svg' % iximpicon, nmiconsize, nmiconsize))

        # TreeStore используется как хранилище данных во время работы
        # в первом столбце (WishCalc.COL_ITEM_OBJ) хранится ссылка
        # на экземпляр WishCalc.Item (см. wcdata.py)

        self.wishlistview = uibldr.get_object('wishlistview')
        self.wishlistview.set_tooltip_column(WishCalc.COL_INFO)

        self.wishlistviewsel = uibldr.get_object('wishlistviewsel')

        self.wlv_colItemSelect, self.wlv_colItemInCart, self.wlv_colItemImportance = get_ui_widgets(uibldr,
            ('colItemSelect', 'colItemInCart', 'colItemImportance'))

        uibldr.get_object('imgCart').set_from_pixbuf(self.iconNMincart)
        uibldr.get_object('imgImportance').set_from_pixbuf(self.importanceIcons[0])

        #
        # наличность и остаток
        #
        self.cashentry, self.refillentry, self.remainsentry = get_ui_widgets(uibldr,
            ('cashentry', 'refillentry', 'remainsentry'))

        # сумма выбранных в дереве
        self.selectedsumbox, self.selectedcountentry, self.selectedsumentry, self.selectedneedsentry,\
        self.selectedmonthsentry = get_ui_widgets(uibldr,
            ('selectedsumbox', 'selectedcountentry', 'selectedsumentry', 'selectedneedsentry',
            'selectedmonthsentry'))

        # сумма заказанных товаров
        self.incartbox, self.incartcountentry, self.incartsumentry = get_ui_widgets(uibldr,
            ('incartbox', 'incartcountentry', 'incartsumentry'))

        #
        # редактор товара
        #
        self.itemEditor = ItemEditorDlg(self.window, resldr,
            self.cfg.itemEditorWindow, self.importanceIcons)

        # меню "товарных" команд - для вызова контекстного меню на списке товаров
        self.mnuItem = uibldr.get_object('mnuItem').get_submenu()

        # подменю "заказан/оплачен"
        self.mnuItemToggleInCartPaid = uibldr.get_object('mnuItemToggleInCartPaid').get_submenu()

        # подменю "важности" товара
        self.mnuItemImportance = uibldr.get_object('mnuItemImportance')
        self.submnuItemImportance = Gtk.Menu()
        self.submnuItemImportance.set_reserve_toggle_size(False)

        self.mnuItemImportance.set_submenu(self.submnuItemImportance)

        for importance, iicon in enumerate(self.importanceIcons):
            mitem = Gtk.MenuItem.new()
            mitem.add(Gtk.Image.new_from_pixbuf(iicon))
            mitem.connect('activate', self.item_set_importance, importance)

            self.submnuItemImportance.append(mitem)

        # костыль для избавления от лишней дерготни подменю "важности":
        # когда оно уже открыто из меню уровнем выше, тут д.б. значение > 0
        self.mnuItemImportanceVisible = 0

        #
        # виджеты, свойство "sensitive" которых зависит от состояния списка
        #
        # вот это вот (и соотв. setup_widgets_sensitive()) возможно
        # придётся переделывать через actions
        self.widgetsItemEditing = get_ui_widgets(uibldr,
            ('mnuItemEdit', 'btnItemEdit', 'mnuItemPurchased', 'btnItemPurchased',
             'mnuItemAddSubItem', 'btnItemAddSubItem',
             'mnuItemToggleInCart', 'mnuItemTogglePaid', 'mnuItemImportance',
             'mnuItemOpenURL', 'btnItemOpenURL', 'mnuItemRemove', 'btnItemRemove'))
        self.widgetsItemMoveUp = get_ui_widgets(uibldr,
            ('mnuItemMoveUp', 'btnItemMoveUp',
             'mnuItemMoveToTop', 'btnItemMoveToTop'))
        self.widgetsItemMoveDown = get_ui_widgets(uibldr,
            ('mnuItemMoveDown', 'btnItemMoveDown',
             'mnuItemMoveToBottom', 'btnItemMoveToBottom'))
        self.widgetsItemURL = get_ui_widgets(uibldr,
            ('mnuItemOpenURL', 'btnItemOpenURL', 'mnuItemCopyURL'))
        self.widgetsItemCopyPaste = get_ui_widgets(uibldr,
            ('mnuItemCopy', 'btnItemCopy'))
            # эти - всегда будут доступны, т.к. возможна вставка при невыбранном элементе
            #, 'mnuItemPaste', 'btnItemPaste'))

        # а вот оно будет рулиться НЕ из setup_widgets_sensitive()!
        self.widgetsRefillCash = get_ui_widgets(uibldr,
            ('mnuRefillCash', 'btnRefillCash'))

        # выделение галками
        self.widgetsSelectAll = get_ui_widgets(uibldr, ('cbSelectAll', 'mnuItemSelectAll'))
        self.widgetsSelectNone = get_ui_widgets(uibldr, ('mnuItemUnselectAll',))
        self.cbSelectAll = uibldr.get_object('cbSelectAll')

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
        self.dlgAbout.set_logo(resldr.load_pixbuf('images/wishcalc_logo.svg', 128, 128))
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
        if wlfname is not None:
            if not self.load_wishlist(wlfname):
                exit(1)
        else:
            self.wishCalc = WishCalc(None)

        self.wishlist_is_loaded()

        self.setup_widgets_sensitive()

    def about_program(self, widget):
        self.dlgAbout.show()
        self.dlgAbout.run()
        self.dlgAbout.hide()

    def refresh_window_title(self):
        if self.wishCalc.filename:
            dispfname = os.path.splitext(os.path.split(self.wishCalc.filename)[1])[0]
        else:
            dispfname = '<новый файл>'

        self.headerbar.set_title('%s: %s' % (TITLE_VERSION, dispfname))

        self.headerbar.set_subtitle(SUB_TITLE if not self.wishCalc.comment else self.wishCalc.comment)

    def wishlist_pop_up_menu(self, event, menu=None):
        """Открытие всплывающего меню на списке товаров."""

        # костылинг особенностей поведения GTK под разными бэкендами (X11/Wayland/...)
        # см. документацию по обработке Gtk.Menu.popup()

        if event is None:
            etime = Gtk.get_current_event_time ()
        else:
            etime = event.time

        if menu is None:
            menu = self.mnuItem

        menu.popup(None, None, None, None, 3, etime)

    def on_colItemSelect_clicked(self, cbtn):
        self.__item_select_all(not (self.cbSelectAll.get_active() or self.cbSelectAll.get_inconsistent()))

    def wl_button_press_event(self, widget, event):
        # вызов popup menu мышом
        if event.button == 3:
            # сначала принудительно выбираем элемент дерева, на котором торчит указатель мыша

            menu = None

            ep = self.wishlistview.get_path_at_pos(event.x, event.y)
            if ep is not None:
                # если мышь на столбце с иконками - вместо общего контекстного
                # меню вызываем менюху "важности" товара
                col = ep[1]

                if col == self.wlv_colItemImportance:
                    menu = self.submnuItemImportance
                elif col == self.wlv_colItemInCart:
                    menu = self.mnuItemToggleInCartPaid

                self.wishlistviewsel.select_path(ep[0])

            # и таки открываем менюху
            self.wishlist_pop_up_menu(event, menu)

            return True

    def wl_popup_menu(self, widget):
        # вызов popup menu клавиатурой
        self.wishlist_pop_up_menu(None)

    def on_mnuItemImportance_select(self, widget):
        # меню "важности" открывается
        self.mnuItemImportanceVisible += 1

    def on_mnuItemImportance_deselect(self, widget):
        # меню "важности" закрывается
        if self.mnuItemImportanceVisible > 0:
            self.mnuItemImportanceVisible -= 1

    def item_choose_importance(self, btn):
        # обработка сигнала по нажатию Ctrl+I из основного окна
        # НЕ должна срабатывать, если меню submnuItemImportance
        # уже открыто из основного или контекстного меню
        if self.mnuItemImportanceVisible == 0:
            self.wishlist_pop_up_menu(None, self.submnuItemImportance)

    def wl_drag_end(self, wgt, ctx):
        self.refresh_wishlistview()

    def wishlist_is_loaded(self):
        """Этот метод должен вызываться после успешной загрузки
        файла (т.е. если load_wishlist() не рухнул с исключением)."""

        # обязательно заменяем TreeStore загруженной!
        self.wishlistview.set_model(self.wishCalc.store)
        #...и надеемся, что предыдущий экземпляр будет укоцан потрохами PyGObject и питоньей сборкой мусора...

        self.refresh_wishlistview()

        self.refresh_totalcash_view()
        self.refillentry.set_text(str(self.wishCalc.refillCash))
        self.refresh_remains_view()
        self.refresh_selected_sum_view()

        self.refresh_window_title()

    def file_exit(self, widget):
        self.before_exit()
        self.destroy(widget)

    def file_save(self, mnu):
        """Сохранение файла"""

        if self.wishCalc.filename:
            self.save_wishlist()
        else:
            self.file_save_as(mnu)

    def __run_filename_dialog(self, dlg):
        dlg.select_filename(self.wishCalc.filename if self.wishCalc.filename else DEFAULT_FILENAME)
        r = dlg.run()
        dlg.hide()

        return r

    def file_save_as(self, mnu):
        """Сохранение файла с выбором имени"""

        r = self.__run_filename_dialog(self.dlgFileSaveAs)

        if r == Gtk.ResponseType.OK:
            self.wishCalc.filename = self.dlgFileSaveAs.get_filename()
            if self.save_wishlist():
                self.refresh_window_title()

    def file_open(self, mnu):
        r = self.__run_filename_dialog(self.dlgFileOpen)

        if r == Gtk.ResponseType.OK:
            fname = self.dlgFileOpen.get_filename()
            if self.wishCalc.filename and os.path.samefile(fname, self.wishCalc.filename):
                return

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
        hasitems = self.wishCalc.store.iter_n_children(None) > 0

        bsens = False
        bcanmoveup = False
        bcanmovedown = False
        bcanopenurl = False
        bcanselect = False
        bcanunselect = False

        if hasitems:
            if itr is not None:
                ix = self.wishCalc.store.get_path(itr).get_indices()[-1]
                lastix = self.wishCalc.store.iter_n_children(self.wishCalc.store.iter_parent(itr)) - 1

                bsens = True

                bcanmoveup = ix > 0
                bcanmovedown = ix < lastix

                bcanopenurl = self.wishCalc.get_item(itr).url != ''

            bcanselect = True
            bcanunselect = self.wishCalc.totalSelectedCount > 0

        set_widgets_sensitive(self.widgetsItemCopyPaste, bsens)
        set_widgets_sensitive(self.widgetsItemEditing, bsens)
        set_widgets_sensitive(self.widgetsItemMoveUp, bsens & bcanmoveup)
        set_widgets_sensitive(self.widgetsItemMoveDown, bsens & bcanmovedown)
        set_widgets_sensitive(self.widgetsItemURL, bsens & bcanopenurl)

        set_widgets_sensitive(self.widgetsSelectAll, bcanselect)
        set_widgets_sensitive(self.widgetsSelectNone, bcanselect & bcanunselect)

    def wishlistviewsel_changed(self, selection):
        self.setup_widgets_sensitive()

    def refresh_totalcash_view(self):
        self.cashentry.set_text(str(self.wishCalc.totalCash))

    def get_percent_icon(self, avail, total):
        """Возвращает иконку (экземпляр Pixbuf), соответствующий прОценту."""

        if total <= 0:
            return self.iconNMunk
        else:
            if avail > total:
                avail = total

            return self.iconPercent[int((avail / float(total)) * self.PERCENT_RANGE)]

    def get_need_months_icon_text(self, needsTotal, itemSum, nmonths, deficon):
        """Сочиняет текст для всплывающей подсказки и подбирает подобающую иконку.

        Параметры:
        needsTotal  - общая необходимая сумма;
        itemSum     - если не None - цена товара для вызова из refresh_wishlistview();
        nmonths     - кол-во месяцев, необходимых на накопление;
        deficon     - экземпляр Pixbuf с предварительно выбранной иконкой,
                      (напр. вызовом get_percent_icon).

        Возвращает кортеж из трёх элементов:
        1й: строка с количеством месяцев,
        2й: экземпляр Pixbuf; для небольших сроков возвращает deficon,
            для больших см. ниже в коде;
        3й: текст для всплывающей подсказки (в формате Pango Markup)."""

        nmicon = deficon
        infomonths = ''

        if nmonths is None or nmonths <= 0:
            needmonths = '-'
        else:
            needmonths = str(nmonths)

            if nmonths > 36:
                infomonths = 'трёх лет.\nС твоими мозгами что-то не так, сильно не так!'
                nmicon = self.iconNM36m
            elif nmonths > 18:
                infomonths = 'полутора лет.\nУ тебя с головой всё в порядке?'
                nmicon = self.iconNM18m
            elif nmonths > 12:
                infomonths = 'года.\nМожет, лучше забить?'
                nmicon = self.iconNM12m
            elif nmonths > 6:
                infomonths = 'полугода.\nТебе точно это надо?'
                nmicon = self.iconNM6m

        if infomonths:
            infomonthtxt = '<b>На накопление %sнужно более %s</b>' %\
                ('' if not needsTotal else '%d бабла ' % needsTotal,
                infomonths)
        elif itemSum <= 0:
            infomonthtxt = '<b>Ценник не указан. Время накопления - неизвестно...</b>'
        else:
            infomonthtxt = ''

        return (needmonths, nmicon, infomonthtxt)

    def recalculate_items(self):
        """Полный пересчёт (а также обновление состояния чекбокса
        "выбрать всё")."""

        nTotal, nSelected = self.wishCalc.recalculate()

        if nTotal == 0:
            sa = False
            si = False
        else:
            sa = nSelected == nTotal
            si = (nSelected != 0) and (not sa)

        self.cbSelectAll.set_active(sa)
        self.cbSelectAll.set_inconsistent(si)

    def refresh_wishlistview(self, selitem=None):
        """Перерасчёт списка товаров, обновление содержимого TreeView.

        selitem - None или экземпляр WishCalc.Item, в последнем случае
                  после обновления TreeView в нём должен быть подсвечен
                  элемент дерева, содержащий соотв. Item."""

        self.recalculate_items()

        # получается, что проходим по TreeStore второй раз (после recalculate)
        # ну да и хрен с ним пока...

        def __refresh_node(parentitr):
            """Обновление полей элементов TreeStore на основе соответствующих
            значений полей экземпляров WishCalc.Item.

            Возвращает экземпляр Gtk.TreeIter, указывающий на элемент дерева,
            который должен стать активным после обновления всего дерева."""

            itr = self.wishCalc.store.iter_children(parentitr)

            __itersel = None

            while itr is not None:
                item = self.wishCalc.store.get_value(itr, WishCalc.COL_ITEM_OBJ)

                if item is selitem:
                    __itersel = itr

                if item.incart and item.paid:
                    needs = 'оплачено'
                    needsicon = self.iconNMok
                    needmonths = ''
                    infomonthtxt = ''
                else:
                    if item.needCash == 0:
                        needs = 'хватает'
                        needsicon = self.iconNMok
                    elif item.needCash is None:
                        needs = '?'
                        needsicon = self.iconNMunk
                    else:
                        if item.availCash > 0:
                            needs = str(item.needCash)
                            needsicon = self.get_percent_icon(item.availCash, item.sum)
                        else:
                            needs = str(item.needTotal) if item.needTotal else ''
                            needsicon = self.iconNMempty

                    needmonths, needsicon, infomonthtxt = self.get_need_months_icon_text(item.needTotal,
                        item.sum, item.needMonths, needsicon)

                itemname = markup_escape_text(item.name)

                nchildren = self.wishCalc.store.iter_n_children(itr)
                if nchildren > 1:
                    itemname = '%s <span size="smaller"><i>(%d)</i></span>' % (itemname, nchildren)

                infobuf = ['<b>%s</b>' % itemname]
                infomonths = ''

                if item.info:
                    infobuf += ['', markup_escape_text(item.info)]

                if infomonthtxt:
                    infobuf += ['', infomonthtxt]

                importance = item.importance
                if importance == 0:
                    importance = item.childrenImportance

                #!
                if item.incart:
                    inCartIcon = self.iconNMincart
                    infoincart = '<u>Товар заказан%s.</u>' % ('' if not item.paid else ' и оплачен')
                elif item.childrenInCart:
                    inCartIcon = self.iconNMchildrenincart
                    infoincart = '<u>Некоторые из вложенных товаров заказаны.</u>'
                else:
                    inCartIcon = self.iconNMnotincart
                    infoincart = ''

                if infoincart:
                    infobuf += ['', infoincart]

                # пока отключено, т.к. не уверен, что стоит долбать treeview
                # обновлениями всех ветвей при клике по чекбоксам
                #if item.childrenSelected:
                #    infobuf += ['', 'Выбрано несколько вложенных товаров.']

                #
                __subsel = __refresh_node(itr)

                if __subsel is not None:
                    __itersel = __subsel

                self.wishCalc.store.set(itr,
                    (WishCalc.COL_NAME,
                        WishCalc.COL_COST,
                        WishCalc.COL_NEEDED, WishCalc.COL_NEED_ICON,
                        WishCalc.COL_NEED_MONTHS, WishCalc.COL_INFO,
                        WishCalc.COL_QUANTITY, WishCalc.COL_SUM,
                        WishCalc.COL_IMPORTANCE,
                        WishCalc.COL_INCART,
                        #WishCalc.COL_SELECTEDSUBITEMS,
                        ),
                    (itemname,
                        str(item.cost) if item.cost else '?',
                        needs,
                        needsicon,
                        needmonths,
                        '\n'.join(infobuf),
                        str(item.quantity),
                        str(item.sum) if item.cost else '?',
                        self.importanceIcons[importance],
                        inCartIcon,
                        #item.childrenSelected,
                        ))

                itr = self.wishCalc.store.iter_next(itr)

            return __itersel

        itersel = __refresh_node(None)

        # вертаем выбор взад
        if itersel is not None:
            self.item_select_by_iter(itersel)

        self.setup_widgets_sensitive()

        self.refresh_incart_view()

        self.refresh_totalcash_view()
        self.refresh_remains_view()

    def item_select_by_iter(self, itr, expandrow=False):
        path = self.wishCalc.store.get_path(itr)

        if expandrow:
            self.wishlistview.expand_row(path, False)

        self.wishlistviewsel.select_path(path)
        self.wishlistview.set_cursor(path, None, False)

    def __do_edit_item(self, newitem, newaschild=False):
        """Вызов редактора описания товара.

        newitem     - булевское значение:
                      False, если нужно отредактировать выбранный
                      товар,
                      True, если нужно создать новый товар;
        newaschild  - используется только если newitem==True;
                      значения:
                      None  - новый товар добавляется в корневой уровень
                              дерева;
                      False - новый товар добавляется на том же уровне
                              дерева, что и выбранный товар (или в корневом
                              уровне, если ничего не выбрано);
                      True  - новый товар добавляется как дочерний
                              к выбранному."""

        itrsel = self.get_selected_item_iter()

        if newitem:
            item = None
        else:
            if itrsel is None:
                return

            item = self.wishCalc.get_item(itrsel)

        item = self.itemEditor.edit(item,
            not newitem and (False if itrsel is None else self.wishCalc.store.iter_n_children(itrsel) > 0))

        if item is not None:
            if not newitem:
                # заменяем существующий экземпляр изменённым
                self.wishCalc.replace_item(itrsel, item)
            else:
                # добавляем новый
                if newaschild is None:
                    parent = None
                elif newaschild == True:
                    parent = itrsel
                else:
                    parent = self.wishCalc.store.iter_parent(itrsel) if itrsel is not None else None

                if itrsel is None:
                    # потому что см. поведение GtkTreeStore.insert_after с sibling=None
                    self.wishCalc.append_item(parent, item)
                else:
                    self.wishCalc.store.insert_after(parent, itrsel, self.wishCalc.make_store_row(item))

                if parent is not None:
                    # принудительно разворачиваем ветвь, иначе TreeView не изменит selection
                    path = self.wishCalc.store.get_path(parent)
                    self.wishlistview.expand_row(path, False)

            self.refresh_wishlistview(item)

    def wl_row_activated(self, treeview, path, col):
        if col == self.wlv_colItemInCart:
            self.item_toggle_incart(treeview)
        else:
            self.__do_edit_item(False)

    def wl_item_selected_toggled(self, cr, path):
        # тыкнут чекбокс выбора элемента дерева
        # пока у нас один чекбокс на строку - столбец не проверяем
        itr = self.wishCalc.store.get_iter(path)

        item = self.wishCalc.store.get_value(itr, WishCalc.COL_ITEM_OBJ)

        itemsel = not self.wishCalc.store.get_value(itr, WishCalc.COL_SELECTED)
        self.wishCalc.store.set_value(itr, WishCalc.COL_SELECTED, itemsel)

        #if itemsel:
        #    self.wishCalc.store.set_value(itr, WishCalc.COL_SELECTEDSUBITEMS, False)

        # пересчитываем сумму ценников выбранных товаров
        # self.refresh_wishlistview() при этом вызывать не требуется

        self.recalculate_items()
        #self.refresh_wishlistview()
        self.refresh_selected_sum_view()

    def refresh_incart_view(self):
        self.incartbox.set_sensitive(self.wishCalc.totalInCartCount > 0)

        self.incartcountentry.set_text(str(self.wishCalc.totalInCartCount))
        self.incartsumentry.set_text(str(self.wishCalc.totalInCartSum))

    def refresh_selected_sum_view(self):
        self.wishCalc.recalculate()

        if self.wishCalc.totalSelectedCount:
            vsel = True

            selcount = str(self.wishCalc.totalSelectedCount)
            selsums = str(self.wishCalc.totalSelectedSum)

            if self.wishCalc.totalCash >= self.wishCalc.totalSelectedSum:
                needs = 'хватает'
                needsicon = self.iconNMok
                needsinfo = needs
                needmonths = ''
            else:
                if self.wishCalc.totalSelectedSum == 0:
                    needs = ''
                    needsicon = self.iconNMempty
                    needsinfo = '<b>Денег нет совсем!</b>'
                    needmonths = '?'
                else:
                    need = self.wishCalc.totalSelectedSum

                    if self.wishCalc.totalCash > 0:
                        need -= self.wishCalc.totalCash

                    needs = str(need)

                    needsicon = self.get_percent_icon(self.wishCalc.totalCash, self.wishCalc.totalSelectedSum)
                    needmonths, needsicon, needsinfo = self.get_need_months_icon_text(need,
                        self.wishCalc.totalSelectedSum,
                        WishCalc.need_months(need, self.wishCalc.refillCash),
                        needsicon)

        else:
            vsel = False

            selsums = ''
            selcount = 'нет'
            needs = ''
            needsicon = self.iconNMempty
            needsinfo = ''
            needmonths = ''

        self.selectedsumentry.set_text(selsums)
        self.selectedcountentry.set_text(selcount)

        self.selectedneedsentry.set_text(needs)
        self.selectedneedsentry.set_tooltip_markup(needsinfo)

        self.selectedneedsentry.set_icon_from_pixbuf(Gtk.EntryIconPosition.PRIMARY, needsicon)
        self.selectedneedsentry.set_icon_tooltip_markup(Gtk.EntryIconPosition.PRIMARY, needsinfo)

        self.selectedmonthsentry.set_text(needmonths)

        self.selectedsumbox.set_sensitive(vsel)

        self.setup_widgets_sensitive() #!!!

    def get_selected_item_iter(self):
        """Возвращает Gtk.TreeIter если в TreeView выбрана строка,
        иначе None."""
        return self.wishlistviewsel.get_selected()[1]

    def item_set_importance(self, widget, importance=None):
        itrsel = self.get_selected_item_iter()

        if itrsel is None:
            return

        item = self.wishCalc.get_item(itrsel)

        item.importance = importance
        self.refresh_wishlistview(item)

    def item_toggle_incart(self, widget):
        itrsel = self.get_selected_item_iter()

        if itrsel is None:
            return

        item = self.wishCalc.get_item(itrsel)
        item.incart = not item.incart
        if not item.incart:
            item.paid = False

        self.refresh_wishlistview(item)

    def item_toggle_paid(self, widget):
        itrsel = self.get_selected_item_iter()

        if itrsel is None:
            return

        item = self.wishCalc.get_item(itrsel)

        if item.incart:
            item.paid = not item.paid

            self.refresh_wishlistview(item)

    def item_edit(self, btn):
        self.__do_edit_item(False)

    def item_add(self, btn):
        self.__do_edit_item(True)

    def item_add_subitem(self, btn):
        self.__do_edit_item(True, True)

    def __item_select_all(self, select):
        self.wishCalc.select_items(select)
        self.recalculate_items()
        self.refresh_selected_sum_view()

        self.cbSelectAll.set_active(select)
        self.cbSelectAll.set_inconsistent(False)

    def item_select_all(self, widget):
        self.__item_select_all(True)

    def item_unselect_all(self, widget):
        self.__item_select_all(False)

    def item_expand_all(self, widget):
        self.wishlistview.expand_all()

    def item_collapse_all(self, widget):
        self.wishlistview.collapse_all()

    def item_random_choice(self, widget):
        # список всех Gtk.TreeIter дерева товаров
        alliters = []

        def __gather_children(parentitr):
            itr = self.wishCalc.store.iter_children(parentitr)
            while itr is not None:
                alliters.append(itr)
                __gather_children(itr)
                itr = self.wishCalc.store.iter_next(itr)

        __gather_children(None)

        if alliters:
            self.item_select_by_iter(random_choice(alliters), True)

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
                    parent = self.wishCalc.store.iter_parent(itrsel)

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

    def item_copy_url(self, btn):
        itr = self.get_selected_item_iter()
        if itr:
            item = self.wishCalc.get_item(itr)
            if item.url:
                self.clipboard.set_text(item.url, -1)

    def __delete_item(self, ispurchased):
        """Удаление товара из списка.
        Если ispurchased == True, товар считается купленным, и его цена
        вычитается из суммы доступных наличных."""

        itr = self.get_selected_item_iter()
        if not itr:
            return

        nchildren = self.wishCalc.store.iter_n_children(itr)

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
            movefunc = self.wishCalc.store.move_before if (down ^ onepos) else self.wishCalc.store.move_after

            if onepos:
                moveref = self.wishCalc.store.iter_next(itr) if down else self.wishCalc.store.iter_previous(itr)
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

        self.wishCalc.totalCash = v if v is not None else 0

        self.refresh_wishlistview()
        self.refresh_selected_sum_view()

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


def process_cmdline(args):
    if len(args) > 1:
        return os.path.abspath(args[1])
    else:
        for wlfname in ('.',):# os.path.split(args[0])[0]):
            wlfname = os.path.join(os.path.abspath(wlfname), DEFAULT_FILENAME)

            if os.path.exists(wlfname):
                return(wlfname)


def main(args):
    MainWnd(process_cmdline(args)).main()

    return 0


if __name__ == '__main__':
    exit(main(sys.argv))
