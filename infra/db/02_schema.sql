:setvar DatabaseName "leverance"

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;

IF DB_ID(N'$(DatabaseName)') IS NULL
BEGIN
    THROW 50000, 'Database $(DatabaseName) does not exist. Run 01_create_database.sql first.', 1;
END;
GO

USE [$(DatabaseName)];
GO

IF SCHEMA_ID(N'jn') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA jn');
END;
GO

IF OBJECT_ID(N'jn.prompts', N'U') IS NULL
BEGIN
    CREATE TABLE jn.prompts (
        prompt_id INT IDENTITY(1,1) NOT NULL,
        model NVARCHAR(100) NOT NULL,
        prompt NVARCHAR(MAX) NOT NULL,
        ordning NVARCHAR(100) NOT NULL,
        er_evaluering TINYINT NOT NULL,
        api_version NVARCHAR(50) NOT NULL,
        sekvens_nr NVARCHAR(10) NOT NULL,
        load_time DATETIME2(7) NOT NULL CONSTRAINT DF_jn_prompts_load_time DEFAULT SYSDATETIME(),
        CONSTRAINT PK_jn_prompts PRIMARY KEY CLUSTERED (prompt_id),
        CONSTRAINT CK_jn_prompts_er_evaluering CHECK (er_evaluering IN (0, 1))
    );
END;
GO

IF OBJECT_ID(N'jn.notat', N'U') IS NULL
BEGIN
    CREATE TABLE jn.notat (
        call_id NVARCHAR(255) NULL,
        genererings_prompt_id INT NULL,
        validerings_prompt_id INT NULL,
        queue NVARCHAR(255) NULL,
        kr_initialer NVARCHAR(50) NULL,
        forretningsomraade NVARCHAR(100) NULL,
        notat NVARCHAR(MAX) NULL,
        load_time DATETIME2(7) NOT NULL CONSTRAINT DF_jn_notat_load_time DEFAULT SYSDATETIME(),
        CONSTRAINT FK_jn_notat_genererings_prompt FOREIGN KEY (genererings_prompt_id) REFERENCES jn.prompts (prompt_id),
        CONSTRAINT FK_jn_notat_validerings_prompt FOREIGN KEY (validerings_prompt_id) REFERENCES jn.prompts (prompt_id)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'UX_jn_notat_call_id'
      AND object_id = OBJECT_ID(N'jn.notat')
)
BEGIN
    CREATE UNIQUE NONCLUSTERED INDEX UX_jn_notat_call_id
        ON jn.notat (call_id)
        WHERE call_id IS NOT NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_jn_notat_kr_initialer_load_time'
      AND object_id = OBJECT_ID(N'jn.notat')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_jn_notat_kr_initialer_load_time
        ON jn.notat (kr_initialer, load_time DESC);
END;
GO

IF OBJECT_ID(N'jn.samtale', N'U') IS NULL
BEGIN
    CREATE TABLE jn.samtale (
        call_id NVARCHAR(255) NULL,
        queue NVARCHAR(255) NULL,
        kr_initialer NVARCHAR(50) NULL,
        tekststykke NVARCHAR(MAX) NULL,
        rolle NVARCHAR(50) NULL,
        sekvens_nr INT NULL,
        load_time DATETIME2(7) NOT NULL CONSTRAINT DF_jn_samtale_load_time DEFAULT SYSDATETIME()
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'UX_jn_samtale_call_id_sekvens_nr'
      AND object_id = OBJECT_ID(N'jn.samtale')
)
BEGIN
    CREATE UNIQUE NONCLUSTERED INDEX UX_jn_samtale_call_id_sekvens_nr
        ON jn.samtale (call_id, sekvens_nr)
        WHERE call_id IS NOT NULL AND sekvens_nr IS NOT NULL;
END;
GO

IF OBJECT_ID(N'jn.notat_feedback', N'U') IS NULL
BEGIN
    CREATE TABLE jn.notat_feedback (
        call_id NVARCHAR(255) NOT NULL,
        agent_id NVARCHAR(50) NOT NULL,
        feedback NVARCHAR(MAX) NOT NULL,
        rating INT NOT NULL,
        benyttet TINYINT NOT NULL,
        load_time DATETIME2(7) NOT NULL CONSTRAINT DF_jn_notat_feedback_load_time DEFAULT SYSDATETIME(),
        CONSTRAINT CK_jn_notat_feedback_rating CHECK (rating BETWEEN -1 AND 5),
        CONSTRAINT CK_jn_notat_feedback_benyttet CHECK (benyttet IN (0, 1))
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_jn_notat_feedback_call_id_load_time'
      AND object_id = OBJECT_ID(N'jn.notat_feedback')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_jn_notat_feedback_call_id_load_time
        ON jn.notat_feedback (call_id, load_time DESC)
        INCLUDE (agent_id, rating, benyttet);
END;
GO

IF OBJECT_ID(N'jn.config', N'U') IS NULL
BEGIN
    CREATE TABLE jn.config (
        kr_initialer NVARCHAR(50) NOT NULL,
        miljoe NVARCHAR(20) NOT NULL,
        streamer_version NVARCHAR(50) NOT NULL,
        transcriber_version NVARCHAR(50) NOT NULL,
        chatgpt_version NVARCHAR(50) NOT NULL,
        controller_version NVARCHAR(50) NOT NULL,
        forretningsomraade NVARCHAR(100) NOT NULL,
        load_time DATETIME2(7) NOT NULL CONSTRAINT DF_jn_config_load_time DEFAULT SYSDATETIME(),
        CONSTRAINT PK_jn_config PRIMARY KEY CLUSTERED (kr_initialer)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_jn_prompts_ordning_sekvens_nr_load_time'
      AND object_id = OBJECT_ID(N'jn.prompts')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_jn_prompts_ordning_sekvens_nr_load_time
        ON jn.prompts (ordning, sekvens_nr, load_time DESC)
        INCLUDE (model, er_evaluering, api_version);
END;
GO
