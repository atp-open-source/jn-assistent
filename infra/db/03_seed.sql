:setvar DatabaseName "leverance"

SET NOCOUNT ON;

IF DB_ID(N'$(DatabaseName)') IS NULL
BEGIN
    THROW 50000, 'Database $(DatabaseName) does not exist. Run 01_create_database.sql first.', 1;
END;
GO

USE [$(DatabaseName)];
GO

IF OBJECT_ID(N'jn.prompts', N'U') IS NULL
BEGIN
    THROW 50000, 'Table jn.prompts does not exist. Run 02_schema.sql first.', 1;
END;

IF OBJECT_ID(N'jn.config', N'U') IS NULL
BEGIN
    THROW 50000, 'Table jn.config does not exist. Run 02_schema.sql first.', 1;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM jn.prompts
    WHERE ordning = N'standard'
      AND sekvens_nr = N'1'
      AND er_evaluering = 0
)
BEGIN
    INSERT INTO jn.prompts (
        model,
        prompt,
        ordning,
        er_evaluering,
        api_version,
        sekvens_nr,
        load_time
    )
    VALUES (
        N'gpt-4o',
        N'Du er kunderådgiver i Udbetaling Danmark. Skriv et kort, præcist journalnotat på dansk ud fra en transskriberet telefonsamtale mellem borger og kunderådgiver. Medtag kun oplysninger, der fremgår af samtalen. Strukturér notatet i to afsnit med overskrifterne "Oplysninger" og "Status". I Oplysninger beskrives formålet med henvendelsen, væsentlige fakta, datoer, beløb og vejledning. I Status beskrives aftaler, næste skridt, henvisninger eller viderestillinger. Hvis der ikke er en egentlig aftale, skal Status afsluttes med "Henvendelse afsluttet". Udelad CPR-numre, kontonumre, fulde navne og irrelevante høflighedsfraser. Skriv i jeg-form om kunderådgiveren.',
        N'standard',
        0,
        N'2024-10-21',
        N'1',
        SYSDATETIME()
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM jn.prompts
    WHERE ordning = N'standard'
      AND sekvens_nr = N'2'
      AND er_evaluering = 0
)
BEGIN
    INSERT INTO jn.prompts (
        model,
        prompt,
        ordning,
        er_evaluering,
        api_version,
        sekvens_nr,
        load_time
    )
    VALUES (
        N'gpt-4o',
        N'Gennemgå journalnotatet og omskriv det, så det er kortfattet, faktuelt og uden personfølsomme oplysninger. Fjern gentagelser, kønnet sprog, CPR-numre, kontonumre, fulde navne, følelsesbeskrivelser og løfter. Brug jeg-form om kunderådgiveren. Sørg for, at Status aldrig er tom; hvis der ikke er en aftale eller opfølgning, skal status være "Henvendelse afsluttet". Returnér kun gyldig JSON uden markdown og uden ekstra tekst i formatet {"oplysninger":"...","status":"..."}.',
        N'standard',
        0,
        N'2024-10-21',
        N'2',
        SYSDATETIME()
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM jn.config
    WHERE kr_initialer = N'TEST'
)
BEGIN
    INSERT INTO jn.config (
        kr_initialer,
        miljoe,
        streamer_version,
        transcriber_version,
        chatgpt_version,
        controller_version,
        forretningsomraade,
        load_time
    )
    VALUES (
        N'TEST',
        N'dev',
        N'openai',
        N'azure',
        N'azure',
        N'onprem',
        N'standard',
        SYSDATETIME()
    );
END;
GO
