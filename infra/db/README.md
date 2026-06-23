# JN-assistent database scripts

SQL Server scripts til JN-assistentens business-database.

## Filer

- `01_create_database.sql` — opretter databasen (default: `leverance`) med collation `Danish_Norwegian_CI_AS`
- `02_schema.sql` — opretter schema `jn` og tabellerne `jn.notat`, `jn.samtale`, `jn.notat_feedback`, `jn.prompts`, `jn.config`
- `03_seed.sql` — indsætter basis-prompts og en testkonfiguration for agent `TEST`
- `init.sh` — venter på SQL Server og kører scripts i rækkefølge via `sqlcmd`

## Krav

- `sqlcmd` fra `mssql-tools18`
- Adgang til SQL Server med en bruger, der kan oprette database/schema/tabeller

## Kør via init-script

```bash
chmod +x infra/db/init.sh
MSSQL_HOST=mssql \
MSSQL_SA_PASSWORD='YourStrong(!)Password' \
LEVERANCE_BUSINESS_DATABASE_NAME=leverance \
./infra/db/init.sh
```

Valgfrie miljøvariabler:

- `MSSQL_PORT` — default `1433`
- `MSSQL_SA_USER` — default `sa`
- `MSSQL_WAIT_TIMEOUT` — default `120`
- `MSSQL_WAIT_INTERVAL` — default `2`

## Kør manuelt med sqlcmd

```bash
sqlcmd -C -S mssql,1433 -U sa -P 'YourStrong(!)Password' -d master \
  -i infra/db/01_create_database.sql -v DatabaseName=leverance

sqlcmd -C -S mssql,1433 -U sa -P 'YourStrong(!)Password' -d master \
  -i infra/db/02_schema.sql -v DatabaseName=leverance

sqlcmd -C -S mssql,1433 -U sa -P 'YourStrong(!)Password' -d master \
  -i infra/db/03_seed.sql -v DatabaseName=leverance
```

## Bemærkninger

- `jn.config` bliver slået op som `jn.config` (2-part navn) i applikationen, så forbindelsens default database skal være den samme som `LEVERANCE_BUSINESS_DATABASE_NAME`.
- Scripts er skrevet med `IF NOT EXISTS`/eksistenskontrol, så de kan køres flere gange uden at oprette dubletter.
- Seed bruger agent `TEST`, fordi end-to-end testen forventer denne agent-id.
