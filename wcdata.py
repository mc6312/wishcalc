#!/usr/bin/env python
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


def get_dict_item(fromdict, vname, vtype, rangecheck=None, fallback=None):
    """Берёт из словаря fromdict значение поля vname, проверяет тип
    и правильность значения.
    В случае успеха возвращает полученное значение, иначе генерирует исключение.

    rangecheck  - None или функция проверки диапазона значений;
                  должна возвращать булевское значение,
    fallback    - значение по умолчанию или None;
                  если не указано - то при отсутствии поля в словаре
                  генерируется исключение, иначе функция возвращает
                  значение fallback."""

    if vname not in fromdict:
        if fallback is not None:
            return fallback

        raise ValueError('отсутствует поле "%s"' % vname)

    v = fromdict[vname]
    if not isinstance(v, vtype):
        raise TypeError('неправильный тип поля "%s"' % vname)

    if callable(rangecheck):
        if not rangecheck(v):
            raise ValueError('значение поля "%s" вне допустимого диапазона' % vname)

    return v


class WishCalc():
    class Item():
        NAME = 'name'
        COST = 'cost'
        INFO = 'info'
        URL = 'url'

        @staticmethod
        def new_from_dict(d):
            return WishCalc.Item(get_dict_item(d, WishCalc.Item.NAME, str, lambda s: s != ''),
                get_dict_item(d, WishCalc.Item.COST, int, lambda c: c >= -1),
                get_dict_item(d, WishCalc.Item.INFO, str, fallback=''),
                get_dict_item(d, WishCalc.Item.URL, str, fallback=''))

        @staticmethod
        def new_copy(other):
            """other - экземпляр WishCalc.Item"""

            return WishCalc.Item(other.name, other.cost, other.info, other.url)

        def __init__(self, name='', cost=0, info='', url=''):
            # поля исходных данных

            self.name = name
            self.cost = cost
            self.info = info
            self.url = url

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

        def __str__(self):
            # для отладки
            return '(name="%s", cost=%d, info="%s", url="%s", needCash=%s, needTotal=%s, availCash=%s, needMonths=%s)' %\
                (self.name, self.cost, self.info, self.url, self.needCash, self.needTotal, self.availCash, self.needMonths)

        def get_fields_dict(self):
            """Возвращает словарь с именами и значениями полей"""

            d = {self.NAME:self.name, self.COST:self.cost}

            if self.info:
                d[self.INFO] = self.info

            if self.url:
                d[self.URL] = self.url

            # поля need* для сохранения не предназначены и в словарь не кладутся!

            return d

    def __init__(self, filename):
        self.filename = filename

        # все имеющиеся в наличии средства
        self.totalCash = 0

        # планируемая сумма ежемесячных пополнений
        self.refillCash = 0

        # расчётный остаток
        self.totalRemain = 0

        # краткое описание копилки для отображения в заголовке окна, например
        self.comment = ''

        # список экземпляров WishCalc.Item
        self.items = []

    def __str__(self):
        # для отладки
        return '%s: filename="%s", comment="%s", totalCash=%d, refillCash=%d, totalRemain=%d, items=[%s]' %\
            (self.__class__.__name__,
            self.filename, self.comment,
            self.totalCash, self.refillCash, self.totalRemain,
            ', '.join(map(str, self.items)))

    VAR_AVAIL = 'available'
    VAR_REFILL = 'refill'
    VAR_WISHLIST = 'wishlist'
    VAR_COMMENT = 'comment'
    JSON_ENCODING = 'utf-8'

    def load(self):
        """Загрузка списка"""

        self.items.clear()

        self.totalCash = 0
        self.refillCash = 0
        self.totalRemain = 0

        self.comment = ''

        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding=self.JSON_ENCODING) as f:
                d = json.load(f)

            self.comment = normalize_str(get_dict_item(d, self.VAR_COMMENT, str, None, ''))

            self.totalCash = get_dict_item(d, self.VAR_AVAIL, int, lambda i: i >= 0, 0)
            self.refillCash = get_dict_item(d, self.VAR_REFILL, int, lambda i: i >= 0, 0)

            wishList = get_dict_item(d, self.VAR_WISHLIST, list, fallback=[])

            self.totalRemain = self.totalCash # потом должно быть пересчитано!

            for ixitem, item in enumerate(wishList, 1):
                __val_error = lambda s: '%s элемента %d списка "%s"' % (s, ixitem, self.VAR_WISHLIST)

                if not isinstance(item, dict):
                    raise ValueError(__val_error('неправильный тип'))

                try:
                    self.items.append(self.Item.new_from_dict(item))
                except Exception as ex:
                    raise ValueError(__val_error(str(ex)))

    def save(self):
        if self.filename:
            tmpd = {self.VAR_AVAIL:self.totalCash,
                self.VAR_REFILL:self.refillCash,
                self.VAR_COMMENT:self.comment,
                self.VAR_WISHLIST:[ia for ia in map(lambda itm: itm.get_fields_dict(), self.items)]}

            tmpfn = self.filename + '.tmp'

            with open(tmpfn, 'w+', encoding=self.JSON_ENCODING) as f:
                json.dump(tmpd, f, ensure_ascii=False, indent='  ')

            if os.path.exists(self.filename):
                os.remove(self.filename)
            os.rename(tmpfn, self.filename)

    def recalculate(self):
        """Перерасчет.
        Производится проход по списку items, для каждого элемента
        расчитываются значения полей item.needCash и item.needMonths
        на основе полей self.totalCash, self.refillCash и значений
        полей элементов).
        По завершению обновляется значение self.totalRemain."""

        self.totalRemain = self.totalCash

        totalNeedCash = 0

        for item in self.items:
            if item.cost <= 0:
                item.needCash = None
                item.availCash = None
                item.needMonths = None
            else:
                if self.totalRemain >= item.cost:
                    item.needCash = 0
                    item.availCash = item.cost
                    self.totalRemain -= item.cost
                elif self.totalRemain > 0:
                    item.needCash = item.cost - self.totalRemain
                    item.availCash = self.totalRemain
                    self.totalRemain = 0
                else:
                    item.needCash = item.cost
                    item.availCash = 0

                if item.needCash:
                    totalNeedCash += item.needCash
                    item.needTotal = totalNeedCash

                    if self.refillCash > 0:
                        item.needMonths = totalNeedCash // self.refillCash
                        if totalNeedCash % float(self.refillCash) > 0.0:
                            item.needMonths += 1
                    else:
                        item.needMonths = None
                else:
                    item.needCash = 0
                    item.needTotal = 0
                    item.needMonths = 0

        # на всякий пожарный случай
        if self.totalRemain < 0:
            self.totalRemain = 0

    def item_delete(self, ix, ispurchased):
        """Удаление товара из списка.

        ix          - позиция в списке (целое),
        ispurchased - булевское значение: если True, товар считается
                      купленным, и его цена вычитается из суммы доступных
                      наличных.

        После вызова этого метода может понадобиться вызвать recalculate()."""

        item = self.items[ix]

        if ispurchased:
            if item.cost:
                self.totalCash -= item.cost
                if self.totalCash < 0:
                    self.totalCash = 0

        del self.items[ix]

    def move_item_updown(self, ix, down):
        """Перемещение товара на одну позицию по списку.

        ix      - целое, позиция в списке
        down    - булевское, кудой двигать - вверх или вниз.

        Если список изменится, возвращает целое число - новую позицию
        в списке, иначе возвращает None.

        В случае успешного изменения может понадобиться потом вызвать
        метод recalculate()."""

        count = len(self.items)
        if count < 2:
            return None

        ixnew = ix + 1 if down else ix - 1

        if ixnew >= 0 and ixnew <= count - 1:
            t = self.items[ix]
            self.items[ix] = self.items[ixnew]
            self.items[ixnew] = t

            return ixnew
        else:
            return None

    def move_item_topbottom(self, ix, tobottom):
        """Перемещение товара в начало или конец списка.

        ix          - целое, позиция в списке
        tobottom    - булевское, кудой двигать - в начало или в конец.

        Если список изменится, возвращает целое число - новую позицию
        в списке, иначе возвращает None.

        В случае успешного изменения может понадобиться потом вызвать
        метод recalculate()."""

        count = len(self.items)
        if count < 2:
            return None

        ixnew = count - 1 if tobottom else 0

        if ixnew == ix:
            return None

        t = self.items[ix]
        del self.items[ix]

        if tobottom:
            self.items.append(t)
        else:
            self.items.insert(ixnew, t)

        return ixnew



if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    wishcalc = WishCalc('wishlist.json')
    wishcalc.load()

    wishcalc.recalculate()

    for item in wishcalc.items:
        print(item)

    print('total: %d, remain: %d, refill: %d' % (wishcalc.totalCash, wishcalc.totalRemain, wishcalc.refillCash))

    #wishcalc.save()
