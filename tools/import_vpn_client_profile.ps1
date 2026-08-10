#requires -Version 5.1
<#
.SYNOPSIS
  Generates a fresh Azure VPN Client (P2S) profile package for vpngw-purview,
  downloads/extracts it, and stages the AAD-auth XML config for import into the
  Azure VPN Client desktop app.

.DESCRIPTION
  The Azure VPN Client desktop app has no scriptable "import" command, so this
  script automates everything up to that point: it asks Azure for a fresh
  download URL (the SAS token is short-lived, ~1 hour), downloads the zip,
  extracts it, locates AzureVPN\azurevpnconfig.xml, and opens Explorer with
  that file selected plus launches the Azure VPN Client app so the last step
  (Import > file) is a couple of clicks.

.PARAMETER GatewayName
  Name of the virtual network gateway. Default: vpngw-purview

.PARAMETER ResourceGroup
  Resource group containing the gateway. Default: AzureWest3-RG

.PARAMETER SubscriptionId
  Subscription name or ID. Default: ME-MngEnvMCAP660444-seankelley-3

.PARAMETER OutputDir
  Local folder to extract the profile package into.
  Default: $env:USERPROFILE\Downloads\AzureVpnProfile-purview

.EXAMPLE
  .\import_vpn_client_profile.ps1
#>
param(
    [string]$GatewayName = "vpngw-purview",
    [string]$ResourceGroup = "AzureWest3-RG",
    [string]$SubscriptionId = "ME-MngEnvMCAP660444-seankelley-3",
    [string]$OutputDir = "$env:USERPROFILE\Downloads\AzureVpnProfile-purview"
)

$ErrorActionPreference = "Stop"

Write-Host "Requesting a fresh VPN client profile package (AAD/OpenVPN auth) for '$GatewayName'..." -ForegroundColor Cyan
$downloadUrl = az network vnet-gateway vpn-client generate `
    --name $GatewayName `
    --resource-group $ResourceGroup `
    --subscription $SubscriptionId `
    --authentication-method EAPTLS `
    -o tsv

if (-not $downloadUrl) {
    throw "Failed to generate VPN client profile package URL. Check the gateway name/resource group/subscription."
}

if (Test-Path $OutputDir) {
    Remove-Item -Path $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputDir | Out-Null

$zipPath = Join-Path $OutputDir "vpnclientconfiguration.zip"
Write-Host "Downloading profile package..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

Write-Host "Extracting..." -ForegroundColor Cyan
Expand-Archive -Path $zipPath -DestinationPath $OutputDir -Force

$configXml = Get-ChildItem -Path $OutputDir -Filter "azurevpnconfig_aad.xml" -Recurse | Select-Object -First 1
if (-not $configXml) {
    # Fall back to the default name used when only one auth type is enabled.
    $configXml = Get-ChildItem -Path $OutputDir -Filter "azurevpnconfig.xml" -Recurse | Select-Object -First 1
}
if (-not $configXml) {
    throw "azurevpnconfig_aad.xml not found under $OutputDir. The package may only contain a Generic/Certificate profile - check the extracted folders."
}

Write-Host "`nFound AAD-auth config: $($configXml.FullName)" -ForegroundColor Green

# Open Explorer with the file selected, and try to launch the Azure VPN Client app.
Start-Process explorer.exe "/select,`"$($configXml.FullName)`""
Start-Process "azurevpnclient:" -ErrorAction SilentlyContinue

Write-Host "`nManual import steps (Azure VPN Client desktop app has no CLI import):" -ForegroundColor Yellow
Write-Host "  1. In the Azure VPN Client app, click '+' > 'Import'."
Write-Host "  2. Choose 'A file' and select the highlighted azurevpnconfig.xml in the Explorer window that just opened."
Write-Host "  3. Save the connection, click 'Connect', and sign in with your Entra ID account when prompted."
Write-Host "`nNote: the download URL is time-limited (~1 hour). Re-run this script if it expires before you import." -ForegroundColor DarkGray
