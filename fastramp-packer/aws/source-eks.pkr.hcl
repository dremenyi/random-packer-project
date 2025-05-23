data "amazon-ami" "eks-al2" {
  filters = {
    architecture        = var.source_ami_arch
    name                = "amazon-eks-node-${var.eks_major_version}-*"
    root-device-type    = "ebs"
    state               = "available"
    virtualization-type = "hvm"
  }
  most_recent = true
  owners      = ["602401143452", "013241004608"] # "602401143452" for commercial, "013241004608" for GovCloud
  region      = var.aws_region
  assume_role {
    role_arn     = "arn:${var.partition}:iam::${var.builder_account_id}:role/packer_role"
    session_name = "packer_session"
  }
}

# Note: Must subscribe to https://aws.amazon.com/marketplace/pp?sku=dw21ctly265u7zwld1ihi9jhk to use this AMI
# The subscription must happen on mgmt account to build it, then on prod account to use it
data "amazon-ami" "ubuntu1804" {
  filters = {
    architecture        = var.source_ami_arch
    name                = "ubuntu-pro-fips-server/images/hvm-ssd/ubuntu-bionic-18.04-amd64-pro-fips-server-*"
    root-device-type    = "ebs"
    state               = "available"
    virtualization-type = "hvm"
  }
  most_recent = true
  owners      = ["aws-marketplace"]
  region      = var.aws_region
  assume_role {
    role_arn     = "arn:${var.partition}:iam::${var.builder_account_id}:role/packer_role"
    session_name = "packer_session"
  }
}

source "amazon-ebs" "eks" {
  aws_polling {
    # Default value is 40, increasing to avoid timeout during encryption
    # https://developer.hashicorp.com/packer/plugins/builders/amazon#resourcenotready-error
    delay_seconds = 30
    max_attempts = 80
  }
  ami_users                   = ["${data.amazon-parameterstore.prod_account_id.value}"]
  associate_public_ip_address = true
  ebs_optimized               = true
  encrypt_boot                = true
  iam_instance_profile        = "packer_profile"
  instance_type               = var.linux_build_instance_type
  launch_block_device_mappings {
    delete_on_termination = true
    device_name           = "/dev/sdb"
    volume_size           = 50
    volume_type           = "gp3"
  }
  kms_key_id = data.amazon-parameterstore.kms_key_id.value
  region     = var.aws_region
  subnet_id  = data.amazon-parameterstore.subnet_id.value
  vpc_id     = data.amazon-parameterstore.vpc_id.value
  assume_role {
    role_arn     = "arn:${var.partition}:iam::${var.builder_account_id}:role/packer_role"
    session_name = "packer_session"
  }
}