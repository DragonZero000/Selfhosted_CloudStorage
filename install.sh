#!/usr/bin/env bash
#
# install.sh — интерактивный установщик Selfhosted CloudStorage
#
# Скрипт спрашивает у пользователя необходимые параметры, генерирует .env,
# при необходимости устанавливает Docker и разворачивает проект через
# docker compose (локальный режим) или docker-compose.prod.yml + Caddy (production, HTTPS).
#
set -euo pipefail

# ─── Цвета для вывода ──────────────────────────────────────────────────────────
C_RESET='\033[0m'
C_BOLD='\033[1m'
C_GREEN='\033[0;32m'
C_YELLOW='\033[0;33m'
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'

info()  { echo -e "${C_BLUE}[i]${C_RESET} $1"; }
ok()    { echo -e "${C_GREEN}[✓]${C_RESET} $1"; }
warn()  { echo -e "${C_YELLOW}[!]${C_RESET} $1"; }
err()   { echo -e "${C_RED}[✗]${C_RESET} $1" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${C_BOLD}=======================================================${C_RESET}"
echo -e "${C_BOLD}   Selfhosted CloudStorage — установочный скрипт${C_RESET}"
echo -e "${C_BOLD}=======================================================${C_RESET}"
echo

# ─── Проверка обязательных файлов ──────────────────────────────────────────────
for f in docker-compose.yml docker-compose.prod.yml Caddyfile; do
    if [[ ! -f "$f" ]]; then
        err "Файл $f не найден. Запускайте скрипт из корня репозитория."
        exit 1
    fi
done

# ─── Генератор случайных строк ────────────────────────────────────────────────
rand_hex() {
    local len="${1:-16}"
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "$len"
    else
        head -c "$((len * 2))" /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c "$((len * 2))"
    fi
}

# ─── Вопрос с вариантом по умолчанию ──────────────────────────────────────────
ask() {
    local prompt="$1" default="$2" var_name="$3"
    local answer
    if [[ -n "$default" ]]; then
        read -rp "$(echo -e "${C_BOLD}${prompt}${C_RESET} [${default}]: ")" answer
        answer="${answer:-$default}"
    else
        while [[ -z "${answer:-}" ]]; do
            read -rp "$(echo -e "${C_BOLD}${prompt}${C_RESET}: ")" answer
        done
    fi
    printf -v "$var_name" '%s' "$answer"
}

ask_secret() {
    local prompt="$1" default="$2" var_name="$3"
    local answer
    if [[ -n "$default" ]]; then
        read -rsp "$(echo -e "${C_BOLD}${prompt}${C_RESET} [оставьте пустым, чтобы сгенерировать автоматически]: ")" answer
        echo
        answer="${answer:-$default}"
    else
        read -rsp "$(echo -e "${C_BOLD}${prompt}${C_RESET}: ")" answer
        echo
    fi
    printf -v "$var_name" '%s' "$answer"
}

ask_yes_no() {
    local prompt="$1" default="$2" answer
    while true; do
        read -rp "$(echo -e "${C_BOLD}${prompt}${C_RESET} [y/n] (по умолчанию: ${default}): ")" answer
        answer="${answer:-$default}"
        case "$answer" in
            [Yy]*) echo "y"; return 0 ;;
            [Nn]*) echo "n"; return 0 ;;
            *) warn "Введите y или n" ;;
        esac
    done
}

# ─── 1. Проверка и установка Docker ────────────────────────────────────────────
install_docker() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        ok "Docker и Docker Compose уже установлены."
        return
    fi

    warn "Docker (или плагин Docker Compose) не найден."
    local choice
    choice=$(ask_yes_no "Установить Docker автоматически (официальный get-docker.sh)?" "y")
    if [[ "$choice" == "y" ]]; then
        if [[ "$EUID" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
            err "Нужны права root или установленный sudo для установки Docker."
            exit 1
        fi
        info "Устанавливаю Docker, это может занять пару минут..."
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        sh /tmp/get-docker.sh
        rm -f /tmp/get-docker.sh
        if command -v systemctl >/dev/null 2>&1; then
            sudo systemctl enable --now docker || true
        fi
        ok "Docker установлен."
        warn "Если Docker был только что установлен, для запуска без sudo может понадобиться перелогиниться (usermod -aG docker \$USER && newgrp docker)."
    else
        err "Установите Docker и Docker Compose вручную и запустите скрипт снова: https://docs.docker.com/engine/install/"
        exit 1
    fi
}

DOCKER_CMD="docker"
compose() {
    if ! $DOCKER_CMD compose version >/dev/null 2>&1; then
        err "Не найден 'docker compose'. Убедитесь, что установлен Docker Compose plugin."
        exit 1
    fi
    $DOCKER_CMD compose "$@"
}

install_docker

echo
info "Нужно ответить на несколько вопросов, чтобы настроить установку."
echo

# ─── 2. Режим установки ────────────────────────────────────────────────────────
echo -e "${C_BOLD}Выберите режим установки:${C_RESET}"
echo "  1) Локальный / без домена  — доступ по http://IP или http://localhost (без HTTPS)"
echo "  2) Production с доменом    — HTTPS через Caddy + Let's Encrypt"
MODE=""
while [[ "$MODE" != "1" && "$MODE" != "2" ]]; do
    read -rp "Ваш выбор [1/2]: " MODE
done

DOMAIN=""
PUBLIC_HOST=""

if [[ "$MODE" == "2" ]]; then
    echo
    warn "Для production-режима домен должен уже указывать A-записью на IP этого сервера,"
    warn "а порты 80 и 443 — быть открыты и свободны (не заняты другим веб-сервером)."
    ask "Введите домен (например cloud.example.com)" "" DOMAIN
    PUBLIC_HOST="https://${DOMAIN}"
else
    echo
    info "В локальном режиме приложению нужен адрес, по которому браузер сможет"
    info "обращаться к серверу (для корректной работы ссылок на скачивание файлов)."
    DEFAULT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    DEFAULT_IP="${DEFAULT_IP:-localhost}"
    ask "IP-адрес или адрес сервера (без http://, без порта)" "$DEFAULT_IP" SERVER_HOST
    PUBLIC_HOST="http://${SERVER_HOST}"
fi

# ─── 3. Параметры PostgreSQL ───────────────────────────────────────────────────
echo
echo -e "${C_BOLD}--- PostgreSQL ---${C_RESET}"
ask "Имя пользователя БД" "cloudstorage_admin" POSTGRES_USER
ask "Имя базы данных" "appdb" POSTGRES_DB
DEFAULT_PG_PASS="$(rand_hex 16)"
ask_secret "Пароль PostgreSQL" "$DEFAULT_PG_PASS" POSTGRES_PASSWORD

# ─── 4. Параметры MinIO ────────────────────────────────────────────────────────
echo
echo -e "${C_BOLD}--- MinIO (файловое хранилище) ---${C_RESET}"
ask "MinIO access key (логин)" "cloudstorage_minio_admin" MINIO_ACCESS_KEY
DEFAULT_MINIO_SECRET="$(rand_hex 16)"
ask_secret "MinIO secret key (пароль)" "$DEFAULT_MINIO_SECRET" MINIO_SECRET_KEY
ask "Название бакета" "cloudstorage" S3_BUCKET

# ─── 5. Секретный ключ JWT ─────────────────────────────────────────────────────
SECRET_KEY="$(rand_hex 32)"

# ─── 6. Публичный URL для MinIO (presigned-ссылки) ─────────────────────────────
echo
if [[ "$MODE" == "2" ]]; then
    # MinIO S3 API слушает 9000 порт напрямую (Caddy не проксирует MinIO по умолчанию)
    DEFAULT_MINIO_PUBLIC="http://${DOMAIN}:9000"
    info "Ссылки на скачивание файлов (presigned URL) будут указывать на порт 9000 вашего домена."
    ask "Публичный URL для MinIO (presigned-ссылки)" "$DEFAULT_MINIO_PUBLIC" MINIO_PUBLIC_URL
else
    DEFAULT_MINIO_PUBLIC="${PUBLIC_HOST}:9000"
    ask "Публичный URL для MinIO (presigned-ссылки)" "$DEFAULT_MINIO_PUBLIC" MINIO_PUBLIC_URL
fi

# ─── 7. Запись .env ────────────────────────────────────────────────────────────
echo
info "Сохраняю настройки в .env ..."

cat > .env <<EOF
# ─────────────────────────────────────────────────────────────
# Сгенерировано install.sh $(date '+%Y-%m-%d %H:%M:%S')
# ─────────────────────────────────────────────────────────────

# База данных
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}

# MinIO
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
S3_BUCKET=${S3_BUCKET}

# JWT
SECRET_KEY=${SECRET_KEY}

# Публичный URL для presigned ссылок
MINIO_PUBLIC_URL=${MINIO_PUBLIC_URL}
EOF

ok ".env создан."

# ─── 8. Caddyfile для production-режима ────────────────────────────────────────
if [[ "$MODE" == "2" ]]; then
    info "Обновляю Caddyfile под ваш домен..."
    cp Caddyfile "Caddyfile.bak.$(date +%s)" 2>/dev/null || true
    # Заменяем первую строку (домен) на введённый пользователем
    tmpfile="$(mktemp)"
    {
        echo "${DOMAIN} {"
        tail -n +2 Caddyfile
    } > "$tmpfile"
    mv "$tmpfile" Caddyfile
    ok "Caddyfile обновлён (домен: ${DOMAIN})."
fi

# ─── 9. Запуск ──────────────────────────────────────────────────────────────────
echo
if [[ "$MODE" == "2" ]]; then
    COMPOSE_FILE="docker-compose.prod.yml"
else
    COMPOSE_FILE="docker-compose.yml"
fi

info "Собираю и запускаю контейнеры (${COMPOSE_FILE})... это может занять несколько минут."
compose -f "$COMPOSE_FILE" up -d --build

echo
info "Жду готовности сервисов..."
ATTEMPTS=30
until [[ "$(compose -f "$COMPOSE_FILE" ps --status running --services 2>/dev/null | wc -l)" -ge 1 ]]; do
    ATTEMPTS=$((ATTEMPTS - 1))
    if [[ $ATTEMPTS -le 0 ]]; then
        warn "Сервисы запускаются дольше обычного, проверьте логи: docker compose -f ${COMPOSE_FILE} logs -f"
        break
    fi
    sleep 2
done
sleep 5

echo
echo -e "${C_GREEN}${C_BOLD}=======================================================${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}   Установка завершена!${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}=======================================================${C_RESET}"
echo
HOST_NO_SCHEME="$(echo "$PUBLIC_HOST" | sed -E 's#^https?://##')"
if [[ "$MODE" == "2" ]]; then
    echo -e "  Приложение:    ${C_BOLD}https://${DOMAIN}${C_RESET}  (сертификат Let's Encrypt выпустится автоматически, подождите 10-30 сек)"
else
    echo -e "  Приложение:    ${C_BOLD}${PUBLIC_HOST}${C_RESET}"
fi
echo -e "  MinIO консоль: ${C_BOLD}http://${HOST_NO_SCHEME}:9001${C_RESET} (логин/пароль — MinIO access/secret key из .env)"
echo
echo "  Полезные команды:"
echo "    docker compose -f ${COMPOSE_FILE} logs -f      # логи"
echo "    docker compose -f ${COMPOSE_FILE} ps           # статус сервисов"
echo "    docker compose -f ${COMPOSE_FILE} down          # остановить"
echo
warn "Все сгенерированные пароли и ключи сохранены в файле .env — храните его в безопасности."
echo
