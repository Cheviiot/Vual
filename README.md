<p align="center">
  <img src="data/Vual.png" alt="Vual" width="96">
</p>

<h1 align="center">Vual</h1>

<p align="center">
  GTK4-приложение для запуска Cheat Engine в Steam-играх через Proton
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-green?style=flat-square" alt="GPL-3.0"></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/gtk-4-4a86cf?style=flat-square" alt="GTK 4">
  <img src="https://img.shields.io/badge/libadwaita-1-3584e4?style=flat-square" alt="Libadwaita 1">
</p>

## Что это

Vual показывает библиотеку установленных Steam-игр в виде сетки с обложками и позволяет в один клик запустить игру, включить для неё [protonhax](https://github.com/jcnils/protonhax) и открыть Cheat Engine прямо внутри Proton-контекста запущенной игры.

Приложение самостоятельно скачивает и распаковывает Cheat Engine, управляет protonhax, настраивает тему Wine для всех Proton-префиксов и поддерживает русский язык — как собственного интерфейса, так и Cheat Engine.

## Возможности

| | |
|---|---|
| 🎮 **Библиотека** | Сетка игр с обложками из Steam CDN, поиск, сортировка по имени и статусу |
| ▶️ **Запуск** | Запуск игры через Steam URI, автоматическое подключение CE к запущенной Proton-игре |
| 🔧 **protonhax** | Переключатель launch options для каждой игры и массовое включение/отключение |
| 📦 **Cheat Engine** | Скачивание с cheatengine.org, распаковка через Wine из Proton, тестовый запуск |
| 🎨 **Тема Wine** | Тёмная и светлая тема для всех Proton-префиксов разом |
| 🌐 **Локализация** | Язык приложения (EN/RU), язык CE, установка русской локализации CE |
| ⚙️ **Настройки** | Путь к Steam, шаблон LaunchOptions, regex-исключения, размер плитки |

## Установка

### Из исходников

```bash
git clone https://github.com/Cheviiot/vual.git
cd vual
./vual
```

### Stapler (ALT Linux)

```bash
stplr repo add lumenara https://github.com/Cheviiot/Lumenara
stplr refresh && stplr install vual
```

<details>
<summary><strong>Зависимости</strong></summary>

| Дистрибутив | Команда |
|---|---|
| ALT Linux | `apt-get install python3-module-pygobject3 libgtk4 libadwaita` |
| Fedora | `dnf install python3-gobject gtk4 libadwaita` |
| Arch | `pacman -S python-gobject gtk4 libadwaita` |
| Debian / Ubuntu | `apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1` |

Также необходим **Proton** (установленный через Steam) — для распаковки CE и работы protonhax.

</details>

## Быстрый старт

1. Запустите `./vual`
2. Откройте настройки (☰ → Настройки)
3. На вкладке **Cheat Engine** скачайте и распакуйте CE
4. Установите **protonhax** если он ещё не установлен
5. Включите переключатель у нужной игры — Vual пропишет launch options
6. Нажмите ▶ у игры — после запуска CE откроется автоматически

## Структура данных

```
~/.config/vual/
└── config.json              # Настройки приложения

~/.local/share/vual/
├── cheatengine/             # Установленный Cheat Engine
├── bin/protonhax            # Управляемый скрипт protonhax
└── wine_prefix/             # Префикс Wine для тестового запуска CE

~/.cache/vual/
└── covers/                  # Кэш обложек Steam
```

## Участие в разработке

> **Это личный проект.** Vual создаётся одним человеком для собственного использования при помощи ИИ.

Код полностью открыт. Если хотите помочь — Pull Request и Issue приветствуются: исправление ошибок, новые функции, переводы, плагины.

## Лицензия

[GPL-3.0-or-later](LICENSE)
