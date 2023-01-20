USE [DataFeed]
GO

/****** Object:  Trigger [dbo].[TRG_INSERT_ClearanceAppSubmission]    Script Date: 10/6/2021 1:47:33 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


CREATE OR ALTER TRIGGER [dbo].[TRG_INSERT_ClearanceAppSubmission]
ON [dbo].[ClearanceAppSubmission]
FOR INSERT
AS
SET NOCOUNT ON
BEGIN
    INSERT INTO LibraryClearanceFeed
    SELECT
        concat ( CampusID, ':0' ) AS CIDC,
        CASE
            Enable
            WHEN 'Y' THEN
            ClearanceName
            WHEN 'N' THEN
            concat ( '-', ClearanceName )
        END ClearanceName
    FROM inserted
END
GO

ALTER TABLE [dbo].[ClearanceAppSubmission] ENABLE TRIGGER [TRG_INSERT_ClearanceAppSubmission]
GO


