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


MAX_ITEM_LEVEL = 3 # максимальный уровень вложенности WishCalc.Item
# в текущей версии не используется
# см. комментарий в WishCalc.Item.set_fields_dict()


def cost_str_to_int(s):
    """Преобразует строчное значение цены в целое число и возвращает его.
    В случае неправильного значения возвращает None."""

    try:
        s = normalize_str(s)
        if not s:
            return 0

        cost = int(round(float(s)))
        if cost < -1:
            cost = -1
        return cost

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

    COL_ITEM_OBJ, COL_NAME, COL_COST, COL_COST_ERROR, COL_NEEDED,\
    COL_NEED_ICON, COL_NEED_MONTHS, COL_INFO = range(8)

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
        INFO = 'info'
        URL = 'url'
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
            self.info = ''
            self.url = ''

            # поля, которые вычисляются при вызове WishCalc.recalculate()
            # их значения могут зависеть от предыдущих по списку товаров!
            # вычисленные значения - целые положительные числа;
            # значение поля, равное 0, означает, что уже усё, денег достаточно
            # значение None означает "вычислить не удалось" и ошибкой не является

            # недостающая сумма
            self.needCash = None

            # недостающая сумма с учётом предыдущих по списку товаров
            self.needTotal = None

            # доступная сумма
            self.availCash = None

            # кол-во месяцев на накопление
            self.needMonths = None

        def clear(self):
            """Очистка полей данных"""

            self.name = ''
            self.cost = 0
            self.info = ''
            self.url = ''

        def get_data_from(self, other):
            self.name = other.name
            self.cost = other.cost
            self.info = other.info
            self.url = other.url

        def __repr__(self):
            # для отладки
            return '%s(name="%s", cost=%d, info="%s", url="%s", needCash=%s, needTotal=%s, availCash=%s, needMonths=%s)' %\
                (self.__class__.__name__,
                 self.name, self.cost, self.info, self.url, self.needCash,
                 self.needTotal, self.availCash, self.needMonths)

        def get_fields_dict(self):
            """Возвращает словарь с именами и значениями полей"""

            d = {self.NAME:self.name, self.COST:self.cost}

            if self.info:
                d[self.INFO] = self.info

            if self.url:
                d[self.URL] = self.url

            # поля need* для сохранения не предназначены и в словарь не кладутся!

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
            self.info = get_dict_item(srcdict, self.INFO, str, fallback='')
            self.url = get_dict_item(srcdict, self.URL, str, fallback='')

    def __init__(self, filename):
        """Параметры:
        filename    - имя файла в формате JSON для загрузки/сохранения.

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
            GObject.TYPE_STRING, Pixbuf, GObject.TYPE_STRING,
            Pixbuf, GObject.TYPE_STRING, GObject.TYPE_STRING)

        self.totalCash = 0
        self.refillCash = 0
        self.totalRemain = 0
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

        s = s.strip()
        if not s:
            raise ValueError('получена пустая строка')

        srcdict = json.loads(s)

        if not isinstance(srcdict, dict):
            raise TypeError('корневой элемент JSON не является словарём')

        self.comment = normalize_str(get_dict_item(srcdict, self.VAR_COMMENT, str, None, ''))

        self.totalCash = get_dict_item(srcdict, self.VAR_AVAIL, int, lambda i: i >= 0, 0)
        self.refillCash = get_dict_item(srcdict, self.VAR_REFILL, int, lambda i: i >= 0, 0)

        self.totalRemain = self.totalCash # потом должно быть пересчитано!

        wishList = get_dict_item(srcdict, self.VAR_WISHLIST, list,
            fallback=None, failifnokey=False)

        if wishList is None:
            raise ValueError('словарь JSON не содержит ключа "%s"' % self.VAR_WISHLIST)

        self.load_subitems(None, wishList, [])

    def load(self):
        """Загрузка списка.
        Если файл filename не существует, метод просто очищает поля.
        В случае ошибок при загрузке файла генерируются исключения."""

        self.clear()

        if not os.path.exists(self.filename):
            return

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

    def append_item(self, parentitr, item):
        """Добавление нового элемента в TreeStore.
        Возвращает экземпляр Gtk.TreeIter, соответствующий новому
        элементу TreeStore.

        parentitr   - None или экземпляр Gtk.TreeIter; новый элемент
                      будет добавлен как дочерний относительно parentitr;
        item        - экземпляр WishCalc.Item.

        Внимание! В store сейчас кладём только ссылку на объект,
        прочие поля будут заполняться из UI и методом recalculate()."""

        return self.store.append(parentitr,
            (item, '', '', None, '', None, '', ''))

    def items_to_list(self, parentitr):
        """Проходит по TreeStore и возвращает список словарей
        с содержимым полей соответствующих экземпляров WishCalc.Item.

        parentitr   - экземпляр Gtk.TreeIter - указатель на элемент,
                      с которого начинать проход по списку;
                      None для первого элемента верхнего уровня дерева."""

        items = []

        itr = self.store.iter_children(parentitr)
        while itr is not None:
            item = self.store.get(itr, self.COL_ITEM_OBJ)[0]
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
            raise ValueError('%s.save(): поле filename не содержит значения' % self.__class__.__name__)
        else:
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

        Возвращает кортеж из двух элементов:
        1й: суммарная цена элементов,
        2й: обновлённое значение totalRemain."""

        totalNeedCash = 0
        totalCost = 0

        itr = self.store.iter_children(parentitr)
        while itr is not None:
            item = self.store.get(itr, self.COL_ITEM_OBJ)[0]

            # "дети" есть?
            if self.store.iter_n_children(itr) > 0:
                # не товар, а группа товаров
                item.cost, subRemain = self.__recalculate_items(itr,
                    totalCash, refillCash, totalRemain)

            #?    totalRemain += subRemain

            totalCost += item.cost

            if item.cost <= 0:
                item.needCash = None
                item.availCash = None
                item.needMonths = None
            else:
                if totalRemain >= item.cost:
                    item.needCash = 0
                    item.availCash = item.cost
                    totalRemain -= item.cost
                elif totalRemain > 0:
                    item.needCash = item.cost - totalRemain
                    item.availCash = totalRemain
                    totalRemain = 0
                else:
                    item.needCash = item.cost
                    item.availCash = 0

                if item.needCash:
                    totalNeedCash += item.needCash
                    item.needTotal = totalNeedCash

                    if refillCash > 0:
                        item.needMonths = totalNeedCash // refillCash
                        if totalNeedCash % float(refillCash) > 0.0:
                            item.needMonths += 1
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

        return (totalCost, totalRemain)

    def recalculate(self):
        """Перерасчет.
        Производится проход по списку items, для каждого элемента
        расчитываются значения полей item.needCash и item.needMonths
        на основе полей self.totalCash, self.refillCash и значений
        полей элементов).
        По завершению обновляется значение self.totalRemain."""

        __totalCost, self.totalRemain = self.__recalculate_items(None,
            self.totalCash, self.refillCash, self.totalCash)

    def item_delete(self, itr, ispurchased):
        """Удаление товара из списка.

        itr         - позиция в Gtk.TreeStore (экземпляр Gtk.TreeIter),
        ispurchased - булевское значение: если True, товар считается
                      купленным, и его цена вычитается из суммы доступных
                      наличных.

        После вызова этого метода может понадобиться вызвать recalculate()."""

        item = self.get_item(itr)

        if ispurchased:
            if item.cost:
                self.totalCash -= item.cost
                if self.totalCash < 0:
                    self.totalCash = 0

        self.store.remove(itr)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    wishcalc = WishCalc('wishlist.json')
    wishcalc.load()

    #wishcalc.load_str('{}')

    print(wishcalc.save_str())
    exit(0)

    wishcalc.recalculate()

    print(wishcalc.get_item(wishcalc.store.get_iter_first()))

    print('total: %d, remain: %d, refill: %d' % (wishcalc.totalCash, wishcalc.totalRemain, wishcalc.refillCash))

    #wishcalc.save()
