:setvar DatabaseName "leverance"

SET NOCOUNT ON;

IF DB_ID(N'$(DatabaseName)') IS NULL
BEGIN
    DECLARE @create_db_sql NVARCHAR(MAX) =
        N'CREATE DATABASE ' + QUOTENAME(N'$(DatabaseName)') + N' COLLATE Danish_Norwegian_CI_AS;';

    EXEC sys.sp_executesql @create_db_sql;
    PRINT N'Database [' + N'$(DatabaseName)' + N'] created with collation Danish_Norwegian_CI_AS.';
END
ELSE
BEGIN
    PRINT N'Database [' + N'$(DatabaseName)' + N'] already exists. Skipping CREATE DATABASE.';
END;
GO

DECLARE @current_collation SYSNAME = (
    SELECT collation_name
    FROM sys.databases
    WHERE name = N'$(DatabaseName)'
);

IF @current_collation <> N'Danish_Norwegian_CI_AS'
BEGIN
    PRINT N'Warning: database [' + N'$(DatabaseName)' + N'] already exists with collation ['
        + COALESCE(@current_collation, N'<unknown>')
        + N'], expected [Danish_Norwegian_CI_AS].';
END;
GO
