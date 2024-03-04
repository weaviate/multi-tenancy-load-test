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
