# FTP AI Assistant

## Запуск на сервере

### 1. Установка Docker и Docker Compose
```bash
sudo apt update && sudo apt install docker.io docker-compose

#Запусти сервер вручную
docker exec -it my_ftp_assistant /opt/conda/bin/python /app/api.py
