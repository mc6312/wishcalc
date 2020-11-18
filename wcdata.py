#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" wcdata.py

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


import json
import os.path

#from gi.repository import Gtk, GObject
#from gi.repository.GdkPixbuf import Pixbuf

from collections import namedtuple

from wcconfig import JSON_ENCODING
from wccommon import *

import csv


MAX_ITEM_LEVEL = 3 # максимальный уровень вложенности WishCalc.Item
# в текущей версии не используется
# см. комментарий в WishCalc.Item.set_fields_dict()


# кол-во уровней "важности" товара, 0 - "неизвестно/неважно"
IMPORTANCE_LEVELS = (
    'не указана',
    'низкая',
    'обычная',
    'высокая',
    'высшая')

IMPORTANCE_LEVEL_MIN = 0
IMPORTANCE_LEVEL_MAX = len(IMPORTANCE_LEVELS) - 1

DEFAULT_FILENAME = 'wishlist.json'


def str_to_int_range(s, minvalue=-1, maxvalue=None):
    """Преобразует строчное значение цены s в целое число и возвращает его.
    Значение принудительно впихивается в указанный диапазон:

    minvalue    - минимальное целое значение или None (в последнем случае
                  мин. значение не проверяется;
    maxvalue    - максимальное целое значение или None (в последнем случае
                  макс. значение не проверяется).

    В случае неправильного (нечислового) значения возвращает None."""

    try:
        s = normalize_str(s)
        if not s:
            # 0 соответствует "значение не указано"
            return 0

        v = int(round(float(s)))

        if minvalue is not None and v < minvalue:
            v = minvalue

        if maxvalue is not None and v < maxvalue:
            v = maxvalue

        return v

    except ValueError:
        return None


def normalize_text(s):
    """Удаление лишних пробельных символов и пустых строк из строки"""

    return '\n'.join(filter(None, map(lambda t: ' '.join(t.split(None)), s.splitlines(False))))


def normalize_str(s):
    """Удаление лишних пробельных символов и пустых строк из строки"""

    return ' '.join(s.split(None))


def get_dict_item(fromdict, vname, *vtype, rangecheck=None, fallback=None, failifnokey=True):
    """Берёт из словаря  значение поля, проверяет тип и правильность значения.

    В случае успеха возвращает полученное значение, иначе генерирует исключение.

    fromdict    - словарь, из которого брать значение;
    vname       - строка, ключ словаря;
    vtype       - допустимые типы значения;
    rangecheck  - None или функция проверки диапазона значений;
                  должна возвращать булевское значение;
    fallback    - значение, которое следует возвращать при отсутствии
                  ключа vname в словаре;
                  если не указано (т.е. None), то поведение функции
                  зависит также от параметра failifnokey;
    failifnokey - что делать, если поля vname нет в словаре и fallback=None:
                  если True - генерируется исключение,
                  если False - функция в любом случае возвращает значение
                  fallback."""

    if vname not in fromdict:
        if fallback is not None or failifnokey == False:
            return fallback

        raise KeyError('отсутствует поле "%s"' % vname)

    v = fromdict[vname]

    typeok = False
    for vt in vtype:
        if isinstance(v, vt):
            typeok = True
            break

    if not typeok:
        raise TypeError('неправильный тип поля "%s"' % vname)

    if callable(rangecheck):
        if not rangecheck(v):
            raise ValueError('значение поля "%s" вне допустимого диапазона' % vname)

    return v


def importance_to_disp_str(imp):
    return IMPORTANCE_LEVELS[imp]

def bool_to_disp_str(b):
    return 'да' if b else 'нет'

def url_to_csv_str(url):
    tmp = []

    for url, urlname in url:
        turl = url

        if urlname:
            turl = '%s (%s)' % (turl, urlname)

        tmp.append(turl)

    return ','.join(tmp)


class WishCalc():
    """Обёртка для Gtk.TreeStore, хранящего ссылки на экземпляры Item
    и данные для отображения в Gtk.TreeView.

    Константы индексов столбцов Gtk.TreeStore указаны прямо здесь,
    т.к. этот класс работает напрямую с TreeStore, ибо в данном случае
    полное отделение UI от данных приведёт к дублированию кучи функций
    вроде изменения порядка элементов дерева (и для самого TreeView,
    и для данных).

    Внимание! При изменениях в wishcalc.ui нижеследующие константы
    должны быть приведены в соответствие!"""

    COL_ITEM_OBJ, COL_NAME, COL_COST, COL_NEEDED,\
    COL_NEED_ICON, COL_NEED_MONTHS, COL_INFO, COL_QUANTITY, COL_SUM,\
    COL_IMPORTANCE, COL_SELECTED, COL_INCART, COL_SELECTEDSUBITEMS = range(13)

    class Item():
        """Данные для описания товара.
        Перечисленные ниже имена полей используются для загрузки/сохранения
        JSON.
        Внимание! Имя "items" предназначено для обработчика JSON,
        списки вложенных элементов хранятся в Gtk.TreeStore,
        а не в экземпляре Item!"""

        # имена полей (для JSON)
        NAME = 'name'
        COST = 'cost'
        QUANTITY = 'quantity'
        SUM = 'sum'
        INFO = 'info'
        URL = 'url'
        IMPORTANCE = 'importance'
        INCART = 'incart'
        PAID = 'paid'
        ITEMS = 'items'

        __expar = namedtuple('__expar', 'name dispname tostr')

        CSV_FIELDS = (__expar(NAME, 'Название', str),
            __expar(COST, 'Цена', str),
            __expar(QUANTITY, 'Количество', str),
            __expar(SUM, 'Сумма', str),
            __expar(INFO, 'Описание', str),
            __expar(URL, 'URL', url_to_csv_str),
            __expar(IMPORTANCE, 'Важность', importance_to_disp_str),
            __expar(INCART, 'Заказано', bool_to_disp_str),
            __expar(PAID, 'Оплачено', bool_to_disp_str),
            )

        def new_copy(self):
            """Создаёт и возвращает новый экземпляр Item с копией
            содержимого."""

            ni = self.__class__()
            ni.get_data_from(self)
            return ni

        def __init__(self):
            # поля исходных данных

            self.name = ''
            self.cost = 0
            self.quantity = 1
            self.info = ''
            self.url = []
            self.incart = False
            self.paid = False

            self.importance = 0
            # "важность" товара, она же индекс в wccommon.ImportanceIcons;
            # 0 - "не важно/не указано", 1 и более - возрастающая важность

            #
            # следующие поля используются только UI и в файле не сохраняются!
            #

            # поля, которые вычисляются при вызове WishCalc.recalculate()
            # их значения могут зависеть от предыдущих по списку товаров!
            # вычисленные значения - целые положительные числа;
            # значение поля, равное 0, означает, что уже усё, денег достаточно
            # значение None означает "вычислить не удалось" и ошибкой не является

            # сумма (cost * quantity)
            self.sum = 0

            # недостающая сумма
            self.needCash = None

            # недостающая сумма с учётом предыдущих по списку товаров
            self.needTotal = None

            # доступная сумма
            self.availCash = None

            # кол-во месяцев на накопление
            self.needMonths = None

            # максимальное значение importance вложенных товаров
            self.childrenImportance = 0

            self.childrenSelected = False
            self.childrenInCart = False

        def clear(self):
            """Очистка полей данных"""

            self.name = ''
            self.cost = 0
            self.quantity = 1 # внимание! значение 0 - тоже верное!
            self.sum = 0
            self.info = ''
            self.url.clear()
            self.importance = 0
            self.incart = False
            self.paid = False

            self.childrenImportance = 0
            self.childSelected = False
            self.childInCart = False

        def calculate_sum(self):
            self.sum = self.cost * self.quantity

            """if self.cost > 0:
                self.sum = self.cost * self.quantity
            else:
                # т.к. cost м.б. -1
                self.sum = 0"""

        def get_data_from(self, other):
            self.name = other.name
            self.cost = other.cost
            self.quantity = other.quantity
            self.sum = other.sum

            self.info = other.info

            # патамушто список!
            self.url = other.url.copy()

            self.incart = other.incart
            self.paid = other.paid

            self.importance = other.importance

        def __repr__(self):
            # для отладки
            return '%s(name="%s", cost=%d, quantity=%d, sum=%d, info="%s", url=%s, importance=%d, incart=%s, paid=%s, needCash=%s, needTotal=%s, availCash=%s, needMonths=%s)' %\
                (self.__class__.__name__,
                 self.name, self.cost, self.quantity, self.sum,
                 self.info, repr(self.url),
                 self.importance, self.incart, self.paid,
                 self.needCash, self.needTotal, self.availCash, self.needMonths)

        def get_fields_dict(self):
            """Возвращает словарь с именами и значениями полей"""

            d = {self.NAME:self.name, self.COST:self.cost, self.QUANTITY:self.quantity}

            # необязательные поля кладём в словарь только при наличии "неумолчальных" значений
            # дабы JSON не распухал
            if self.info:
                d[self.INFO] = self.info

            if self.url:
                d[self.URL] = self.url

            if self.importance > 0:
                d[self.IMPORTANCE] = self.importance

            if self.incart:
                d[self.INCART] = self.incart

            if self.paid:
                d[self.PAID] = self.paid

            # поля sum и need* для сохранения не предназначены и в словарь не кладутся!

            return d

        def set_fields_dict(self, srcdict, __level=0):
            """Установка значений полей из словаря srcdict.
            __level - костыль для ограничения глубины дерева (и рекурсии)."""

            #if __level >= MAX_ITEM_LEVEL:
            #    raise OverflowError('слишком много уровней вложенных элементов')
            # отключено, т.к. я пока не знаю, как ограничить глубину
            # вложенности при drag'n'drop в UI, а без этого можно
            # в UI создать больше уровней, чем задано MAX_ITEM_LEVEL

            self.clear()

            self.name = get_dict_item(srcdict, self.NAME, str, rangecheck=lambda s: s != '')
            self.cost = get_dict_item(srcdict, self.COST, int) #lambda c: c >= -1)
            self.quantity = get_dict_item(srcdict, self.QUANTITY, int,
                rangecheck=lambda c: c >= 0, fallback=1, failifnokey=False)
            self.calculate_sum()

            self.info = get_dict_item(srcdict, self.INFO, str, fallback='')

            self.url.clear()
            _url = get_dict_item(srcdict, self.URL, str, list, fallback=[])

            # загрузка данных версии < 2.7.0
            if isinstance(_url, str):
                # начиная с версии 2.7.0 можно хранить несколько URL
                # в списке по ДВА элемента - URL и отображаемое имя (м.б. пустое)
                if _url:
                    self.url.append([_url, ''])
            elif isinstance(_url, list):
                for surl in _url:
                    if len(surl) != 2:
                        raise ValueError('неправильное количество полей элемента url')

                    for suf in surl:
                        if not isinstance(suf, str):
                            raise TypeError('неправильный тип поля элемента url')

                    if surl[0]:
                        #TODO а не надо ли ограничить максимальное кол-во URL?
                        self.url.append(surl)
            else:
                raise TypeError('неправильный тип элемента url')

            self.importance = get_dict_item(srcdict, self.IMPORTANCE, int, fallback=0)
            # принудительно вгоним в рамки
            if self.importance < IMPORTANCE_LEVEL_MIN:
                self.importance = IMPORTANCE_LEVEL_MIN
            elif self.importance > IMPORTANCE_LEVEL_MAX:
                self.importance = IMPORTANCE_LEVEL_MAX

            self.incart = get_dict_item(srcdict, self.INCART, bool, fallback=False)
            self.paid = get_dict_item(srcdict, self.PAID, bool, fallback=False)

    def __init__(self, filename):
        """Параметры:
        filename    - None или имя файла в формате JSON для загрузки/сохранения.

        Поля:
        filename, store     - см. параметры;
        exportFilename      - имя файла для экспорта (в CSV);
        exportHRHeaders     - булевское: True - человекочитаемые
                              заголовки таблицы;
        exportHRValues      - булевское: True - человекочитаемые значения
                              в ячейках таблицы;
        totalCash           - все имеющиеся в наличии средства;
        refillCash          - планируемая сумма ежемесячных пополнений;
        totalRemain         - расчётный остаток (в файле не хранится);
        comment             - краткое описание файла для отображения в UI
                              (в заголовке окна)."""

        self.filename = filename

        #
        self.exportFilename = 'wishcalc.csv' if not filename else '%s.csv' % os.path.splitext(filename)[0]

        #
        self.exportHRHeaders = False
        self.exportHRValues = False

        """Дабы не дублировать данные и не гонять их туда-сюда лишний раз,
        дерево объектов храним непосредственно в Gtk.TreeStore."""

        # при изменениях в wishcalc.ui - приводить в соответствие!
        self.store = Gtk.TreeStore(GObject.TYPE_PYOBJECT, GObject.TYPE_STRING,
            GObject.TYPE_STRING, GObject.TYPE_STRING,
            Pixbuf, GObject.TYPE_STRING, GObject.TYPE_STRING,
            GObject.TYPE_STRING, GObject.TYPE_STRING,
            Pixbuf,
            GObject.TYPE_BOOLEAN,
            Pixbuf,
            GObject.TYPE_BOOLEAN,
            )

        self.totalCash = 0
        self.refillCash = 0
        self.totalRemain = 0
        self.totalSelectedSum = 0
        self.totalSelectedCount = 0
        self.totalInCartSum = 0
        self.totalInCartCount = 0
        self.comment = ''

    def __str__(self):
        # для отладки
        return '%s: filename="%s", comment="%s", totalCash=%d, refillCash=%d, totalRemain=%d' %\
            (self.__class__.__name__,
            self.filename, self.comment,
            self.totalCash, self.refillCash, self.totalRemain)

    VAR_AVAIL = 'available'
    VAR_REFILL = 'refill'
    VAR_WISHLIST = 'wishlist'
    VAR_COMMENT = 'comment'

    def clear(self):
        """Очистка списка."""

        self.store.clear()

        self.totalCash = 0
        self.refillCash = 0
        self.totalRemain = 0

        self.comment = ''

    def load_subitems(self, parentitr, fromlist, level):
        """Загрузка данных в self.store.

        parentitr   - экземпляр Gtk.TreeIter (None для верхнего
                      уровня дерева);
        fromlist    - список словарей с полями элементов;
        level       - список целых (уровней вложенности) для отображения
                      сообщений об ошибках.

        Если parent == None - элементы добавляются в верхний уровень
        дерева, иначе - как дочерние относительно parent."""

        for ixitem, itemdict in enumerate(fromlist, 1):
            nextlevel = level + [ixitem]
            __val_error = lambda s: '%s элемента %s списка "%s"' %\
                (s, ':'.join(map(str, nextlevel)), self.VAR_WISHLIST)

            if not isinstance(itemdict, dict):
                raise ValueError(__val_error('неправильный тип'))

            try:
                item = self.Item()
                item.set_fields_dict(itemdict)
                itr = self.append_item(parentitr, item)

                # есть вложенные элементы?
                subitems = get_dict_item(itemdict, item.ITEMS, list, fallback=[])
                if subitems:
                    self.load_subitems(itr, subitems, nextlevel)
            except Exception as ex:
                raise ValueError(__val_error(str(ex)))

    def load_str(self, s):
        """Загрузка списка из строки.
        s - строка, которая должна содержать правильный JSON.
        В случае ошибок генерируются исключения."""

        self.clear()

        #
        # проверка на правильный формат
        #
        e_format = lambda s: 'несовместимый формат документа: %s' % s

        s = s.strip()
        if not s:
            raise ValueError(e_format('получена пустая строка'))

        srcdict = json.loads(s)

        if not isinstance(srcdict, dict):
            raise TypeError(e_format('корневой элемент JSON не является словарём'))

        wishList = get_dict_item(srcdict, self.VAR_WISHLIST, list,
            fallback=None, failifnokey=False)

        if wishList is None:
            raise ValueError(e_format('словарь JSON не содержит ключа "%s"' % self.VAR_WISHLIST))

        #
        # далее считаем, что нам подсунули таки б/м правильный WishCalc'овский JSON
        #

        self.comment = normalize_str(get_dict_item(srcdict, self.VAR_COMMENT, str, fallback=''))

        self.totalCash = get_dict_item(srcdict, self.VAR_AVAIL, int,
            rangecheck=lambda i: i >= 0, fallback=0)
        self.refillCash = get_dict_item(srcdict, self.VAR_REFILL, int,
            rangecheck=lambda i: i >= 0, fallback=0)

        self.totalRemain = self.totalCash # потом должно быть пересчитано!

        self.load_subitems(None, wishList, [])

    def load(self):
        """Загрузка списка.
        Если файл filename не существует, метод просто очищает поля.
        В случае ошибок при загрузке файла генерируются исключения."""

        if self.filename is None:
            raise ValueError('%s.load(): не указано имя файла' % self.__class__.__name__)

        self.clear()

        if not os.path.exists(self.filename):
            raise ValueError('файл "%s" не существует или недоступен' % self.filename)
            #return

        with open(self.filename, 'r', encoding=JSON_ENCODING) as f:
            return self.load_str(f.read())

    def get_item(self, itr):
        """Возвращает экземпляр WishCalc.Item (содержимое столбца
        WishCalc.COL_ITEM_OBJ из self.wishlist), соответствующий
        itr (экземпляру Gtk.TreeIter)."""

        return self.store.get_value(itr, WishCalc.COL_ITEM_OBJ)

    def replace_item(self, itr, item):
        """Замена элемента в TreeStore.

        itr         - экземпляр Gtk.TreeIter, позиция в TreeStore;
        item        - экземпляр WishCalc.Item.

        Внимание! В store сейчас кладём только ссылку на объект,
        прочие поля будут заполняться из UI и методом recalculate()."""

        self.store.set_value(itr, self.COL_ITEM_OBJ, item)

    def select_items(self, select):
        """Устанавливает значение столбца COL_SELECTED для всех элементов
        store значением select (булевским)."""

        def __select_items(parentitr):
            itr = self.store.iter_children(parentitr)
            while itr is not None:
                item = self.store.set_value(itr, self.COL_SELECTED, select)

                # "дети" есть? а если найду?
                if self.store.iter_n_children(itr) > 0:
                    __select_items(itr)

                itr = self.store.iter_next(itr)

        __select_items(None)

    def make_store_row(self, item):
        """Создаёт и возвращает кортеж со значениями полей для вставки/добавления
        в Gtk.TreeModel.
        Фактически в кортеж помещается только ссылка на объект, т.к.
        значения остальных полей изменяются из UI и вызовом метода
        recalculate().
        Метод же make_store_row() нужен для того, чтоб в ста местах
        программы не вспоминать количество и порядок полей TreeModel."""

        return (item, '', '', '', None, '', '', '', '', None, False, None, False)

    def append_item(self, parentitr, item):
        """Добавление нового элемента в TreeStore.
        Возвращает экземпляр Gtk.TreeIter, соответствующий новому
        элементу TreeStore.

        parentitr   - None или экземпляр Gtk.TreeIter; новый элемент
                      будет добавлен как дочерний относительно parentitr;
        item        - экземпляр WishCalc.Item.

        Внимание! В store сейчас кладём только ссылку на объект,
        прочие поля будут заполняться из UI и методом recalculate()."""

        row = self.make_store_row(item)

        return self.store.append(parentitr, row)

    def items_to_list(self, parentitr):
        """Проходит по TreeStore и возвращает список словарей
        с содержимым полей соответствующих экземпляров WishCalc.Item.

        parentitr   - экземпляр Gtk.TreeIter - указатель на элемент,
                      с которого начинать проход по списку;
                      None для первого элемента верхнего уровня дерева."""

        items = []

        itr = self.store.iter_children(parentitr)
        while itr is not None:
            item = self.store.get_value(itr, self.COL_ITEM_OBJ)
            itemdict = item.get_fields_dict()

            # "дети" есть? а если найду?
            if self.store.iter_n_children(itr) > 0:
                itemdict[self.Item.ITEMS] = self.items_to_list(itr)

            items.append(itemdict)
            itr = self.store.iter_next(itr)

        return items

    def save_str(self):
        """Возвращает строку, содержащую JSON с содержимым списка элементов
        TreeStore и прочих полей.
        В случае ошибок генерируются исключения."""

        tmpd = {self.VAR_AVAIL:self.totalCash,
            self.VAR_REFILL:self.refillCash,
            self.VAR_COMMENT:self.comment}

        # с элементами дерева - отдельная возня
        tmpd[self.VAR_WISHLIST] = self.items_to_list(None)

        return json.dumps(tmpd, ensure_ascii=False, indent='  ')

    def save_csv(self):
        """Сохраняет содержимое дерева элементов TreeStore и прочих полей
        в файле в формате JSON.
        Если в дереве есть помеченные элементы - экспортируются только
        они, иначе - всё содержимое дерева.
        В случае ошибок генерируются исключения."""

        if not self.exportFilename:
            raise ValueError('%s.save_csv(): не указано имя файла' % self.__class__.__name__)

        with open(self.exportFilename, 'w+') as f:
            csvw = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)

            csvw.writerow(map(lambda ep: ep.dispname if self.exportHRHeaders else ep.name,
                self.Item.CSV_FIELDS))

            def __export_node(fromitr, subsel):
                itr = self.store.iter_children(fromitr)

                while itr is not None:
                    item, selected = self.store.get(itr, self.COL_ITEM_OBJ, self.COL_SELECTED)

                    if selected or subsel or self.totalSelectedCount == 0:
                        rd = item.get_fields_dict()
                        erow = []

                        for ep in self.Item.CSV_FIELDS:
                            if ep.name not in rd:
                                es = ''
                            elif self.exportHRValues:
                                es = ep.tostr(rd[ep.name])
                            else:
                                es = str(rd[ep.name])

                            erow.append(es)

                        csvw.writerow(erow)

                    # "дети" есть? а если найду?
                    if self.store.iter_n_children(itr) > 0:
                        __export_node(itr, selected or subsel)

                    itr = self.store.iter_next(itr)

            __export_node(None, False)

    def save(self):
        """Сохраняет содержимое списка элементов TreeStore и прочих полей
        в файле в формате JSON.
        В случае ошибок генерируются исключения."""

        if not self.filename:
            raise ValueError('%s.save(): не указано имя файла' % self.__class__.__name__)

        tmps = self.save_str()

        # пытаемся сохранить "безопасно"
        tmpfn = self.filename + '.tmp'
        with open(tmpfn, 'w+', encoding=JSON_ENCODING) as f:
            f.write(tmps)

        if os.path.exists(self.filename):
            os.remove(self.filename)
        os.rename(tmpfn, self.filename)

    def __recalculate_items(self, parentitr, totalCash, refillCash, totalRemain):
        """Перерасчет.
        Производится проход по TreeStore для элементов, дочерних
        относительно parentitr (экземпляр Gtk.TreeIter, м.б. None для
        верхнего уровня дерева), для каждого элемента
        расчитываются значения полей item.needCash и item.needMonths
        на основе параметров totalCash, refillCash, totalRemain
        и значений полей элементов (при необходимости рекурсивно).

        Возвращает кортеж из следующих элементов:
        1й: суммарная цена элементов (с учётом количества),
        2й: суммарная цена за вычетом оплаченных товаров,
        3й: обновлённое значение totalRemain,
        4й: максимальное значение поля importance вложенных элементов
            (товаров),
        5й: суммарная стоимость помеченных чекбоксами в UI элементов;
        6й: количество помеченных элементов (без учёта вложенности, если помечен элемент верхнего уровня);
        7й: суммарная стоимость заказанных товаров;
        8й: количество заказанных товаров;
        9й: общее количество элементов на текущем и вложенных уровнях;
        10й: общее количество помеченных элементов на текущем и вложенных уровнях."""

        totalNeedCash = 0
        totalCost = 0 # общая сумма
        totalNeed = 0 # общая сумма за вычетом оплаченных
        maxImportance = 0
        totalSelectedSum = 0
        totalSelectedCount = 0
        totalInCartSum = 0
        totalInCartCount = 0

        totalItems = 0
        totalItemsChecked = 0

        itr = self.store.iter_children(parentitr)
        while itr is not None:
            item = self.store.get_value(itr, self.COL_ITEM_OBJ)
            itemsel = self.store.get_value(itr, self.COL_SELECTED)

            totalItems += 1

            # сбрасываем, дабы обновлялось!
            item.childrenImportance = 0

            # внимание! всё считаем на основе item.sum, а не item.cost!

            # "дети" есть? а если найду?
            nchildren = self.store.iter_n_children(itr)

            if nchildren == 0:
                # одиночный товар
                if itemsel:
                    totalSelectedSum += item.sum
                    totalSelectedCount += 1

                    totalItemsChecked += 1

                if item.incart:
                    totalInCartSum += item.sum
                    totalInCartCount += 1

                item.childSelected = False
                item.childInCart = False
            else:
                # не товар, а группа товаров! для них цена -
                # общая стоимость вложенных!
                item.cost, subNeed, subRemain, subImportance, subSelectedSum,\
                    subSelectedCount, subInCartSum, subInCartCount,\
                    subTotalItems, subTotalItemsChecked = self.__recalculate_items(itr,
                        totalCash, refillCash, totalRemain)
                item.calculate_sum()

                totalItems += subTotalItems
                # для этого счётчика учитывается и сам элемент, и вложенные!
                totalItemsChecked += subTotalItemsChecked

                item.childrenSelected = subSelectedCount > 0
                item.childrenInCart = subInCartCount > 0

                # внимание! если помечена группа товаров - учитываем общую сумму,
                # а не отдельные помеченные вложенные!
                if itemsel:
                    totalSelectedSum += item.sum
                    totalSelectedCount += 1
                    # для этого счётчика учитывается и сам элемент, и вложенные!
                    totalItemsChecked += 1
                elif subSelectedSum:
                    totalSelectedSum += subSelectedSum
                    totalSelectedCount += subSelectedCount

                # внимание! если заказана группа товаров - учитываем общую сумму,
                # а не отдельные заказанные вложенные!
                if item.incart:
                    totalInCartSum += item.sum
                    totalInCartCount += 1
                elif subInCartSum:
                    totalInCartSum += subInCartSum
                    totalInCartCount += subInCartCount

                if item.childrenImportance < subImportance:
                    item.childrenImportance = subImportance

                if item.importance == 0:
                    if maxImportance < subImportance:
                        maxImportance = subImportance

            if maxImportance < item.importance:
                maxImportance = item.importance

            totalCost += item.sum #!!!

            if item.sum <= 0:
                item.needCash = None
                item.availCash = None
                item.needMonths = None
            else:
                item.needCash = 0
                item.needTotal = 0
                item.needMonths = 0

                if not (item.incart and item.paid):
                    if totalRemain >= item.sum:
                        item.needCash = 0
                        item.availCash = item.sum
                        totalRemain -= item.sum
                    elif totalRemain > 0:
                        item.needCash = item.sum - totalRemain
                        item.availCash = totalRemain
                        totalRemain = 0
                    else:
                        item.needCash = item.sum
                        item.availCash = 0

                    if item.needCash:
                        totalNeedCash += item.needCash
                        item.needTotal = totalNeedCash

                        if refillCash > 0:
                            item.needMonths = self.need_months(totalNeedCash, refillCash)
                        else:
                            item.needMonths = None

            itr = self.store.iter_next(itr)

        # на всякий пожарный случай
        if totalRemain < 0:
            totalRemain = 0

        return (totalCost, totalNeed, totalRemain, maxImportance,
            totalSelectedSum, totalSelectedCount,
            totalInCartSum, totalInCartCount,
            totalItems, totalItemsChecked)

    def recalculate(self):
        """Перерасчет.
        Производится проход по списку items, для каждого элемента
        расчитываются значения полей item.needCash и item.needMonths
        на основе полей self.totalCash, self.refillCash и значений
        полей элементов).
        По завершению обновляется значение self.totalRemain.
        Возвращает кортеж из двух элементов:
        1й: общее количество элементов в дереве,
        2й: количество помеченных элементов."""

        __totalCost, __totalNeed, self.totalRemain, __importance, \
            self.totalSelectedSum, self.totalSelectedCount, \
            self.totalInCartSum, self.totalInCartCount,\
            totalItems, totalItemsChecked = self.__recalculate_items(None,
                self.totalCash, self.refillCash, self.totalCash)

        return (totalItems, totalItemsChecked)

    @staticmethod
    def need_months(needcash, refillcash):
        """Возвращает целое - кол-во полных месяцев, необходимых на накопление
        суммы needcash при ежемесячном пополнении кошелька refillcash."""

        m = needcash // refillcash
        if needcash % float(refillcash) > 0.0:
            m += 1

        return m

    def item_delete(self, itr, ispurchased):
        """Удаление товара из списка.

        itr         - позиция в Gtk.TreeStore (экземпляр Gtk.TreeIter),
        ispurchased - булевское значение: если True, товар считается
                      купленным, и его цена вычитается из суммы доступных
                      наличных.

        После вызова этого метода может понадобиться вызвать recalculate()."""

        item = self.get_item(itr)

        if ispurchased:
            if item.sum:
                self.totalCash -= item.sum
                if self.totalCash < 0:
                    self.totalCash = 0

        self.store.remove(itr)


def __debug_dump(wishcalc):
    wishcalc.select_items(True)

    wishcalc.recalculate()

    def __print_items(store, parentitr, indent):
        itr = store.iter_children(parentitr)

        sindent = ' ' * indent * 2

        while itr is not None:
            item = store.get_value(itr, WishCalc.COL_ITEM_OBJ)
            selected = store.get_value(itr, WishCalc.COL_SELECTED)
            nchildren = store.iter_n_children(itr)

            print('%s%s %s (%d, %d, %d), %d (%s)' % (sindent,
                '*' if nchildren == 0 else '>',
                item.name, item.cost, item.quantity, item.sum,
                item.importance, selected))

            if nchildren > 0:
                __print_items(store, itr, indent + 1)

            itr = store.iter_next(itr)

    __print_items(wishcalc.store, None, 0)

    #print(wishcalc.get_item(wishcalc.store.get_iter_first()))

    print('total: %d, remain: %d, refill: %d, in cart: %d (%d)' %\
        (wishcalc.totalCash, wishcalc.totalRemain, wishcalc.refillCash,
        wishcalc.totalInCartCount, wishcalc.totalInCartSum))


def __debug_export_csv(wishcalc):
    wishcalc.exportHRHeaders = True
    wishcalc.exportHRValues = True
    wishcalc.save_csv()


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    wishcalc = WishCalc(DEFAULT_FILENAME)
    wishcalc.load()

    #wishcalc.save()

    #__debug_dump(wishcalc)
    __debug_export_csv(wishcalc)
