FROM python:3.12-slim

WORKDIR /app

# Окружение, чтобы Python не создавал файлы .pyc и сразу выводил логи в консоль
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Системные зависимости для psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Обновляем pip и ставим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Убедитесь, что модуль "main" соответствует вашему файлу запуска (например, main.py)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]