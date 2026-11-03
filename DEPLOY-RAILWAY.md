# Cloud deployment guide — Railway

This repo deploys as two Railway services from the same GitHub repository:
- `clipgenius-api`: backend Dockerfile at `/backend/Dockerfile`
- `clipgenius-web`: frontend Dockerfile at `/frontend/Dockerfile`

## 1. Push this project to GitHub
Create a private repository, upload the project contents, and push the default branch.

## 2. Create the API service
In Railway, create a project and choose Deploy from GitHub Repo. Select this repository.
Set the service's Dockerfile path to `/backend/Dockerfile` (or set the service root directory to `/backend`
and Dockerfile path to `Dockerfile`, depending on the Railway UI).

Set variables:
- `WHISPER_MODEL=base` (use `small` for better accuracy if memory permits)
- `CORS_ORIGINS=https://YOUR-WEB-DOMAIN`
- `PORT` is supplied by Railway; do not hardcode it.

Attach a Railway Volume mounted at `/app/data`. This is essential for the MVP's uploaded media,
generated clips, and JSON project records to persist across redeploys. Use a single API replica because
this MVP stores its job metadata and processing state on local disk.

Generate a public domain for the API. Confirm `https://YOUR-API-DOMAIN/api/health` returns JSON.

## 3. Create the web service
Add a second service from the same GitHub repository.
Set Dockerfile path to `/frontend/Dockerfile` (or root directory `/frontend` and Dockerfile path `Dockerfile`).
Set the build argument/environment variable:
- `NEXT_PUBLIC_API_URL=https://YOUR-API-DOMAIN`

Important: `NEXT_PUBLIC_API_URL` is embedded into the browser bundle at build time. Set it before building
and redeploy the web service whenever the API domain changes.

Generate a public domain for the web service. Open it and test uploading a small sample video.

## 4. Cloud runtime settings
- Use at least 2 vCPU and 4–8 GB RAM for a modest CPU transcription workload. Longer videos or `small`
  Whisper models may need more RAM/CPU. This is a practical starting point, not a guaranteed sizing.
- Set request/body upload limits according to your hosting plan. Large uploads should later move to direct
  object-storage uploads rather than passing through the API container.
- Configure a persistent volume and monitor disk usage. The MVP does not automatically expire old uploads.
- Do not expose the API with wildcard CORS. Set `CORS_ORIGINS` to the exact web origin.
- Do not commit secrets or media files to Git.
- Add authentication, per-user authorization, rate limits, file validation/scanning, retention policies,
  backups, and observability before inviting public users.

## Important MVP limitations before public launch
This cloud package is a deployable demonstration/MVP, not a hardened multi-tenant SaaS:
- It currently uses local JSON job records and local disk storage, not PostgreSQL/object storage.
- It uses FastAPI BackgroundTasks, not a durable queue. A restart during a job can interrupt processing.
- The API and worker are currently the same service. Keep one replica and attach persistent storage.
- There is no login or account isolation yet. Anyone who can reach the public API may access project endpoints.
- The frontend's project list is not private per user.
- No payment system, watermarking, or paid feature restrictions are included.

For a real public SaaS launch, the next engineering milestone is authentication + PostgreSQL + private object storage
+ Redis/Celery worker service + signed upload/download URLs. Do not market this MVP as production-secure until
those are implemented and tested.
