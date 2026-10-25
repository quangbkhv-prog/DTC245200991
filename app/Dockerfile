
FROM python:3.12-slim
WORKDIR /app
RUN useradd -r -u 10001 appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Tao thu muc luu anh va cap quyen cho appuser
RUN mkdir -p /app/static/uploads/products \
    && chown -R appuser:appuser /app/static/uploads

USER appuser
EXPOSE 8000
CMD ["gunicorn","-b","0.0.0.0:8000","--workers","2","main:app"]
