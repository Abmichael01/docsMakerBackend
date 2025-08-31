web: gunicorn serverConfig.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --max-requests 1000 --max-requests-jitter 100 --timeout 300 --worker-connections 1000
