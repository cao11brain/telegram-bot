# Azure App Service Runbook (Container)

## 1) Build and push image to ACR

```bash
az acr build \
  --registry <ACR_NAME> \
  --image telegram-bot:<GIT_SHA> \
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
- Expected response: `{"status":"ok","version":"v2-no-echo","app_version":"<GIT_SHA>"}` or equivalent

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

## 8) GitHub Actions CI/CD

Repository includes a workflow at `.github/workflows/deploy.yml`.

Add these GitHub repository secrets before using it:

- `ACR_USERNAME`
- `ACR_PASSWORD`

The workflow runs on pushes to `main` and:

1. Builds the Docker image from `Dockerfile`
2. Pushes both `sjtelebot.azurecr.io/telegram-bot:<GIT_SHA>` and `sjtelebot.azurecr.io/telegram-bot:latest`
3. Updates App Service to use the exact SHA tag image
4. Restarts App Service so the running version is explicit and traceable

Required GitHub secrets:

- `ACR_USERNAME`
- `ACR_PASSWORD`
- `AZURE_CREDENTIALS`
