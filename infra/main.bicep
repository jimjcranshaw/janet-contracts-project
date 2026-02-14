@description('The location for all resources.')
param location string = resourceGroup().location

@description('The name of the environment (e.g. "prod", "dev")')
param envName string = 'prod'

@description('Postgres Administrator Login')
param adminLogin string = 'grantsadmin'

@secure()
@description('Postgres Administrator Password')
param adminPassword string

// Storage Account
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name = 'stgrantsai${envName}uk'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}

resource tenderContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: resourceId('Microsoft.Storage/storageAccounts/blobServices', storage.name, 'default')
  name: 'tender-packages'
  properties: {
    publicAccess: 'None'
  }
}

// Postgres Flexible Server
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' = {
  name: 'psql-grantsai-${envName}-uk'
  location: location
  sku: {
    name: 'Standard_B1ms'  // Burstable tier for dev (cheaper)
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: adminLogin
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: 32
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// Allow access from your local machine
resource firewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2022-12-01' = {
  parent: postgres
  name: 'AllowLocalDevelopment'
  properties: {
    startIpAddress: '0.0.0.0'  // TODO: Replace with your actual IP for security
    endIpAddress: '255.255.255.255'
  }
}

// Create database
resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2022-12-01' = {
  parent: postgres
  name: 'procurement_matching'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Enable pgvector extension
resource pgvectorExtension 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2022-12-01' = {
  parent: postgres
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR'
    source: 'user-override'
  }
}

// Container Registry
resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: 'acrgrantsai${envName}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2022-11-01-preview' = {
  name: 'cae-grantsai-${envName}-uk'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-grantsai-${envName}-uk'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

output storageAccountName string = storage.name
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
output acrLoginServer string = acr.properties.loginServer
