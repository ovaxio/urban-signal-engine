FROM python:3.11-slim

WORKDIR /app

# Dépendances système (sqlite3 cli pour le script de seed check)
RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

# Répertoire data (sera monté comme volume persistant sur Railway)
RUN mkdir -p data

RUN chmod +x start.sh

EXPOSE 8000

CMD ["sh", "start.sh"]
