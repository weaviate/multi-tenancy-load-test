provider "google" {
  project = var.project
  region  = var.region
}

variable "project" {
  default = "semi-automated-benchmarking"
}

variable "cluster_name" {
  default = "mt-load-test"
}

variable "zone" {
  default = "us-central1-c"
}

variable "region" {
  default = "us-central1"
}

variable "client_node_pool_size" {
  default = 6
}

variable "server_node_pool_size" {
  default = 12
}

resource "google_container_cluster" "my_cluster" {
  name               = var.cluster_name
  location           = var.zone

  network    = "default"
  subnetwork = "default"

  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }

  node_pool {
    name               = "client-pool"
    initial_node_count = var.client_node_pool_size

    node_config {
      machine_type = "e2-standard-4"

      oauth_scopes = [
        "https://www.googleapis.com/auth/logging.write",
        "https://www.googleapis.com/auth/monitoring",
        "https://www.googleapis.com/auth/cloud-platform"
      ]
    }
  }

  node_pool {
    name               = "server-pool"
    initial_node_count = var.server_node_pool_size

    node_config {
      machine_type = "e2-standard-4"

      oauth_scopes = [
        "https://www.googleapis.com/auth/logging.write",
        "https://www.googleapis.com/auth/monitoring",
        "https://www.googleapis.com/auth/cloud-platform"
      ]
    }
  }

  deletion_protection = false
}

