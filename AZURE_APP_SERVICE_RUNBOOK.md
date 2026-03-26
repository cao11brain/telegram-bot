# Azure App Service Runbook (Container)

## 1) Build and push image to ACR

```bash
az acr build \
  --registry <ACR_NAME> \
  --image telegram-bot:latest \
  .
```

## 2) Create App Service for Containers

- Runtime: Linux
- Container source: Azure Container Registry
- Image: `telegram-bot:latest`

## 3) App Settings

Set the following environment variables in App Service:

- `TELEGRAM_BOT_TOKEN`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `WEBSITES_PORT=8000`

## 4) Startup command

Use the container default command from `Dockerfile`:

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
```

If you must override from App Service startup command, use the same command above.

## 5) Health check

- Endpoint: `GET /`
- Expected response: `{"status":"ok","version":"v2-no-echo"}`

## 6) Operational checks

- Open App Service Log stream.
- Check Playwright runtime errors and outbound DNS/network errors.
- Validate webhook flow by posting a Telegram message with:
  - arXiv link
  - Korean blog link
  - English article link

## 7) Built-in Python runtime (not recommended)

If you do not use custom container:

```bash
python -m playwright install chromium && gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} app.main:app
```

This option can increase cold-start and restart time.

