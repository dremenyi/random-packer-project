### Windows Gold ###
build {
  name = "windows"
  source "source.amazon-ebs.windows" {
    name       = "win-base"
    ami_name   = "win2019-gold-${local.datetime}"
    source_ami = data.amazon-ami.win-base.id
    run_tags = {
      Name     = "win2019-ms-gold-coalfire"
      OSType   = "Windows"
      OSFamily = "Windows2019"
      Release  = "${local.datetime}"
    }
    tags = {
      Name     = "win2019-ms-gold-coalfire"
      OSType   = "Windows"
      OSFamily = "Windows2019"
      Release  = "${local.datetime}"
    }
  }
  source "source.amazon-ebs.windows" {
    name       = "win-asg"
    ami_name   = "win2019-asg-gold-${local.datetime}"
    source_ami = data.amazon-ami.win-base.id
    run_tags = {
      Name     = "win2019-asg-ms-gold-coalfire"
      OSType   = "Windows"
      OSFamily = "Windows2019"
      Release  = "${local.datetime}"
    }
    tags = {
      Name     = "win2019-asg-ms-gold-coalfire"
      OSType   = "Windows"
      OSFamily = "Windows2019"
      Release  = "${local.datetime}"
    }
  }

  provisioner "powershell" {
    inline = [
      "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12",
      "Install-PackageProvider -Name NuGet -Force",
      "Start-Sleep -s 5",
      "setx /M EC2LAUNCH_TELEMETRY 0",
      "Uninstall-WindowsFeature -Name FS-SMB1"
    ]
  }

  provisioner "powershell" {
    inline = [
      "if (!(Test-Path -Path $PROFILE.AllUsersCurrentHost)) {\n  New-Item -ItemType File -Path $PROFILE.AllUsersCurrentHost -Force\n}",
      "echo \"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12\" | Out-File -FilePath $PROFILE.AllUsersCurrentHost"
    ]
  }
  provisioner "powershell" {
    only = ["amazon-ebs.win-asg"]
    environment_vars = [
        "AWS_REGION=${var.aws_region}",
        "SPLUNK_DOWNLOAD_URL=${local.splunk_win_download_url}",
        "SPLUNK_FILENAME=${local.splunk_win_file_name}"
    ]
    script = "./scripts/windows/Install-Agents.ps1"
  }
  ### Hardening ###
  # We're assuming STIG for Fedramp Rev 5
  # Download from https://public.cyber.mil/stigs/downloads/
  # Search for Windows Server 2019 STIG (NOT GPOs)
  # This will be in the "Supporting Files" folder
  provisioner "file" {
    destination = "C:\\Windows\\Temp\\"
    source      = "./files/windows/DOD_EP_V3.xml"
  }
  provisioner "powershell" {
    inline = ["Set-ProcessMitigation -PolicyFilePath 'C:\\Windows\\Temp\\DOD_EP_V3.xml'"]
  }
  provisioner "powershell" {
    environment_vars = [
      "install_root_url=${local.install_root_url}",
      "install_root_downloadpath=C:\\Windows\\Temp\\",
      "install_root_filepath=C:\\Windows\\Temp\\${var.install_root_file}"
    ]
    script = "./scripts/windows/pk-dod-install-root.ps1"
  }

  provisioner "windows-restart" {
  }

  provisioner "powershell" {
    inline = [
      "& 'C:/Program Files/Amazon/EC2Launch/ec2launch' reset",
      "& 'C:/Program Files/Amazon/EC2Launch/ec2launch' sysprep --shutdown"
    ]
  }
}