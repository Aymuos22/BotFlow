# EC2 deployment (FastAPI + Docker)

Lean stack for small instances: **API in Docker**. **Weaviate** is not bundled — set `WEAVIATE_URL` and `WEAVIATE_API_KEY` in `.env` to Weaviate Cloud or another reachable cluster.

**WhatsApp** uses **Twilio**. Configure Twilio Account SID, Auth Token, and sender number per company in the portal; Twilio posts inbound messages to `https://<your-host>/api/v1/webhooks/twilio/messages`.

## Compose

From repo root:

```bash
docker compose -f deploy/docker-compose.ec2.yml up -d --build
```

Ensure `.env` at the repo root contains `DATABASE_URL`, `WEAVIATE_URL`, `WEAVIATE_API_KEY`, LLM keys, S3, `SECRET_KEY`, etc. (see `.env.example`).

If you use GitHub Actions deploy (`.github/workflows/deploy-ec2.yml`), add repository secrets `WEAVIATE_URL` and `WEAVIATE_API_KEY` with the same values as on the instance.

**On EC2**, after pulling: edit `/path/to/repo/.env` (or your deploy copy) with the cloud URL and key, then `docker compose -f deploy/docker-compose.ec2.yml up -d --build` so containers pick up the new env.
