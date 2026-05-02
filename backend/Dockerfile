FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copia la carpeta app
COPY ./app ./app

# Copia las credenciales de Firebase si existen
RUN if [ -f firebase-credentials.json ]; then cp firebase-credentials.json /code/; fi

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]