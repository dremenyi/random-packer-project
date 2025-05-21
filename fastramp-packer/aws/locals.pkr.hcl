locals {
  # These are default values that are not expected to change frequently
  datetime = formatdate("YYYY-MM-DD-hh-mm-ssZ", timestamp())

  # Linux
  aws_ssh_username = "ec2-user"

  # Shared
  ansible_role_path      = "../../fastramp-ansible/roles/"
  partition_disk_ansible = "./scripts/shared/partition-disk.yml"
  playbook_dir           = "./scripts/shared/playbook_dir"

  ### EKS ###
  # Common
  binary_bucket_name   = "amazon-eks"
  binary_bucket_region = "us-west-2"

  # Ubuntu Variables
  pause_container_version = "3.5"
  pull_cni_from_github    = "true"
  cache_container_images  = "false"

  is_gov = var.partition == "aws-us-gov" ? true : false

  # Splunk
  # Windows
  install_root_url          = "https://dl.dod.cyber.mil/wp-content/uploads/pki-pke/msi/InstallRoot_5.5x64.msi"
  splunk_package_version    = "9.0.3"
  build_id                  = "dd0128b1f8cd"
  splunk_win_file_name      = "splunkforwarder-${local.splunk_package_version}-${local.build_id}-x64-release.msi"
  splunk_win_download_url   = "https://download.splunk.com/products/universalforwarder/releases/${local.splunk_package_version}/windows/${local.splunk_win_file_name}"
  splunk_win_installer_hash = "f398bb5d225998b5916fbb4df4712094a07da77c3c6657f611695fa1c3c0f2a04a27aa6b146579fb37b218a6aa8feb2327bcd21882d694c1aac015cdc1fdf95d"
}