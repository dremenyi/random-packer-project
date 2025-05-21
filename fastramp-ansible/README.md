# coalfire-packer

Update variables.pkrvars.hcl prior to building the images.

The Packer files have been consolidated due to the upgrade to HCL2, which concatenates all .hcl files in the current directory much like Terraform
does with .tf files.
What you want to build depends on the string filter applied which corresponds to the names in the build files.

# Directory
Packer uses Ansible roles for CIS/STIG hardening on RHEL.  The file path must be local on your system.  To avoid duplicating sources for roles, 
we're using the same role that is in the FastRAMP Ansible repository.

The default roles path is "../../fastramp-ansible/roles/", so the Ansible repository must be 2 levels up if running in "packer/aws"

```
ubuntu@cfs-PW010D7H:~/VSCode/fastramp-live$ tree -L 1
.
├── fastramp-ansible
└── fastramp-packer

2 directories, 0 files
```

# Variables
Similar to Terraform, variables which are exposed and can be overwritten are expected to be provided via a *.pkrvars.hcl file and specified to Packer with "-var-file=\<directory>/\<var-file>"

# Examples

## Pkrvars
```
# Global variables used by all Packer builds
aws_region  = "us-east-1"
builder_account_id = "798995567797"  # Fastramp Sandbox 3
partition = "aws"

# These are to help with debugging
#ssh_keypair_name = "fastramp-3"
#ssh_private_key_file = "~/.ssh/fastramp-3.pem"
```

Change directory first (aws or aws/eks)

Run Packer init to load AWS Plugin (needed for AWS SSM Parameter Store):
`packer init .`  

## Base OS ##
`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*win-base*" .`  
Builds only the Windows golden image (not tied to one benchmark or the other because the GPOs apply them during Ansible config)

`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*al2-cis*" .`  
Builds only AL2 CIS golden image

`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*rhel-stig*" .`  
Builds only RHEL STIG golden image

`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*ubuntu2004-stig*" .`  
Builds only Ubuntu Pro 20.04 LTS FIPS STIG golden image

## ASG ##
`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*win-asg*" .`  
Builds only the Windows ASG golden image (not tied to one benchmark or the other because the GPOs apply them during Ansible config)

## EKS ##
`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*al2-eks-cis*" .`  
Builds only the EKS AL2 CIS image

`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*ubuntu2004-eks-stig*" .`  
Builds only the EKS Ubuntu Pro 20.04 LTS FIPS STIG image

## ECS ##
`AWS_PROFILE=fastramp-3 packer build -var-file=vars/variables.pkrvars.hcl -only="*al2-ecs-cis*" .`  
Builds only AL2 ECS CIS golden image


# Compatibility Notes
## AL2
Does NOT work with:
- Ansible Tower
- Trend DSM (explicitly called out not to work by vendor)

## Ubuntu 20.04 LTS FIPS
Does NOT work with:
- Ansible Tower
- Trend DSM (explicitly called out not to work by vendor)


# EKS Packer AMIs
This repository contains Packer configurations to create custom AMIs for EKS.

## Original Source
AL2 (CIS):
https://github.com/aws-samples/amazon-eks-custom-amis

AL2 (Clean):
https://github.com/awslabs/amazon-eks-ami

Ubuntu (18.04, stale):
https://github.com/Gusto/ubuntu-eks-ami

## Observations
We utilized an older copy of the AL2 (CIS) repository provided by AWS before support for other distros (RHEL, Ubuntu) were removed.  It is my observation that the repository uses AL2 EKS optimized image as a base and simply applies hardening to it.

We use a copy of the public AWS Terraform EKS module authored by Anton Babenko to deploy EKS:
https://github.com/terraform-aws-modules/terraform-aws-eks

That module in particular runs "bootstrap.sh" in user data to join the node to the cluster.  The script must be present in the resulting AMI.

## Recreation
As of now, there are only 2 tested and working distros in FastRAMP:
  - Amazon Linux 2
  - Ubuntu Pro 20.04 LTS FIPS

I used AWS Labs as a "source of truth" for building a working AMI: https://github.com/awslabs/amazon-eks-ami
That repository is open sourced and is how AWS builds their EKS optimized AMI for AL2 that is available in the AWS marketplace.  That is what the Terraform AWS EKS module expects.

For converting to use with other distros, I copied all files and modified "bootstrap.sh" and "install-worker.sh" scripts for things that aren't applicable (package manager from "yum" to "apt", package names that don't exist).

For Ubuntu I referenced an older build for distro specific items (configuring time): https://github.com/Gusto/ubuntu-eks-ami

## Hardening
Where possible, I try to use Ansible Lockdown for hardening since it is my understanding that it is also applied after AMI builds for configuration drift:
https://github.com/ansible-lockdown

This is implemented for:
  - Amazon Linux 2
  - Ubuntu Pro 20.04 LTS FIPS

The original images use Bash scripts, which IMO is harder to maintain because exceptions and changes to CIS prescribed rules are harder to spot.
Using Ansible Lockdown roles, making exceptions in default variables, and then noting with comments where changes are made makes it easier to update, recreate, and maintain.