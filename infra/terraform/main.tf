provider "kind" {}

resource "kind_cluster" "this" {
  name = var.cluster_name

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"
      kubeadm_config_patches = [
        <<-EOT
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
        EOT
      ]
      extra_port_mappings {
        container_port = 80
        host_port      = 8088
        protocol       = "TCP"
      }
      extra_port_mappings {
        container_port = 443
        host_port      = 8443
        protocol       = "TCP"
      }
    }
  }
}

provider "kubernetes" {
  host                   = kind_cluster.this.endpoint
  client_certificate     = kind_cluster.this.client_certificate
  client_key             = kind_cluster.this.client_key
  cluster_ca_certificate = kind_cluster.this.cluster_ca_certificate
}

provider "helm" {
  kubernetes {
    host                   = kind_cluster.this.endpoint
    client_certificate     = kind_cluster.this.client_certificate
    client_key             = kind_cluster.this.client_key
    cluster_ca_certificate = kind_cluster.this.cluster_ca_certificate
  }
}

resource "helm_release" "ai_sre" {
  count      = var.enable_helm_release ? 1 : 0
  name       = "ai-sre"
  chart      = "${path.module}/../helm/ai-sre-copilot"
  namespace  = "ai-sre-copilot"
  create_namespace = true
  dependency_update = false
  wait              = false

  values = [
    file("${path.module}/../helm/ai-sre-copilot/values.yaml"),
  ]
}
