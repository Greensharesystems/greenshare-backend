# Greenshare Backend Deployment

## Azure App Service Startup Command

Set this in **Azure Portal → App Service → Configuration → General Settings → Startup Command**:

```bash
python -m playwright install chromium && gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

This installs the Playwright Chromium browser on each container start (required for PDF generation), then launches the application with Gunicorn/Uvicorn workers.

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

## After Deployment

1. Restart the Azure App Service after deploying.
2. Monitor the **Log Stream** (Azure Portal → App Service → Log Stream) to confirm:
   - `python -m playwright install chromium` completes without errors.
   - The Gunicorn workers start successfully.
   - PDF generation log lines appear when PDFs are requested.
