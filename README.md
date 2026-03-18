<p align="center">
  <img src="data/Vual.png" alt="Vual" width="128">
</p>

<h1 align="center">Vual</h1>

<p align="center">
  Запуск Cheat Engine для Steam-игр через Proton
</p>

<p align="center">
  <img src="https://img.shields.io/badge/GTK-4-4a86cf?style=flat-square" alt="GTK 4">
  <img src="https://img.shields.io/badge/Libadwaita-1-3584e4?style=flat-square" alt="Libadwaita">
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square" alt="Python 3.11+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-green?style=flat-square" alt="GPL-3.0"></a>
</p>


## О проекте

Vual — приложение для запуска Cheat Engine в Steam-играх, работающих через Proton.
Показывает библиотеку Steam, управляет protonhax и launch options, скачивает и
распаковывает CE автоматически, запускает его в нужном Wine-префиксе — всё из одного
окна.

## Возможности

- **Сетка игр** — обложки из Steam CDN, поиск в реальном времени, сортировка по имени или статусу
- **Запуск одним кликом** — игра стартует через Steam, CE подключается к нужному Proton-префиксу
- **Таблицы CE** — привязка .CT-файла к игре, автоматическое открытие вместе с CE
- **protonhax** — автоматическая установка, переключатель launch options для каждой игры, массовое вкл/выкл
- **Установка CE** — скачивание с cheatengine.org, распаковка через Wine из Proton
- **Тема Wine** — тёмная или светлая тема для всех Proton-префиксов разом
- **Локализация** — интерфейс EN/RU, язык CE, установка русской локализации из офиц. репозитория CE
- **Прозрачность окна** — полупрозрачный фон в стиле frosted glass
- **Гайд** — встроенная страница быстрого старта при первом запуске и из меню

## Установка

### Stapler

```
stplr repo add lumenara https://github.com/Cheviiot/Lumenara.git
stplr refresh && stplr install vual
```

### Из исходников

```
git clone https://github.com/Cheviiot/vual.git
cd vual
./vual
```

<details>
<summary><strong>Зависимости</strong></summary>

| Дистрибутив | Команда |
|---|---|
| ALT Linux | `apt-get install python3-module-pygobject3 libgtk4 libadwaita python3-module-requests` |
| Fedora | `dnf install python3-gobject gtk4 libadwaita python3-requests` |
| Arch | `pacman -S python-gobject gtk4 libadwaita python-requests` |
| Debian / Ubuntu | `apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests` |

Также нужен **Proton** (через Steam) — для распаковки CE и работы protonhax.

</details>

## Использование

```
./vual
```

1. При первом запуске откроется встроенный гайд
2. Перейди в **Настройки → Cheat Engine** — скачай и распакуй CE
3. Установи **protonhax** там же
4. Включи переключатель у нужной игры — Vual пропишет launch options
5. Нажми ▶ — игра запустится, CE откроется автоматически

## Управление

| | |
|---|---|
| Запуск CE | Клик по кнопке ▶ на плитке игры |
| Поиск | Клик по полю поиска в заголовке |
| Привязать таблицу | Правая кнопка мыши → Assign Table |
| Вкл/выкл protonhax | Переключатель на плитке игры |
| Массовое вкл/выкл | Кнопки Enable All / Disable All |
| Сортировка | Меню сортировки в заголовке |
| Настройки | Главное меню → Preferences |
| Гайд | Главное меню → Guide |

## Настройки

| | | По умолчанию |
|---|---|---|
| Тема | Системная / Светлая / Тёмная | Системная |
| Язык | Авто / English / Русский | Авто |
| Размер плиток | Small / Medium / Large | Medium |
| Сортировка | По имени / По статусу | По имени |
| Прозрачность окна | вкл / выкл | выкл |
| Тема Wine | Тёмная / Светлая | — |
| Язык CE | EN / RU | — |

## Данные

`~/.config/vual/`

| | |
|---|---|
| config.json | Настройки |

`~/.local/share/vual/`

| | |
|---|---|
| cheatengine/ | Cheat Engine |
| bin/protonhax | protonhax |
| tables/ | .CT-таблицы и привязки |
| wine_prefix/ | Wine-префикс для тестового запуска CE |

`~/.cache/vual/`

| | |
|---|---|
| covers/ | Кэш обложек Steam |

## Участие в разработке

> Это личный проект. Vual создаётся одним человеком для собственного использования при помощи ИИ.

Код полностью открыт. Если хотите помочь — Pull Request и Issue приветствуются:
исправление ошибок, новые функции, переводы.

## Лицензия

[GPL-3.0-or-later](LICENSE)
