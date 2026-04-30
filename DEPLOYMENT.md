# Greenshare Backend Deployment

Azure App Service startup command:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Local development command:

```bash
uvicorn main:app --reload
```