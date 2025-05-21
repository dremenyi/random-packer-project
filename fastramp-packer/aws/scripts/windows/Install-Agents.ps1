### Variables ###
# Global
[string]$aws_region = $env:AWS_REGION
# Splunk
[string]$splunkuf_url = $env:SPLUNK_DOWNLOAD_URL
[string]$splunk_filename = $env:SPLUNK_FILENAME

$ErrorActionPreference = "Stop"

$deployed_siem = (Get-SSMParameter -Name "/production/siem" -WithDecryption $true -Region $aws_region).Value
$domain_name = (Get-SSMParameter -Name "/production/packer/domain_name" -WithDecryption $true -Region $aws_region).Value
$splunk_deployment_server_port = "splunkds1." + $domain_name + ":8089"
$splunk_password = (Get-SSMParameter -Name "/production/mgmt/splunk/user_password" -WithDecryption $true -Region $aws_region).Value

### Install Splunk Agent ###
if($deployed_siem -eq "splunk"){
# Download the agent direct from splunk.
Write-Output "Downloading Splunk agent from $splunkuf_url to C:\Windows\Temp\$splunk_filename"
Invoke-WebRequest -Uri "$splunkuf_url" -OutFile "C:\Windows\Temp\$splunk_filename" -Verbose
# Setup the command line arguments
$MSIArguments = @(
    "/i"
    ('"{0}"' -f "C:\Windows\Temp\$splunk_filename")
    "LAUNCHSPLUNK=0"
    "AGREETOLICENSE=Yes"
    "/quiet"
    "/L*v $env:LogPath\splunk_uf.log"
)
Start-Process "msiexec.exe" -ArgumentList $MSIArguments -Wait -NoNewWindow

$SplunkHome = "C:\Program Files\SplunkUniversalForwarder"
#Enable FIPS
$launchconf = @"
SPLUNK_HOME=$SplunkHome
PYTHONHTTPSVERIFY=0
SPLUNK_SERVER_NAME=Splunkd
SPLUNK_FIPS=1
"@

Set-Content -Path "$SplunkHome\etc\splunk-launch.conf" -Value $launchconf -Force

#Create "deploymentclient.conf"
$deployconf = @"
[target-broker:deploymentServer]
targetUri = $splunk_deployment_server_port
"@

Set-Content -Path "$SplunkHome\etc\system\local\deploymentclient.conf" -Value $deployconf -Force

#Create user-seed.conf
$seedconf = @"
[user_info]
USERNAME = admin
PASSWORD = $splunk_password
"@
Set-Content -Path "$SplunkHome\etc\system\local\user-seed.conf" -Value $seedconf -Force

#Create server.conf
$serverconf = @"
[sslConfig]
sslVersions = tls1.2
cipherSuite = ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256
ecdhCurves =  prime256v1, secp384r1, secp521r1
useSplunkdSSLCompression = false
useClientSSLCompression = false
allowSslCompression = false
"@
Set-Content -Path "$SplunkHome\etc\system\local\server.conf" -Value $serverconf -Force
}

### Install Trend Agent ###
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
   Write-Warning "You are not running as an Administrator. Please try again with admin privileges."
   exit 1
}

$managerUrl="https://dsm1:4119/"

$env:LogPath = "$env:appdata\Trend Micro\Deep Security Agent\installer"
New-Item -path $env:LogPath -type directory
Start-Transcript -path "$env:LogPath\dsa_deploy.log" -append

Write-Output "$(Get-Date -format T) - DSA download started"
if ( [intptr]::Size -eq 8 ) { 
   $sourceUrl=-join($managerUrl, "software/agent/Windows/x86_64/agent.msi") }
else {
   $sourceUrl=-join($managerUrl, "software/agent/Windows/i386/agent.msi") }
Write-Output "$(Get-Date -format T) - Download Deep Security Agent Package" $sourceUrl

$WebClient = New-Object System.Net.WebClient

# Add agent version control info
$WebClient.Headers.Add("Agent-Version-Control", "on")
$WebClient.QueryString.Add("tenantID", "")
$WebClient.QueryString.Add("windowsVersion", (Get-CimInstance Win32_OperatingSystem).Version)
$WebClient.QueryString.Add("windowsProductType", (Get-CimInstance Win32_OperatingSystem).ProductType)

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;
[Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}
$WebClient.DownloadFile($sourceUrl,  "$env:temp\agent.msi")

if ( (Get-Item "$env:temp\agent.msi").length -eq 0 ) {
    Write-Output "Failed to download the Deep Security Agent. Please check if the package is imported into the Deep Security Manager. "
 exit 1
}
Write-Output "$(Get-Date -format T) - Downloaded File Size:" (Get-Item "$env:temp\agent.msi").length

if ( (Get-AuthenticodeSignature "$env:temp\agent.msi").Status -ne "Valid" ) {
    Write-Output "The digital signature of Deep Security Agent is invalid."
    exit 1
}
Write-Output "Enable DSA FIPS mode ..."
Write-Output FIPSMode=1 >> C:\Windows\ds_agent.ini

Write-Output "$(Get-Date -format T) - DSA install started"
Write-Output "$(Get-Date -format T) - Installer Exit Code:" (Start-Process -FilePath msiexec -ArgumentList "/i $env:temp\agent.msi /qn ADDLOCAL=ALL /l*v `"$env:LogPath\dsa_install.log`"" -Wait -PassThru).ExitCode 

Stop-Transcript
Write-Output "$(Get-Date -format T) - DSA Deployment Finished"