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

## After Deployment

1. Restart the Azure App Service after deploying.
2. Monitor the **Log Stream** (Azure Portal → App Service → Log Stream) to confirm:
   - `startup.sh` logs the dependency and Chromium installation steps without errors.
   - The Gunicorn workers start successfully.
   - PDF generation log lines appear when PDFs are requested.
