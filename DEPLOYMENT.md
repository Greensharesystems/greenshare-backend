# Greenshare Backend Deployment

## Azure App Service Startup Command

Set this in **Azure Portal → App Service → Configuration → General Settings → Startup Command**:

```bash
bash startup.sh
```

The committed [startup.sh](startup.sh) script is the single startup entrypoint for Azure App Service staging. It:

- installs the required Linux packages for Playwright Chromium, including `libglib2.0-0`
- installs the Playwright Chromium browser into a controlled path
- exports a stable Playwright runtime environment
- launches the backend with Gunicorn on Linux and a local Uvicorn fallback on non-Linux hosts

`gunicorn` is required in `requirements.txt` so Azure can launch the app with Uvicorn workers.

## Required Files for Deployment

Ensure the following files are included in the deployment package:

- `app/templates/pdf/reception_note.html`
- `app/templates/pdf/reception_certificate.html`
- `app/templates/pdf/circularity_certificate.html`
- `app/templates/pdf/styles.css`
- `app/static/images/` (logo and other static assets)

## Local Development Command

```bash
uvicorn main:app --reload
```

## Local Startup Script Validation

If you want to validate the same entrypoint used by Azure, run:

```bash
bash startup.sh
```

On Windows, run it from Git Bash. The script skips `apt-get` when it is unavailable and uses a local Uvicorn fallback instead of Gunicorn.

## Azure App Service CORS Portal Setting

**Critical**: The backend handles CORS entirely through the FastAPI `CORSMiddleware` configured in `app/core/config.py`. The middleware already allows all required origins:

- `https://www.greenshare.ae`
- `https://greenshare.ae`
- `https://witty-pond-0c214db00.7.azurestaticapps.net` (and dev/staging variants)
- `http://localhost:3000`

**If Azure App Service built-in CORS (portal) is enabled, it overrides the application CORS and will block production requests from custom domains.**

To fix: go to **Azure Portal → App Service → API → CORS** and ensure the allowed origins list is **empty** (leave it blank). This lets the application's own FastAPI CORS middleware handle all CORS, which is already correctly configured.

Do not add a `*` wildcard there either — `allow_credentials=True` requires explicit origins, which the application handles correctly.

To verify via CLI (replace `<resource-group>` and `<app-name>`):

```bash
az webapp cors show --resource-group <resource-group> --name <app-name>
# If any origins are listed, clear them:
az webapp cors remove --resource-group <resource-group> --name <app-name> --allowed-origins "*"
```

After clearing, restart the App Service and confirm CORS headers are returned by the FastAPI app:

```bash
curl -I -X OPTIONS \
  https://<app-name>.azurewebsites.net/crm/leads \
  -H "Origin: https://www.greenshare.ae" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization,content-type"
# Expected: Access-Control-Allow-Origin: https://www.greenshare.ae
```

## After Deployment

1. Restart the Azure App Service after deploying.
2. Verify CORS is NOT configured in the Azure portal (see section above).
3. Monitor the **Log Stream** (Azure Portal → App Service → Log Stream) to confirm:
   - `startup.sh` logs the dependency and Chromium installation steps without errors.
   - The Gunicorn workers start successfully.
   - PDF generation log lines appear when PDFs are requested.
