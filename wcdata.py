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

from gi.repository import Gtk, GObject
from gi.repository.GdkPixbuf import Pixbuf

from wcconfig import JSON_ENCODING
from wccommon import *


MAX_ITEM_LEVEL = 3 # максимальный уровень вложенности WishCalc.Item
# в текущей версии не используется
# см. комментарий в WishCalc.Item.set_fields_dict()


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


def get_dict_item(fromdict, vname, vtype, rangecheck=None, fallback=None, failifnokey=True):
    """Берёт из словаря fromdict значение поля vname, проверяет тип
    и правильность значения.
    В случае успеха возвращает полученное значение, иначе генерирует исключение.

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
    if not isinstance(v, vtype):
        raise TypeError('неправильный тип поля "%s"' % vname)

    if callable(rangecheck):
        if not rangecheck(v):
            raise ValueError('значение поля "%s" вне допустимого диапазона' % vname)

    return v


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
            self.url = ''
            self.incart = False
            self.paid = False

            self.importance = 0
            # "важность" товара, она же индекс в wccommon.ImportanceIcons.icons;
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
            self.url = ''
            self.importance = 0
            self.incart = False
            self.paid = False

            self.childrenImportance = 0
            self.childSelected = False
            self.childInCart = False

        def calculate_sum(self):
            if self.cost > 0:
                self.sum = self.cost * self.quantity
            else:
                # т.к. cost м.б. -1
                self.sum = 0

        def get_data_from(self, other):
            self.name = other.name
            self.cost = other.cost
            self.quantity = other.quantity
            self.sum = other.sum

            self.info = other.info
            self.url = other.url

            self.incart = other.incart
            self.paid = other.paid

            self.importance = other.importance

        def __repr__(self):
            # для отладки
            return '%s(name="%s", cost=%d, quantity=%d, sum=%d, info="%s", url="%s", importance=%d, incart=%s, paid=%s, needCash=%s, needTotal=%s, availCash=%s, needMonths=%s)' %\
                (self.__class__.__name__,
                 self.name, self.cost, self.quantity, self.sum,
                 self.info, self.url,
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

            self.name = get_dict_item(srcdict, self.NAME, str, lambda s: s != '')
            self.cost = get_dict_item(srcdict, self.COST, int, lambda c: c >= -1)
            self.quantity = get_dict_item(srcdict, self.QUANTITY, int, lambda c: c >= 0, 1, False)
            self.calculate_sum()

            self.info = get_dict_item(srcdict, self.INFO, str, fallback='')
            self.url = get_dict_item(srcdict, self.URL, str, fallback='')

            self.importance = get_dict_item(srcdict, self.IMPORTANCE, int, fallback=0)
            # принудительно вгоним в рамки
            if self.importance < ImportanceIcons.MIN:
                self.importance = ImportanceIcons.MIN
            elif self.importance > ImportanceIcons.MAX:
                self.importance = ImportanceIcons.MAX

            self.incart = get_dict_item(srcdict, self.INCART, bool, fallback=False)
            self.paid = get_dict_item(srcdict, self.PAID, bool, fallback=False)

    def __init__(self, filename):
        """Параметры:
        filename    - None или имя файла в формате JSON для загрузки/сохранения.

        Поля:
        filename, store - см. параметры;
        totalCash   - все имеющиеся в наличии средства;
        refillCash  - планируемая сумма ежемесячных пополнений;
        totalRemain - расчётный остаток (в файле не хранится);
        comment     - краткое описание файла для отображения в UI
                      (в заголовке окна)."""

        self.filename = filename

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

        self.comment = normalize_str(get_dict_item(srcdict, self.VAR_COMMENT, str, None, ''))

        self.totalCash = get_dict_item(srcdict, self.VAR_AVAIL, int, lambda i: i >= 0, 0)
        self.refillCash = get_dict_item(srcdict, self.VAR_REFILL, int, lambda i: i >= 0, 0)

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

        Возвращает кортеж из семи элементов:
        1й: суммарная цена элементов (с учётом количества),
        2й: обновлённое значение totalRemain,
        3й: максимальное значение поля importance вложенных элементов
            (товаров),
        4й: суммарная стоимость помеченных чекбоксами в UI элементов;
        5й: количество помеченных элементов;
        6й: суммарная стоимость заказанных товаров;
        7й: количество заказанных товаров."""

        totalNeedCash = 0
        totalCost = 0
        maxImportance = 0
        totalSelectedSum = 0
        totalSelectedCount = 0
        totalInCartSum = 0
        totalInCartCount = 0

        itr = self.store.iter_children(parentitr)
        while itr is not None:
            item = self.store.get_value(itr, self.COL_ITEM_OBJ)
            itemsel = self.store.get_value(itr, self.COL_SELECTED)

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
                if item.incart:
                    totalInCartSum += item.sum
                    totalInCartCount += 1

                item.childSelected = False
                item.childInCart = False
            else:
                # не товар, а группа товаров! для них цена -
                # общая стоимость вложенных!
                item.cost, subRemain, subImportance, subSelectedSum, subSelectedCount, subInCartSum, subInCartCount = self.__recalculate_items(itr,
                    totalCash, refillCash, totalRemain)
                item.calculate_sum()

                item.childrenSelected = subSelectedCount > 0
                item.childrenInCart = subInCartCount > 0

                # внимание! если помечена группа товаров - учитываем общую сумму,
                # а не отдельные помеченные вложенные!
                if itemsel:
                    totalSelectedSum += item.sum
                    totalSelectedCount += 1
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
                else:
                    item.needCash = 0
                    item.needTotal = 0
                    item.needMonths = 0

            itr = self.store.iter_next(itr)

        # на всякий пожарный случай
        if totalRemain < 0:
            totalRemain = 0

        return (totalCost, totalRemain, maxImportance,
            totalSelectedSum, totalSelectedCount,
            totalInCartSum, totalInCartCount)

    def recalculate(self):
        """Перерасчет.
        Производится проход по списку items, для каждого элемента
        расчитываются значения полей item.needCash и item.needMonths
        на основе полей self.totalCash, self.refillCash и значений
        полей элементов).
        По завершению обновляется значение self.totalRemain."""

        __totalCost, self.totalRemain, __importance, \
        self.totalSelectedSum, self.totalSelectedCount , \
        self.totalInCartSum, self.totalInCartCount = self.__recalculate_items(None,
            self.totalCash, self.refillCash, self.totalCash)

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


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    wishcalc = WishCalc(DEFAULT_FILENAME)
    wishcalc.load()

    #wishcalc.load_str('{}')

    #print(wishcalc.save_str())
    #exit(0)

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

    #wishcalc.save()
