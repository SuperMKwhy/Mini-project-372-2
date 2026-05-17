-- ============================================================
-- Error log table (run once)
-- ============================================================
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'webhook_error_log'
)
BEGIN
    CREATE TABLE webhook_error_log (
        id           INT           NOT NULL IDENTITY(1,1) PRIMARY KEY,
        trigger_name NVARCHAR(100) NOT NULL,
        picking_id   INT           NULL,
        error_msg    NVARCHAR(MAX) NOT NULL,
        failed_at    DATETIME      NOT NULL DEFAULT GETDATE()
    );
END
GO

-- ============================================================
-- Trigger: S3a
-- ============================================================
CREATE OR ALTER TRIGGER trg_S3a_AfterInsert
ON S3A_STATIC_LOGS
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @picking_id INT;
    DECLARE @payload    NVARCHAR(MAX);

    BEGIN TRY
        SELECT @picking_id = so.picking_id
        FROM inserted i
        LEFT JOIN sale_order so ON so.name = i.order_id;

        IF @picking_id IS NULL
        BEGIN
            INSERT INTO webhook_error_log (trigger_name, picking_id, error_msg)
            VALUES ('trg_S3a_AfterInsert', NULL, 'picking_id not found in sale_order');
            RETURN;
        END

        SET @payload = N'{"picking_id":' + CAST(@picking_id AS NVARCHAR) + N'}';

        EXEC sp_invoke_external_rest_endpoint
            @url     = N'https://your-app.azurewebsites.net/api/odoo-s3-notify?code=YOUR_KEY',
            @method  = 'POST',
            @headers = N'{"Content-Type":"application/json"}',
            @payload = @payload;
    END TRY
    BEGIN CATCH
        -- XACT_STATE() = -1 means the transaction is doomed; no DML allowed.
        -- We skip logging in that case so the error does not propagate and kill the INSERT.
        IF XACT_STATE() <> -1
        BEGIN
            INSERT INTO webhook_error_log (trigger_name, picking_id, error_msg)
            VALUES ('trg_S3a_AfterInsert', @picking_id, ERROR_MESSAGE());
        END
    END CATCH
END
GO

-- ============================================================
-- Trigger: S3b
-- ============================================================
CREATE OR ALTER TRIGGER trg_S3b_AfterInsert
ON S3B_STATIC_LOGS
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @picking_id INT;
    DECLARE @payload    NVARCHAR(MAX);

    BEGIN TRY
        SELECT @picking_id = so.picking_id
        FROM inserted i
        LEFT JOIN sale_order so ON so.name = i.order_id;

        IF @picking_id IS NULL
        BEGIN
            INSERT INTO webhook_error_log (trigger_name, picking_id, error_msg)
            VALUES ('trg_S3b_AfterInsert', NULL, 'picking_id not found in sale_order');
            RETURN;
        END

        SET @payload = N'{"picking_id":' + CAST(@picking_id AS NVARCHAR) + N'}';

        EXEC sp_invoke_external_rest_endpoint
            @url     = N'https://your-app.azurewebsites.net/api/odoo-s3-notify?code=YOUR_KEY',
            @method  = 'POST',
            @headers = N'{"Content-Type":"application/json"}',
            @payload = @payload;
    END TRY
    BEGIN CATCH
        -- XACT_STATE() = -1 means the transaction is doomed; no DML allowed.
        -- We skip logging in that case so the error does not propagate and kill the INSERT.
        IF XACT_STATE() <> -1
        BEGIN
            INSERT INTO webhook_error_log (trigger_name, picking_id, error_msg)
            VALUES ('trg_S3b_AfterInsert', @picking_id, ERROR_MESSAGE());
        END
    END CATCH
END
GO
