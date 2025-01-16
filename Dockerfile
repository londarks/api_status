# Usamos a imagem oficial do Python
FROM python:3.9-slim

# Cria um diretório de trabalho
WORKDIR /app

# Copia o requirements.txt
COPY requirements.txt /app/

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o conteúdo da pasta local para /app no container
COPY . /app/

# Comando para iniciar a aplicação FastAPI
CMD ["sh", "-c", "uvicorn app.main:app --proxy-headers --host 0.0.0.0 --port 8005"]