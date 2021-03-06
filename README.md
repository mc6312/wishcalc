# WishCalc

## ВВЕДЕНИЕ

1. Сия программа является свободным ПО под лицензией [GPL v3](https://www.gnu.org/licenses/gpl.html).
2. Программа создана и дорабатывается автором исключительно ради собственных
   нужд и развлечения, а также в соответствии с его представлениями об эргономике
   и функциональности.
3. Автор всех видал в гробу и ничего никому не должен, кроме явно
   прописанного в GPL.
4. Несмотря на вышеуказанное, автор совершенно не против, если программа
   подойдёт кому-то еще, кроме тех, под кем прогорит сиденье из-за пунктов
   с 1 по 3.

## НАЗНАЧЕНИЕ

Финансовый калькулятор загребущего нищеброда для надзора за копилкой.

Умеет хранить список желаемых приобретений с подсчётом сроков накопления
на основе указанной суммы в копилке и сумм предполагаемого ежемесячного
пополнения копилки.

## ЧТО ТРЕБУЕТ ДЛЯ РАБОТЫ

- Linux (или другую ОС, в которой заработает нижеперечисленное, напр.
  MS Windows с установленным MSYS2)
- Python 3.6 или новее
- GTK 3.20 или новее и соотв. модули gi.repository

## ФАЙЛЫ ДАННЫХ

Программа хранит список желаемых приобретений в файле формата JSON.

Имя файла может быть указано в командной строке.

Если файл не указан - программа ищет файл с именем "wishlist.json",
сначала в текущем каталоге, а затем в том же каталоге, где расположена
программа; если файл "wishlist.json" отсутствует - программа запускается
с пустым списком товаров.
