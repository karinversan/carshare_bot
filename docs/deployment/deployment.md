# Deployment

## Local
```bash
cp .env.example .env
docker compose -f infra/compose/docker-compose.yml up --build
make bootstrap
```

## Kubernetes
Use the manifests under `infra/k8s/` as the starting point for a portfolio deployment.
