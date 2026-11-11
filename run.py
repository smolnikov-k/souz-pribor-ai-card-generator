#!/usr/bin/env python3
"""Entry point for running the Soyuz-Pribor AI Assistant web application."""
import os
import sys
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"[*] Запуск сервера «СОЮЗ-ПРИБОР AI-помощник» на http://localhost:{port}")
    uvicorn.run("src.app:app", host=host, port=port, reload=False)
