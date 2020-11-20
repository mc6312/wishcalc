#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""wishcalc.py

    Copyright 2017-2020 MC-6312 <mc6312@gmail.com>

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

from enum import IntEnum

from warnings import warn

from wcdata import *
from wcconfig import *
from wccommon import *
from wcitemed import *
from wccalculator import *


class MainWnd():
    PERCENT_RANGE = 4

    CLIPBOARD_DATA = 'wishcalc2_clipboard_data'

    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def before_exit(self):
        if self.wishCalc is not None:
            if self.wishCalc.filename:
                self.wishlist_save()
            elif self.wishCalc.store.iter_n_children(None) > 0:
                self.file_save_as(None)

        self.cfg.save()

    def wnd_delete_event(self, wnd, event):
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
        # главное меню
        #
        self.mnuFileOpenRecent = uibldr.get_object('mnuFileOpenRecent')

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

        self.importanceIcons = ImportanceIcons(resldr)

        # TreeStore используется как хранилище данных во время работы
        # в первом столбце (WishCalc.COL_ITEM_OBJ) хранится ссылка
        # на экземпляр WishCalc.Item (см. wcdata.py)

        self.wishlistview = uibldr.get_object('wishlistview')
        self.wishlistview.set_tooltip_column(WishCalc.COL_INFO)

        self.wishlistviewsel = uibldr.get_object('wishlistviewsel')

        self.wlv_colItemSelect, self.wlv_colItemInCart, self.wlv_colItemImportance = get_ui_widgets(uibldr,
            ('colItemSelect', 'colItemInCart', 'colItemImportance'))

        uibldr.get_object('imgCart').set_from_pixbuf(self.iconNMincart)
        uibldr.get_object('imgImportance').set_from_pixbuf(self.importanceIcons.icons[0].pixbuf)

        uibldr.get_object('imgItemPasteInto').set_from_pixbuf(resldr.load_pixbuf('images/paste-into.svg', nmiconsize, nmiconsize))

        #
        # наличность и остаток
        #
        self.cashentry, self.refillentry, self.remainsentry = get_ui_widgets(uibldr,
            ('cashentry', 'refillentry', 'remainsentry'))

        self.cashcalc = Calculator(resldr, self.cashentry, True)
        self.refillcalc = Calculator(resldr, self.refillentry, True)

        # сумма выбранных в дереве
        self.selectedsumbox, self.selectedcounttxt, self.selectedsumtxt, \
        self.needsumbox, self.selectedneedstxt, self.selectedneedsicon, \
        self.selectedmonthstxt = get_ui_widgets(uibldr,
            ('selectedsumbox', 'selectedcounttxt', 'selectedsumtxt',
             'needsumbox', 'selectedneedstxt', 'selectedneedsicon',
             'selectedmonthstxt'))

        # сумма заказанных товаров
        self.incartbox, self.incartcounttxt, self.incartsumtxt = get_ui_widgets(uibldr,
            ('incartbox', 'incartcounttxt', 'incartsumtxt'))

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
        self.submnuItemImportance = Gtk.Menu.new()
        self.submnuItemImportance.set_reserve_toggle_size(False)

        self.mnuItemImportance.set_submenu(self.submnuItemImportance)

        for importance, iicon in enumerate(self.importanceIcons.icons):
            mitem = Gtk.MenuItem.new()
            mibox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)
            mibox.pack_start(Gtk.Image.new_from_pixbuf(iicon.pixbuf), False, False, 0)
            mibox.pack_start(Gtk.Label.new_with_mnemonic('_%d: %s' % (importance + 1, iicon.label)), False, False, 0)
            mitem.add(mibox)
            mitem.connect('activate', self.item_set_importance, importance)

            self.submnuItemImportance.append(mitem)

        self.submnuItemImportance.show_all()

        # костыль для избавления от лишней дерготни подменю "важности":
        # когда оно уже открыто из меню уровнем выше, тут д.б. значение > 0
        self.mnuItemImportanceVisible = 0

        #
        # виджеты, свойство "sensitive" которых зависит от состояния списка
        #
        # вот это вот (и соотв. setup_widgets_sensitive()) возможно
        # придётся переделывать через actions

        self.widgetsItemEditing = WidgetList.new_from_builder(uibldr,
            'mnuItemEdit', 'btnItemEdit', 'mnuItemPurchased', 'btnItemPurchased',
            'mnuItemAddSubItem', 'btnItemAddSubItem',
            'mnuItemToggleInCart', 'mnuItemTogglePaid', 'mnuItemImportance',
            'mnuItemOpenURL', 'btnItemOpenURL', 'mnuItemRemove', 'btnItemRemove')
        self.widgetsItemMoveUp = WidgetList.new_from_builder(uibldr,
            'mnuItemMoveUp', 'btnItemMoveUp',
            'mnuItemMoveToTop', 'btnItemMoveToTop')
        self.widgetsItemMoveDown = WidgetList.new_from_builder(uibldr,
            'mnuItemMoveDown', 'btnItemMoveDown',
            'mnuItemMoveToBottom', 'btnItemMoveToBottom')
        self.widgetsItemURL = WidgetList.new_from_builder(uibldr,
            'mnuItemOpenURL', 'btnItemOpenURL', 'mnuItemCopyURL')
        self.widgetsItemCopyPaste = WidgetList.new_from_builder(uibldr,
            'mnuItemCopy', 'btnItemCopy', 'mnuItemPasteInto', 'btnItemPasteInto')
            # эти - всегда будут доступны, т.к. возможна вставка при невыбранном элементе
            #, 'mnuItemPaste', 'btnItemPaste'))

        # а вот оно будет рулиться НЕ из setup_widgets_sensitive()!
        self.widgetsRefillCash = WidgetList.new_from_builder(uibldr,
            'mnuRefillCash', 'btnRefillCash')

        # выделение галками
        self.widgetsSelectAll = WidgetList.new_from_builder(uibldr, 'cbSelectAll', 'mnuItemSelectAll')
        self.widgetsSelectNone = WidgetList.new_from_builder(uibldr, 'mnuItemUnselectAll')
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

        logosize = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 4

        self.dlgAbout.set_logo(resldr.load_pixbuf('images/wishcalc_logo.svg', logosize, logosize))
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
        # диалог экспорта файла CSV
        #
        self.dlgFileSaveCSV = uibldr.get_object('dlgFileSaveCSV')
        self.chkExportHRHeaders = uibldr.get_object('chkExportHRHeaders')
        self.chkExportHRValues = uibldr.get_object('chkExportHRValues')

        # (dialog, title, isjson)
        self.fileChooserParams = {self.FileChooserMode.OPEN:(self.dlgFileOpen, 'Открыть', True),
            self.FileChooserMode.SAVE_AS:(self.dlgFileSaveAs, 'Сохранить как...', True),
            self.FileChooserMode.EXPORT:(self.dlgFileSaveCSV, 'Экспорт в CSV', False)}

        #
        # !!!
        #
        self.window.show_all()

        self.cfg.load()
        #print('loaded:', self.cfg.mainWindow)
        self.load_window_state()
        self.itemEditor.load_window_state()
        #print('load_window_state called:', self.cfg.mainWindow)
        self.update_recent_files_menu()

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        uibldr.connect_signals(self)

        #
        # первоначальное заполнение списка
        #
        if wlfname is not None:
            if not self.wishlist_load(wlfname):
                exit(1)
        else:
            self.wishCalc = WishCalc(None)

        self.wishlist_is_loaded()

        self.setup_widgets_sensitive()

    def update_recent_files_menu(self):
        if not self.cfg.recentFiles:
            self.mnuFileOpenRecent.set_submenu()
        else:
            mnu = Gtk.Menu.new()
            mnu.set_reserve_toggle_size(False)

            for ix, rfn in enumerate(self.cfg.recentFiles):
                # сокращаем отображаемое имя файла, длину пока приколотим гвоздями
                #TODO когда-нибудь сделать сокращение отображаемого в меню имени файла по человечески
                lrfn = len(rfn)
                if lrfn > 40:
                    disprfn = '%s...%s' % (rfn[:3], rfn[lrfn - 34:])
                else:
                    disprfn = rfn

                mi = Gtk.MenuItem.new_with_label(disprfn)
                mi.connect('activate', self.file_open_recent, ix)
                mnu.append(mi)

            mnu.show_all()

            self.mnuFileOpenRecent.set_submenu(mnu)

    def file_open_recent(self, wgt, ix):
        fname = self.cfg.recentFiles[ix]

        # проверяем наличие файла обязательно, т.к. в списке недавних
        # могут быть уже удалённые файлы или лежащие на внешних
        # неподключённых носителях
        # при этом метод file_open_filename() проверку производить
        # не должен, т.к. в первую очередь расчитан на вызов после
        # диалога выбора файла, который несуществующего файла не вернёт.
        # кроме того, сообщение об недоступном файле _здесь_ должно
        # отличаться от просто "нету файла"

        if not os.path.exists(fname):
            msg_dialog(self.window, TITLE,
                'Файл "%s" отсутствует или недоступен' % fname)
        else:
            self.file_open_filename(fname)

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
            etime = Gtk.get_current_event_time()
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
        файла (т.е. если wishlist_load() не рухнул с исключением)."""

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
        self.wnd_destroy(widget)

    def file_save(self, mnu):
        """Сохранение файла"""

        if self.wishCalc.filename:
            self.wishlist_save()
        else:
            self.file_save_as(mnu)

    class FileChooserMode(IntEnum):
        OPEN, SAVE_AS, EXPORT = range(3)

    def __run_filename_dialog(self, mode):
        dlg, title, isjson = self.fileChooserParams[mode]

        dlg.set_title(title)

        #TODO костыль с именем файла переделать?
        if isjson:
            fname = self.wishCalc.filename if self.wishCalc.filename else DEFAULT_FILENAME
        else:
            fname = self.wishCalc.exportFilename

        dname, fname = os.path.split(fname)

        dlg.set_current_folder(dname)
        if mode == self.FileChooserMode.OPEN:
            dlg.select_filename(fname)
        else:
            dlg.set_current_name(fname)

        r = dlg.run()
        dlg.hide()

        return (dlg, r)

    def file_export_csv(self, mnu):
        """Экспорт в файла формата CSV с выбором имени,
        всех или выбранных товаров."""

        self.chkExportHRHeaders.set_active(self.wishCalc.exportHRHeaders)
        self.chkExportHRValues.set_active(self.wishCalc.exportHRValues)

        dlg, r = self.__run_filename_dialog(self.FileChooserMode.EXPORT)

        if r == Gtk.ResponseType.OK:
            self.wishCalc.exportFilename = dlg.get_filename()
            self.wishCalc.exportHRHeaders = self.chkExportHRHeaders.get_active()
            self.wishCalc.exportHRValues = self.chkExportHRValues.get_active()

            try:
                self.wishCalc.save_csv()
            except Exception as ex:
                msg_dialog(self.window, TITLE, 'Ошибка экспорта в файл "%s":\n%s' % (self.wishCalc.exportFilename, str(ex)))

    def file_save_as(self, mnu):
        """Сохранение файла с выбором имени"""

        dlg, r = self.__run_filename_dialog(self.FileChooserMode.SAVE_AS)

        if r == Gtk.ResponseType.OK:
            self.wishCalc.filename = dlg.get_filename()
            if self.wishlist_save():
                self.refresh_window_title()

    def file_open_filename(self, fname):
        if self.wishCalc.filename and os.path.samefile(fname, self.wishCalc.filename):
            return

        self.wishlist_save()

        if self.wishlist_load(fname):
            self.cfg.add_recent_file(fname)
            self.update_recent_files_menu()
            self.wishlist_is_loaded()

    def file_open(self, mnu):
        dlg, r = self.__run_filename_dialog(self.FileChooserMode.OPEN)

        if r == Gtk.ResponseType.OK:
            self.file_open_filename(dlg.get_filename())

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

                bcanopenurl = len(self.wishCalc.get_item(itr).url) != 0

            bcanselect = True
            bcanunselect = self.wishCalc.totalSelectedCount > 0

        self.widgetsItemCopyPaste.set_sensitive(bsens)
        self.widgetsItemEditing.set_sensitive(bsens)
        self.widgetsItemMoveUp.set_sensitive(bsens & bcanmoveup)
        self.widgetsItemMoveDown.set_sensitive(bsens & bcanmovedown)
        self.widgetsItemURL.set_sensitive(bsens & bcanopenurl)

        self.widgetsSelectAll.set_sensitive(bcanselect)
        self.widgetsSelectNone.set_sensitive(bcanselect & bcanunselect)

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
                        if item.sum <= 0:
                            # сумма <0 для "скидок"
                            needs = '-'
                            needsicon = self.iconNMempty
                        else:
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
                #if importance == 0:
                if importance < item.childrenImportance:
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
                        self.importanceIcons.icons[importance].pixbuf,
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
        v = self.wishCalc.totalInCartCount > 0

        self.incartbox.set_sensitive(v)
        self.incartbox.set_visible(v)

        self.incartcounttxt.set_text(str(self.wishCalc.totalInCartCount))
        self.incartsumtxt.set_text(str(self.wishCalc.totalInCartSum))

    def refresh_selected_sum_view(self):
        self.wishCalc.recalculate()

        if self.wishCalc.totalSelectedCount:
            sumboxvisible = True

            selcount = str(self.wishCalc.totalSelectedCount)
            selsums = str(self.wishCalc.totalSelectedSum)

            if self.wishCalc.totalCash >= self.wishCalc.totalSelectedSum:
                needs = 'хватает'
                needsicon = self.iconNMok
                needsinfo = needs
                needmonths = ''
                needsumboxvisible = False
            else:
                needsumboxvisible = True

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
            sumboxvisible = False
            needsumboxvisible = False

            selsums = ''
            selcount = 'нет'
            needs = ''
            needsicon = self.iconNMempty
            needsinfo = ''
            needmonths = ''

        self.selectedsumtxt.set_text(selsums)
        self.selectedcounttxt.set_text(selcount)

        self.selectedneedstxt.set_text(needs)
        self.selectedneedstxt.set_tooltip_markup(needsinfo)

        self.selectedneedsicon.set_from_pixbuf(needsicon)
        self.selectedneedsicon.set_tooltip_markup(needsinfo)

        self.selectedmonthstxt.set_text(needmonths)

        self.selectedsumbox.set_visible(sumboxvisible)

        self.needsumbox.set_visible(sumboxvisible & needsumboxvisible)

        #self.setup_widgets_sensitive() #!!!

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

    def __get_item_names(self, itr, children=True):
        """Получает и возвращает список строк с именами элемента дерева,
        на который указывает itr (экземпляр Gtk.TreeIter), и всех
        вложенных элементов, если children==True."""

        item = self.wishCalc.get_item(itr)
        names = [item.name]

        def __gather_subitem_names(fromitr):
            itr = self.wishCalc.store.iter_children(fromitr)

            while itr is not None:
                names.append(self.wishCalc.get_item(itr).name)

                __gather_subitem_names(itr)

                itr = self.wishCalc.store.iter_next(itr)

        if children:
            __gather_subitem_names(itr)

        return names

    def __get_selected_items(self, copydata):
        """Получение списка выбранных элементов дерева.

        copydata    - режим копирования;
                      False - в список помещаются только строки
                              с названиями товаров;
                      True  - в список помещаются словари с полными
                              данными товаров.

        Если есть помеченные (чекбоксами) элементы - берём их все,
        иначе - только тот, на котором курсор.
        В выхлоп попадают все подэлементы выбранных элементов.
        Возвращает, соответственно, список, если было что возвращать,
        иначе - пустой список."""

        retl = []

        def __get_itemdict(itr):
            itemdict = self.wishCalc.get_item(itr).get_fields_dict()

            subitems = self.wishCalc.items_to_list(itr)
            if subitems:
                itemdict[WishCalc.Item.ITEMS] = subitems

            return itemdict

        def __gather_checked_items(fromitr):
            # проверяем сам элемент

            lret = []

            if fromitr is not None:
                if self.wishCalc.get_item_checked(fromitr):
                    if copydata:
                        lret.append(__get_itemdict(fromitr))
                    else:
                        lret += self.__get_item_names(fromitr)

            itr = self.wishCalc.store.iter_children(fromitr)

            while itr is not None:
                lret += __gather_checked_items(itr)
                itr = self.wishCalc.store.iter_next(itr)

            return lret

        if self.wishCalc.totalSelectedCount:
            # есть помеченные

            retl += __gather_checked_items(None)
        else:
            # только выделенный элемент TreeView
            itrsel = self.get_selected_item_iter()

            if itrsel is None:
                return

            if copydata:
                retl.append(__get_itemdict(itrsel))
            else:
                retl += self.__get_item_names(itrsel)

        return retl

    def item_copy(self, btn):
        """Кладём выбранные элементы с подэлементами в clipboard
        в виде JSON.
        Если есть помеченные (чекбоксами) элементы - кладём их все,
        иначе - только тот, на котором курсор.
        А нету курсора - ничего и не делаем."""

        copylst = self.__get_selected_items(True)

        if len(copylst):
            self.clipboard.set_text(json.dumps({self.CLIPBOARD_DATA:copylst},
                ensure_ascii=False,
                # отступы - на случай вставки в текстовый редактор,
                # а не в WishCalc
                indent='  '),
                -1)

    def item_copy_as_text(self, wgt):
        """Действует аналогично item_copy(), но в clipboard помещается
        текст, разделенный переносами строк, содержащий только названия
        выбранных товаров."""

        copylst = self.__get_selected_items(False)

        if len(copylst):
            copylst.append('') # дабы join'ом добавился последний перевод строки
            self.clipboard.set_text('\n'.join(copylst), -1)

    def __item_paste(self, intoselected):
        """Вставка товара из буфера обмена.
        Eсли в TreeView есть выбранный элемент:
            intoselected == True:
                товар вставляется как дочерний элемент к выбранному;
            intoselected == False:
                товар вставляется на том же уровне дерева после выбранного.
        Если выбранного элемента нет, товар вставляется в конец списка
        на верхнем уровне дерева."""

        #
        # пытаемся тащить данные из буфера обмена
        #

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

        E_PASTE = 'Вставка из буфера обмена'

        itrsel = self.get_selected_item_iter()
        if itrsel is None:
            # ничего не выбрано - вставляем элемент в конец списка
            parentitr = None
        elif intoselected:
            parentitr = itrsel
            itrsel = None
        else:
            # иначе - после выбранного элемента на его уровне
            parentitr = self.wishCalc.store.iter_parent(itrsel)

        def __do_paste_itemdict(itemdict):
            # таки пытаемся уже чего-то вставить
            item = WishCalc.Item()
            try:
                item.set_fields_dict(itemdict)

                inserteditr = self.wishCalc.store.insert_after(parentitr, itrsel,
                    self.wishCalc.make_store_row(item))

                # рекурсивно добавляем подэлементы, если они есть
                if WishCalc.Item.ITEMS in itemdict:
                    self.wishCalc.load_subitems(inserteditr,
                        itemdict[WishCalc.Item.ITEMS], [])

                return (item, inserteditr)

            except Exception as ex:
                # пока - так
                msg_dialog(self.window, E_PASTE,
                    'Ошибка: %s' % str(ex))
                return

        items = tmpd[self.CLIPBOARD_DATA]

        # на случай, ежели копипастить будут из предыдущей версии,
        # проверяем, что нам приехало
        if isinstance(items, list):
            for itemdict in items:
                selitem, itrsel =  __do_paste_itemdict(itemdict)
        elif isinstance(items, dict):
            selitem, itrsel = __do_paste_itemdict(items)
        else:
            msg_dialog(self.window, E_PASTE,
                'В буфере обмена находятся данные от несовместимой версии программы')
            return

        self.refresh_wishlistview(selitem)

    def item_paste(self, btn):
        """Вставка товара из буфера обмена."""

        self.__item_paste(None)

    def item_paste_into_selected(self, btn):
        """Вставка из буфера обмена дочерних элементов в выбранный"""

        self.__item_paste(self.get_selected_item_iter())

    def item_open_url(self, btn):
        itr = self.get_selected_item_iter()
        if itr:
            item = self.wishCalc.get_item(itr)
            if item.url:
                if len(item.url) == 1:
                    webbrowser.open_new_tab(item.url[0][0])
                else:
                    mnu = Gtk.Menu.new()
                    mnu.set_reserve_toggle_size(False)

                    for url, urlname in item.url:
                        mi = Gtk.MenuItem.new_with_label(urlname if urlname else url)
                        mi.connect('activate', self.item_open_url_from_menu, url)
                        mnu.append(mi)

                    mnu.show_all()

                    self.wishlist_pop_up_menu(None, mnu)

    def item_open_url_from_menu(self, mi, url):
        webbrowser.open_new_tab(url)

    def item_copy_url(self, btn):
        itr = self.get_selected_item_iter()
        if itr:
            item = self.wishCalc.get_item(itr)
            if item.url:
                self.clipboard.set_text(item.url, -1)

    def __do_delete_item(self, ispurchased):
        """Удаление товара из списка.
        Если ispurchased == True, товар считается купленным, и его цена
        вычитается из суммы доступных наличных."""

        if self.wishCalc.totalSelectedCount:
            # удаление помеченных

            delitrs = self.wishCalc.get_checked_items()
        else:
            # удаление выделенного курсорома
            itr = self.get_selected_item_iter()
            if not itr:
                return

            delitrs = [itr]

        ndel = len(delitrs)

        if ndel > 1:
            sitems = 'выбранные товары (всего - %d)' % ndel
            onlyone = False
        else:
            sitems = 'товар "%s"' % self.wishCalc.get_item(delitrs[0]).name
            onlyone = True

        if not ispurchased:
            what = 'Удалить'
            details = ''
        else:
            what = 'Убрать из списка'
            details = ' купленный' if onlyone else ' купленные и'

        msgwhat = '%s%s %s?' % (what, details, sitems)

        if msg_dialog(self.window, 'Удаление',
                msgwhat,
                buttons=Gtk.ButtonsType.YES_NO,
                destructive_response=Gtk.ResponseType.YES) == Gtk.ResponseType.YES:

            for itr in delitrs:
                self.wishCalc.item_delete(itr, ispurchased)

            self.refresh_wishlistview()

    def item_purchased(self, btn):
        self.__do_delete_item(True)

    def item_delete(self, btn):
        self.__do_delete_item(False)

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

        self.widgetsRefillCash.set_sensitive(bsens)

    def do_refill_cash(self, btn):
        if self.wishCalc.refillCash > 0:
            self.wishCalc.totalCash += self.wishCalc.refillCash
            self.refresh_wishlistview()

    def refresh_remains_view(self):
        self.remainsentry.set_text(str(self.wishCalc.totalRemain) if self.wishCalc.totalRemain > 0 else 'нет')

    def wishlist_save(self):
        """Сохранение списка.
        Возвращает булевское значение (True в случае успеха)."""

        try:
            self.wishCalc.save()

            return True
        except Exception as ex:
            msg_dialog(self.window, TITLE, 'Ошибка сохранения файла "%s":\n%s' % (self.wishCalc.filename, str(ex)))
            return False

    def wishlist_load(self, filename):
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
