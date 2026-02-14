# Azure Database Deployment - Quick Start

This guide will get you from zero to a working database with real procurement data.

## Quick Deploy (5 commands)

```powershell
# 1. Set your password
$ADMIN_PASSWORD = "YourSecurePassword123!"  # CHANGE THIS!

# 2. Deploy to Azure
cd "C:\Users\jimcr\OneDrive\Documents\Consultancy\Current projects\Grants AI\Development\Janet Contracts Project"
az group create --name rg-grantsai-dev --location uksouth
az deployment group create --resource-group rg-grantsai-dev --template-file infra/main.bicep --parameters envName=dev adminPassword=$ADMIN_PASSWORD

# 3. Get connection string
$POSTGRES_FQDN = az deployment group show --resource-group rg-grantsai-dev --name main --query properties.outputs.postgresFqdn.value --output tsv
Write-Host "Database: $POSTGRES_FQDN"

# 4. Create .env file (replace PASSWORD)
@"
DATABASE_URL=postgresql://grantsadmin:$ADMIN_PASSWORD@$POSTGRES_FQDN`:5432/procurement_matching?sslmode=require
OPENAI_API_KEY=sk-your-openai-key-here
LOG_LEVEL=INFO
"@ | Out-File -FilePath .env -Encoding utf8

# 5. Initialize database
python scripts/init_db.py
```

## Run Ingestion

After database is set up:

```powershell
# Fetch last 7 days of contracts
python scripts/run_ingestion.py --days 7

# Validate data
python scripts/validate_data.py
```

## Troubleshooting

**Can't connect?** Check your IP is allowed:
```powershell
$MY_IP = (Invoke-WebRequest -Uri "https://api.ipify.org").Content
az postgres flexible-server firewall-rule create --resource-group rg-grantsai-dev --name psql-grantsai-dev-uk --rule-name MyIP --start-ip-address $MY_IP --end-ip-address $MY_IP
```

**pgvector missing?** Enable it manually:
```powershell
psql "host=$POSTGRES_FQDN port=5432 dbname=procurement_matching user=grantsadmin sslmode=require"
# Then run: CREATE EXTENSION IF NOT EXISTS vector;
```

For detailed guide, see `docs/azure-setup.md`
