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

1. Скопируйте `.env.example` (или отредактируйте `.env`) и заполните:

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
├── backend/                  # FastAPI-приложение
│   ├── CloudStorage.py       # точка входа
│   ├── authorization.py      # регистрация, вход, JWT
│   ├── storage.py            # загрузка/скачивание/шаринг файлов
│   ├── db.py                 # модели SQLAlchemy (User, File)
│   └── requirements.txt
├── frontend/                 # React SPA (Vite)
├── docker-compose.yml        # локальный запуск
├── docker-compose.prod.yml   # production запуск (+ Caddy, HTTPS)
├── Caddyfile                 # конфиг reverse-proxy для прод-режима
├── config.yaml               # справочный файл с настройками по умолчанию
├── .env                      # переменные окружения (создаётся install.sh)
└── install.sh                # автоматический установщик
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

## Безопасность перед продом

- Обязательно смените все значения по умолчанию в `.env` (пароли БД, ключи MinIO, `SECRET_KEY`) — установочный скрипт делает это автоматически.
- Не открывайте порт `9001` (консоль MinIO) наружу без необходимости.
- Используйте production-режим (`docker-compose.prod.yml`) с HTTPS для любого сервера, доступного из интернета.
- Регулярно делайте резервные копии volume'ов `postgres_data` и `minio_data`.

## Лицензия

См. файл `LICENSE` в репозитории (если присутствует), либо уточните у автора проекта.
