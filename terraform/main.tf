provider "google" {
  project = var.project
  region  = var.region
}

resource "google_container_cluster" "my_cluster" {
  name     = var.cluster_name
  location = var.zone

  network    = "default"
  subnetwork = "default"

  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }

  remove_default_node_pool = true
  initial_node_count = 1

  deletion_protection = false
}

resource "google_container_node_pool" "client_pool" {
  name       = "client-pool"
  location   = var.zone
  cluster    = google_container_cluster.my_cluster.name
  node_count = var.client_node_pool_size

  node_config {
    machine_type = "e2-standard-4"

    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  # Preventing automatic upgrades and repairs on this node pool
  management {
    auto_upgrade = false
    auto_repair  = false
  }
}

resource "google_container_node_pool" "server_pool" {
  name       = "server-pool"
  location   = var.zone
  cluster    = google_container_cluster.my_cluster.name
  node_count = var.server_node_pool_size

  node_config {
    machine_type = "e2-standard-4"

    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  # Preventing automatic upgrades and repairs on this node pool
  management {
    auto_upgrade = false
    auto_repair  = false
  }
}

