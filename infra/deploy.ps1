<#
.SYNOPSIS
Deploys Second Half to Azure Container Apps, next to your Microsoft Foundry project.

.DESCRIPTION
Run it from the repository root after `az login`:

    powershell -ExecutionPolicy Bypass -File infra\deploy.ps1

It reads FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL from .env (or takes them as
parameters), finds the Foundry resource and its resource group, and deploys
infra\main.bicep with the container image GitHub Actions built for the commit
you are on (ghcr.io/<owner>/<repo>:sha-<commit>). Run it again after a push,
once the Image job has finished, to roll out the new image.
#>
param(
    [string] $FoundryProjectEndpoint,
    [string] $Model,
    [string] $Image,
    [string] $ReasoningEffort = "minimal",
    [string] $Location = "germanywestcentral",
    [ValidateRange(0, 1)] [int] $MinReplicas = 1
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12  # for Windows PowerShell 5.1
$root = Split-Path -Parent $PSScriptRoot

function Invoke-Az {
    # az is a native command, so check its exit code: $ErrorActionPreference doesn't cover those.
    $out = & az @args
    if ($LASTEXITCODE -ne 0) { throw "This step failed: az $($args -join ' ')" }
    return $out
}

# Settings from .env, unless they were given as parameters.
$settings = @{}
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $settings[$Matches[1]] = $Matches[2].Trim('"', "'")
        }
    }
}
if (-not $FoundryProjectEndpoint) { $FoundryProjectEndpoint = $settings["FOUNDRY_PROJECT_ENDPOINT"] }
if (-not $Model) { $Model = $settings["FOUNDRY_MODEL"] }
if (-not $FoundryProjectEndpoint -or -not $Model) {
    throw "Set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL in .env (or pass -FoundryProjectEndpoint and -Model)."
}

# The Foundry resource is the first part of the endpoint's host name.
$account = ([Uri]$FoundryProjectEndpoint).Host.Split(".")[0]
$group = Invoke-Az cognitiveservices account list --query "[?name=='$account'].resourceGroup" -o tsv |
    Select-Object -First 1
if (-not $group) {
    throw "Couldn't find the Foundry resource '$account' in your subscription. Is az login using the right account?"
}

# Which commit is going out; /api/health shows it.
$release = "dev"
if (Get-Command git -ErrorAction SilentlyContinue) {
    $commit = git -C $root rev-parse HEAD
    if ($LASTEXITCODE -eq 0 -and $commit) { $release = $commit.Substring(0, 7) }
}

# The image GitHub Actions built for this commit, which it tags sha-<commit>. Naming the commit rather than :latest
# makes Azure pull the new image: asked for :latest again, it can start the app from the copy it already has.
# The package has to be public so Azure can pull it.
if (-not $Image) {
    if ($release -eq "dev") {
        throw "Couldn't read the current commit from git; pass -Image ghcr.io/<owner>/<repo>:sha-<commit>."
    }
    $origin = git -C $root remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $origin -notmatch 'github\.com[:/](.+?)(\.git)?/?$') {
        throw "Couldn't work out the GitHub repository from git; pass -Image ghcr.io/<owner>/<repo>:sha-<commit>."
    }
    $repo = $Matches[1].ToLower()
    $Image = "ghcr.io/$($repo):sha-$release"
    try {
        $token = (Invoke-RestMethod -Uri "https://ghcr.io/token?scope=repository:$($repo):pull").token
        $accept = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json"
        Invoke-WebRequest -Method Head -UseBasicParsing -Uri "https://ghcr.io/v2/$repo/manifests/sha-$release" `
            -Headers @{ Authorization = "Bearer $token"; Accept = $accept } | Out-Null
    } catch {
        throw ("Azure can't pull $Image yet. Push commit $release and wait for the Image job in GitHub Actions to " +
            "finish. If it has, check that the package is public: GitHub > your profile > Packages > second-half > " +
            "Package settings > Change visibility.")
    }
}

# Foundry User used to be called Azure AI User; the role id is the same.
$roleId = Invoke-Az role definition list --name "Foundry User" --query "[0].name" -o tsv
if (-not $roleId) { $roleId = Invoke-Az role definition list --name "Azure AI User" --query "[0].name" -o tsv }
if (-not $roleId) { throw "Couldn't find the Foundry User role in your subscription." }

Write-Host "Making sure Container Apps is enabled on your subscription (slow only the first time)..."
Invoke-Az provider register --namespace Microsoft.App --wait | Out-Null
Invoke-Az provider register --namespace Microsoft.OperationalInsights --wait | Out-Null

Write-Host "Deploying $Image ($release) to $group in $Location..."
$url = Invoke-Az deployment group create --resource-group $group --name second-half `
    --template-file (Join-Path $PSScriptRoot "main.bicep") `
    --parameters location=$Location image=$Image foundryAccountName=$account `
    foundryProjectEndpoint=$FoundryProjectEndpoint foundryModel=$Model reasoningEffort=$ReasoningEffort `
    foundryUserRoleId=$roleId release=$release minReplicas=$MinReplicas `
    --query properties.outputs.url.value -o tsv

Write-Host ""
Write-Host "Second Half is live at $url"
Write-Host "MCP endpoint: $url/mcp"
Write-Host "On a first deploy, Azure can take a few minutes to apply the app's Foundry role. Until then the"
Write-Host "agents put out plain stat cards, and the agent trace says the sign-in was refused."
