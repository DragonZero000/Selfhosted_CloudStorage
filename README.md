# Selfhosted CloudStorage

Простое self-hosted облачное хранилище файлов — свой аналог Google Drive/Dropbox,
который разворачивается одной командой на своём сервере или VPS.

- **Backend:** FastAPI (Python) + JWT-авторизация (argon2)
- **База данных:** PostgreSQL
- **Хранилище файлов:** MinIO (S3-совместимое)
- **Frontend:** React (Vite) + nginx
- **Прод:** Caddy (автоматический HTTPS по домену)

## Возможности

- Регистрация и вход по логину/паролю (JWT)
- Загрузка, скачивание, переименование и удаление файлов
- Генерация временных ссылок для шаринга файлов (presigned URL, 24 часа)
- Лимиты хранилища на пользователя
- Мультиязычный интерфейс (RU/EN), светлая/тёмная тема

## Архитектура

```
Браузер
  │
  ▼
[Caddy / nginx]  ── статика + прокси /api → backend
  │
  ├──▶ [Frontend: React / nginx]
  │
  ├──▶ [Backend: FastAPI]
  │        ├──▶ [PostgreSQL]  — пользователи, метаданные файлов
  │        └──▶ [MinIO]       — сами файлы (S3 API)
```

## Требования

- Linux-сервер (Ubuntu/Debian рекомендуется) или локальная машина с Docker
- [Docker](https://docs.docker.com/engine/install/) и Docker Compose plugin
- Для прод-режима с HTTPS: домен, указывающий A-записью на IP сервера, и открытые порты 80/443

## Быстрый старт (автоматическая установка)

Самый простой способ — запустить установочный скрипт. Он сам спросит нужные
параметры, сгенерирует `.env`, при необходимости установит Docker и поднимет проект.

```bash
git clone <адрес-этого-репозитория>
cd Selfhosted_CloudStorage
chmod +x install.sh
./install.sh
```

Скрипт спросит:

1. **Режим установки** — локальный (без HTTPS, доступ по `http://IP` или `http://localhost`)
   или production (с доменом и автоматическим HTTPS через Caddy/Let's Encrypt).
2. **Домен** (только для production-режима) — например `cloud.example.com`.
3. **Логин/пароль для PostgreSQL** и **ключи доступа MinIO** — можно сгенерировать
   автоматически (по умолчанию) или ввести свои.
4. **Публичный URL/IP сервера** (для локального режима) — нужен, чтобы ссылки на
   скачивание файлов работали в браузере, а не только внутри Docker-сети.

После ответа на вопросы скрипт сам:

- сгенерирует надёжный `SECRET_KEY` (`openssl rand -hex 32`);
- создаст файл `.env` со всеми настройками;
- в production-режиме пропишет ваш домен в `Caddyfile`;
- соберёт и запустит контейнеры (`docker compose up -d --build`);
- дождётся готовности сервисов и покажет ссылку для входа.

## Установка вручную

Если не хотите использовать скрипт:

1. Отредактируйте `.env` (файл уже присутствует в репозитории) и заполните:

    ```env
    POSTGRES_USER=cloudstorage
    POSTGRES_PASSWORD=надёжный_пароль
    POSTGRES_DB=appdb

    MINIO_ACCESS_KEY=надёжный_логин
    MINIO_SECRET_KEY=надёжный_пароль

    S3_BUCKET=cloudstorage

    # Сгенерировать: openssl rand -hex 32
    SECRET_KEY=сгенерированный_ключ

    # Публичный адрес сервера (домен или IP), доступный из браузера
    MINIO_PUBLIC_URL=http://ВАШ_IP_ИЛИ_ДОМЕН:9000
    ```

2. **Локальный запуск** (без HTTPS, для разработки/локальной сети):

    ```bash
    docker compose up -d --build
    ```

    Приложение будет доступно на `http://localhost` (порт 80).

3. **Production-запуск** (с доменом и HTTPS через Caddy):

   Отредактируйте `Caddyfile`, указав свой домен вместо примера в первой строке:

    ```
    cloud.example.com {
        ...
    }
    ```

   Затем запустите:

    ```bash
    docker compose -f docker-compose.prod.yml up -d --build
    ```

   Caddy автоматически получит и продлит TLS-сертификат Let's Encrypt для указанного
   домена, приложение будет доступно на `https://ваш-домен`.

## Запуск тестов (backend)

Backend-часть проекта покрыта unit-тестами. Для запуска:

```bash
cd backend
pip install -r requirements.txt -r requirements-test.txt
pytest
```

Или с использованием Docker:

```bash
docker compose exec backend python -m pytest
```

## Управление пользователями (db.py CLI)

По умолчанию у новых пользователей лимит хранилища равен `0` — загрузка файлов
заблокирована, пока администратор не выдаст лимит вручную. Для этого в `db.py`
есть встроенная интерактивная консоль администратора.

Запустите её внутри уже работающего контейнера backend:

```bash
docker compose exec backend python db.py
```

(для production-режима: `docker compose -f docker-compose.prod.yml exec backend python db.py`)

Откроется интерактивный режим с командами:

| Команда     | Действие                                                              |
|-------------|-------------------------------------------------------------------------|
| `get_user`  | Показать одного пользователя (логин, использовано/лимит места, дата создания) |
| `get_users` | Показать всех пользователей и их лимиты                                |
| `add_user`  | Создать пользователя вручную (логин, пароль, лимит в байтах)           |
| `del_user`  | Удалить пользователя (с подтверждением)                                |
| `set_limit` | Изменить лимит хранилища пользователя в байтах (например, `1073741824` = 1 GB) |
| `exit`      | Выйти из консоли                                                        |

Пример — выдать пользователю `ivan` лимит в 5 GB:

```
$ docker compose exec backend python db.py
Commands: get_user | get_users | add_user | del_user | set_limit | exit
> set_limit
Login: ivan
New limit in bytes (0 = block, e.g. 1073741824 = 1GB): 5368709120
Updated
> exit
```

## Управление

```bash
# Посмотреть логи
docker compose logs -f

# Остановить
docker compose down

# Остановить и удалить все данные (БД и файлы!)
docker compose down -v

# Обновить после изменений в коде
docker compose up -d --build
```

Для production-режима используйте те же команды с флагом `-f docker-compose.prod.yml`.

## Структура проекта

```
.
├── backend/                        # FastAPI-приложение
│   ├── CloudStorage.py             # точка входа (uvicorn CloudStorage:app)
│   ├── authorization.py            # регистрация, вход, JWT, FastAPI app + CORS
│   ├── storage.py                  # загрузка/скачивание/переименование/шаринг файлов (роуты /files)
│   ├── db.py                       # модели SQLAlchemy (User, File) + CRUD + интерактивный CLI (см. ниже)
│   ├── CloudStorage-postgres.sql   # справочная SQL-схема (реальные таблицы создаёт db.py при старте)
│   ├── requirements.txt            # python-зависимости backend
│   ├── requirements-test.txt       # зависимости для тестирования (pytest, httpx и др.)
│   ├── pytest.ini                  # конфигурация pytest
│   ├── conftest.py                 # общие fixtures для тестов
│   ├── test_authorization.py       # unit-тесты авторизации
│   ├── test_db.py                  # unit-тесты базы данных
│   ├── test_storage.py             # unit-тесты хранения файлов
│   ├── test_cloudstorage.py        # unit-тесты основного приложения
│   ├── Dockerfile                  # сборка образа backend
│   └── dockerignore
│
├── frontend/                       # React SPA (Vite + bun)
│   ├── src/
│   │   ├── App.jsx                 # корневой компонент, роутинг
│   │   ├── main.jsx                # точка входа React
│   │   ├── i18n.js                 # инициализация i18next
│   │   ├── App.css / index.css
│   │   ├── components/
│   │   │   ├── themeswitcher.jsx   # переключатель светлой/тёмной темы
│   │   │   └── languageswitcher.jsx# переключатель языка (RU/EN)
│   │   ├── pages/
│   │   │   ├── login.jsx           # страница входа/регистрации
│   │   │   └── main.jsx            # основная страница — список файлов
│   │   ├── locales/
│   │   │   ├── ru.json             # переводы RU
│   │   │   └── en.json             # переводы EN
│   │   └── styles/                 # css для отдельных страниц/компонентов
│   ├── index.html
│   ├── vite.config.js
│   ├── nginx.conf                  # конфиг nginx внутри контейнера (прокси /api → backend, SPA fallback)
│   ├── Dockerfile                  # сборка (bun build → nginx)
│   ├── package.json / bun.lock / package-lock.json
│   ├── eslint.config.js
│   └── dockerignore
│
├── docker-compose.yml              # локальный запуск (без HTTPS)
├── docker-compose.prod.yml         # production запуск (+ Caddy, HTTPS)
├── Caddyfile                       # конфиг reverse-proxy для прод-режима
├── config.yaml                     # справочный файл с настройками по умолчанию
├── .env                            # переменные окружения (создаётся install.sh)
├── install.sh                      # автоматический установщик
└── README.md
```

## Переменные окружения

| Переменная            | Описание                                                             | По умолчанию          |
|------------------------|-----------------------------------------------------------------------|------------------------|
| `POSTGRES_USER`        | Пользователь PostgreSQL                                              | —                      |
| `POSTGRES_PASSWORD`    | Пароль PostgreSQL                                                    | —                      |
| `POSTGRES_DB`          | Имя базы данных                                                      | `appdb`                |
| `MINIO_ACCESS_KEY`     | Access key MinIO (аналог логина S3)                                  | —                      |
| `MINIO_SECRET_KEY`     | Secret key MinIO (аналог пароля S3)                                  | —                      |
| `S3_BUCKET`            | Название бакета для хранения файлов                                  | `cloudstorage`         |
| `SECRET_KEY`           | Ключ для подписи JWT-токенов (`openssl rand -hex 32`)                | —                      |
| `MINIO_PUBLIC_URL`     | Публичный адрес MinIO, доступный из браузера (для ссылок на скачивание) | `http://localhost:9000` |
| `MINIO_INTERNAL_URL`   | Внутренний адрес MinIO для backend (в Docker-сети)                   | `http://minio:9000`    |

## Безопасность перед продом

- Обязательно смените все значения по умолчанию в `.env` (пароли БД, ключи MinIO, `SECRET_KEY`) — установочный скрипт делает это автоматически.
- Не открывайте порт `9001` (консоль MinIO) наружу без необходимости.
- Используйте production-режим (`docker-compose.prod.yml`) с HTTPS для любого сервера, доступного из интернета.
- Регулярно делайте резервные копии volume'ов `postgres_data` и `minio_data`.