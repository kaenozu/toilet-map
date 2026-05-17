# Deployment

## Docker (recommended)

```bash
docker build -t toilet-map .
docker run -d -p 8501:8501 toilet-map
```

## Docker Compose

```bash
docker compose up -d
```

## Kubernetes

```bash
helm install toilet-map ./charts/toilet-map
```

## Environment Variables

See `.env.example` for all configurable variables.
