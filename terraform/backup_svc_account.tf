resource "google_service_account_key" "my_key" {
  service_account_id = "load-test-backups@semi-automated-benchmarking.iam.gserviceaccount.com"
  public_key_type    = "TYPE_NONE" # to generate a JSON key file
}

resource "local_file" "key_file" {
  sensitive_content =   base64decode(google_service_account_key.my_key.private_key)
  filename          = "${path.module}/backup-service-account-key.json"
}

output "key" {
  value     = google_service_account_key.my_key.private_key
  sensitive = true
}
