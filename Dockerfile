# Usamos una imagen liviana oficial de Python
FROM python:3.10-slim

# Creamos un directorio de trabajo dentro del contenedor
WORKDIR /code

# Copiamos e instalamos las dependencias
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copiamos el código de la API
COPY . .

# Comando para arrancar FastAPI en el puerto 7860 (el requerido por Hugging Face)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
