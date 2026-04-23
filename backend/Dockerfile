FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /code

# Instalamos dependencias del sistema necesarias para Postgres y compilación de C
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiamos el requirements que está dentro de app/ a la raíz de /code en el contenedor
COPY app/requirements.txt .

# Instalamos las librerías de Python
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copiamos el contenido de la carpeta app al contenedor
COPY app/ .

# Ejecutamos Uvicorn. 
# "app.main:app" le dice: busca el paquete 'app', luego el archivo 'main', y usa la instancia 'app'.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

