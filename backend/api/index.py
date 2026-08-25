"""
Vercel ASGI Handler
This file serves as the entry point for Vercel's serverless function
"""
from app.main import app

# Vercel requires the WSGI/ASGI app to be exported as 'app'
__all__ = ['app']
