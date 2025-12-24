FROM python:3.13-slim 
  
WORKDIR /app

# install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# copy requirements
COPY requirements.txt .

# install python dependencies
RUN pip install --no-cache-dir -r requirements.txt


# copy application code
COPY . .

# expose port 
EXPOSE 8000

# run the application
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]