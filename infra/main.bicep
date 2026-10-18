// Second Half on Azure Container Apps, next to an existing Microsoft Foundry resource.
// Deploy with infra/deploy.ps1, which fills in these parameters.

@description('Region for the app. It must be one your subscription allows.')
param location string = resourceGroup().location

@description('Name of the container app; it also prefixes the environment and log workspace.')
param appName string = 'second-half'

@description('Container image to run, for example ghcr.io/<owner>/second-half:latest.')
param image string

@description('Name of the Foundry resource (in this resource group) that hosts the model.')
param foundryAccountName string

@description('The Foundry project endpoint: https://<resource>.services.ai.azure.com/api/projects/<project>.')
param foundryProjectEndpoint string

@description('The model deployment name in the Foundry project.')
param foundryModel string = 'gpt-5-mini'

@description('Reasoning effort for gpt-5 family models: minimal (gpt-5, -mini, -nano), none (gpt-5.1+), low, or empty.')
param reasoningEffort string = 'minimal'

@description('Role definition id of the built-in Foundry User role (formerly Azure AI User).')
param foundryUserRoleId string

@description('Which commit is running; shown by /api/health. A new value rolls out a new revision.')
param release string = 'dev'

@description('1 keeps the app warm for visitors; 0 lets it sleep when unused (the first visit then waits).')
@minValue(0)
@maxValue(1)
param minReplicas int = 1

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${appName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: { type: 'SystemAssigned' } // signs in to Foundry; no keys anywhere
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'FOUNDRY_MODEL', value: foundryModel }
            { name: 'FOUNDRY_REASONING_EFFORT', value: reasoningEffort }
            // The MCP endpoint only answers requests addressed to this app's own host name.
            { name: 'MCP_ALLOWED_HOSTS', value: '${appName}.${environment.properties.defaultDomain}' }
            { name: 'SECOND_HALF_RELEASE', value: release }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      // Live matches are held in memory and shared by every viewer, so there is exactly one replica.
      scale: { minReplicas: minReplicas, maxReplicas: 1 }
    }
  }
}

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

// Lets the app's identity call models in the Foundry project.
resource foundryAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, app.id, foundryUserRoleId)
  scope: foundry
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
  }
}

output url string = 'https://${app.properties.configuration.ingress.fqdn}'
