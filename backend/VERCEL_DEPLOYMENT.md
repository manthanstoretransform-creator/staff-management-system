# Vercel Deployment Guide

## Prerequisites
- Vercel account
- Backend repository connected to Vercel
- Environment variables configured in Vercel project settings

## Environment Variables Required

Set these in your Vercel project settings:

### Production
```
ENV=production
DATABASE_URL=<your-production-database-url>
JWT_SECRET_KEY=<your-strong-random-secret-key>
EXTERNAL_AUTH_BASE_URL=https://dev-st-performance.pantheonsite.io
EXTERNAL_AUTH_LOGIN_PATH=/wp-json/st-performance/v1/auth/hubstaff/login
EXTERNAL_AUTH_CONNECT_TIMEOUT=10.0
EXTERNAL_AUTH_READ_TIMEOUT=20.0
```

### Development
```
ENV=development
DATABASE_URL_DEV=<your-dev-database-url>
JWT_SECRET_KEY=super-secret-key-change-me-in-production
EXTERNAL_AUTH_BASE_URL=https://dev-st-performance.pantheonsite.io
EXTERNAL_AUTH_LOGIN_PATH=/wp-json/st-performance/v1/auth/hubstaff/login
```

## Deployment Steps

1. **Push changes to repository**
   ```bash
   git add .
   git commit -m "Configure Vercel deployment"
   git push origin main
   ```

2. **Vercel will automatically detect and deploy**
   - Vercel will read `vercel.json` and use Python 3.11
   - It will install dependencies from `requirements.txt`
   - The app will be served via `api/index.py`

3. **Verify deployment**
   - Check Vercel dashboard for build logs
   - Test health endpoint: `https://your-backend-url.vercel.app/health`
   - Test login endpoint: `https://your-backend-url.vercel.app/auth/login`

## Troubleshooting

### FUNCTION_INVOCATION_FAILED
- Check Vercel logs for detailed error messages
- Ensure all required environment variables are set
- Verify database URL is correct and accessible
- Check that Python dependencies are installed

### Database Connection Errors
- Verify DATABASE_URL (production) or DATABASE_URL_DEV (development)
- Ensure database is accessible from Vercel servers
- Check database credentials and network settings

### CORS Errors
- Verify CORS origins are configured correctly in `app/main.py`
- Ensure frontend URL is in the allowed origins list

## Files Modified for Vercel

- `vercel.json` - Vercel configuration
- `api/index.py` - ASGI handler entry point
- `.vercelignore` - Files to exclude from deployment
- `app/core/database.py` - Lazy database initialization for serverless
- `app/core/config.py` - Environment-aware configuration
- `app/main.py` - Logging and health check endpoint

## Performance Considerations

- Connection pooling is optimized for serverless (pool_size=5, max_overflow=10)
- Connections are recycled every hour (pool_recycle=3600)
- Lambda timeout is set to 30 seconds
- Memory is set to 3008 MB

## Notes

- The app uses PostgreSQL with connection pooling
- Each serverless function invocation is independent
- Database connections are automatically managed
- Logging is configured for debugging in Vercel
