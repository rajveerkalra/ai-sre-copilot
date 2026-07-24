# Terraform skeleton (Phase 8)

Creates a **local Kind cluster** (no cloud spend). Optional Helm install of the
platform chart.

```bash
cd infra/terraform
terraform init
terraform plan
# terraform apply -var='enable_helm_release=true'
```

Load images into Kind after build:

```bash
kind load docker-image ai-sre-copilot/auth-service:phase7 --name ai-sre-copilot
# ... repeat for other services
```

`cloud.tf` is a placeholder for future EKS/GKE/AKS modules — left commented so
CI/local plans never create billable resources.
