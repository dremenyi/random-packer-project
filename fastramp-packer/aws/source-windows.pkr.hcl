data "amazon-ami" "win-base" {
  filters = {
    name                = var.win_base_ami_name
    root-device-type    = "ebs"
    virtualization-type = "hvm"
  }
  most_recent = true
  owners      = ["amazon"]
  region      = var.aws_region
}

source "amazon-ebs" "windows" {
  aws_polling {
    # Default value is 40, increasing to avoid timeout during encryption
    # https://developer.hashicorp.com/packer/plugins/builders/amazon#resourcenotready-error
    delay_seconds = 30
    max_attempts = 80
  }
  ami_users                   = ["${data.amazon-parameterstore.prod_account_id.value}"]
  associate_public_ip_address = true
  communicator                = "winrm"
  ebs_optimized               = true
  encrypt_boot                = true
  iam_instance_profile        = "packer_profile"
  instance_type               = var.win_build_instance_type
  kms_key_id                  = data.amazon-parameterstore.kms_key_id.value
  region                      = var.aws_region
  subnet_id                   = data.amazon-parameterstore.subnet_id.value
  user_data_file              = "./scripts/windows/pk-winrm.ps1"
  winrm_insecure              = "true"
  winrm_use_ssl               = "true"
  winrm_username              = "Administrator"
  vpc_id                      = data.amazon-parameterstore.vpc_id.value
  assume_role {
    role_arn     = "arn:${var.partition}:iam::${var.builder_account_id}:role/packer_role"
    session_name = "packer_session"
  }
}
