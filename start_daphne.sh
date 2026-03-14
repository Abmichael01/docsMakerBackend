#!/bin/bash
cd /var/www/backend
/var/www/backend/env/bin/daphne -t 120 -b 0.0.0.0 -p 8000 serverConfig.asgi:application
