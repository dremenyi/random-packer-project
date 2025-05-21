# Install the DoD Root Certificates to meet DISA STIG requirements

$ErrorActionPreference = "Stop"

# Ensure download dir exists
If(!(test-path $Env:install_root_downloadpath))
{
      New-Item -ItemType Directory -Force -Path $Env:install_root_downloadpath
}

# Set to TLS1.2
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Download the agent direct from DoD PKI.
(New-Object System.Net.WebClient).DownloadFile($Env:install_root_url, $Env:install_root_filepath)

# Setup the command line arguments
$MSIArguments = @(
    "/i"
    ('"{0}"' -f $Env:install_root_filepath)
    "/quiet"
)

Start-Process "msiexec.exe" -ArgumentList $MSIArguments -Wait -NoNewWindow

# Install the required DoD Root Certs silently
Start-Process -FilePath "C:\Program Files\DoD-PKE\InstallRoot\InstallRoot.exe" -ArgumentList "--silent" -Wait -NoNewWindow