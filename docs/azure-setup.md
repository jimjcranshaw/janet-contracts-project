# Azure Database Setup Guide

## Prerequisites

- Azure CLI installed: `az --version`
- Logged in to Azure: `az login`
- Azure subscription with free credits

## Step 1: Deploy Infrastructure

Navigate to project directory and deploy:

```powershell
cd "C:\Users\jimcr\OneDrive\Documents\Consultancy\Current projects\Grants AI\Development\Janet Contracts Project"

# Set variables
$RESOURCE_GROUP = "rg-grantsai-dev"
$LOCATION = "uksouth"
$ADMIN_PASSWORD = "YourSecurePassword123!"  # Change this!

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Deploy Bicep template
az deployment group create `
  --resource-group $RESOURCE_GROUP `
  --template-file infra/main.bicep `
  --parameters envName=dev adminPassword=$ADMIN_PASSWORD
```

**Expected output**: Deployment will take ~5-10 minutes. You'll get the PostgreSQL FQDN in the output.

## Step 2: Enable pgvector Extension

After deployment completes, connect and enable pgvector:

```powershell
# Get connection details
$POSTGRES_FQDN = az deployment group show `
  --resource-group $RESOURCE_GROUP `
  --name main `
  --query properties.outputs.postgresFqdn.value `
  --output tsv

Write-Host "Postgres FQDN: $POSTGRES_FQDN"

# Install psql if not already installed
# Download from: https://www.postgresql.org/download/windows/
# Or use Azure Cloud Shell

# Connect to database
psql "host=$POSTGRES_FQDN port=5432 dbname=procurement_matching user=grantsadmin sslmode=require"
```

Once connected, run:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
\dx

-- You should see 'vector' in the list
```

## Step 3: Create .env File

Create `.env` in the project root with your connection string:

```env
# Database Connection
DATABASE_URL=postgresql://grantsadmin:YourSecurePassword123!@${POSTGRES_FQDN}:5432/procurement_matching?sslmode=require

# OpenAI API Key (for embeddings)
OPENAI_API_KEY=sk-your-key-here

# Optional: Logging
LOG_LEVEL=INFO
```

**Security Note**: Never commit `.env` to git!

## Step 4: Run Database Migrations

Create the schema:

```powershell
# Install Alembic if not already installed
pip install alembic

# Initialize Alembic (one-time)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

## Step 5: Test Connection

Test that everything works:

```powershell
python -c "
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print('PostgreSQL version:', result.fetchone()[0])
    
    result = conn.execute(text('SELECT * FROM pg_extension WHERE extname = ''vector'''))
    if result.fetchone():
        print('✓ pgvector extension enabled')
    else:
        print('✗ pgvector extension NOT enabled')
"
```

## Troubleshooting

### Issue: Can't connect to database

**Solution**: Check firewall rules
```powershell
# Get your public IP
$MY_IP = (Invoke-WebRequest -Uri "https://api.ipify.org").Content

# Update firewall rule
az postgres flexible-server firewall-rule update `
  --resource-group $RESOURCE_GROUP `
  --name psql-grantsai-dev-uk `
  --rule-name AllowLocalDevelopment `
  --start-ip-address $MY_IP `
  --end-ip-address $MY_IP
```

### Issue: pgvector not available

**Solution**: Enable extension manually
```sql
-- Connect as admin user
CREATE EXTENSION IF NOT EXISTS vector;
```

### Issue: Deployment fails

**Solution**: Check resource limits
```powershell
# Check if name is available
az postgres flexible-server check-name-availability `
  --name psql-grantsai-dev-uk `
  --resource-group $RESOURCE_GROUP
```

## Cost Optimization Tips

- **Development**: Use `Burstable` tier (already configured)
- **Testing**: Stop server when not in use:
  ```powershell
  az postgres flexible-server stop --resource-group $RESOURCE_GROUP --name psql-grantsai-dev-uk
  ```
- **Cleanup**: Delete resource group when done:
  ```powershell
  az group delete --name $RESOURCE_GROUP --yes
  ```

## Next Steps

Once deployment is complete:
1. ✅ Deploy infrastructure
2. ✅ Enable pgvector
3. ✅ Create .env file
4. ✅ Run migrations
5. ⏭️ **Run ingestion worker** (see `scripts/run_ingestion.py`)
