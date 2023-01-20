-- ----------------------------
-- Table structure for ClearanceAppSubmission
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[ClearanceAppSubmission]') AND type IN ('U'))
	DROP TABLE [dbo].[ClearanceAppSubmission]
GO

CREATE TABLE [dbo].[ClearanceAppSubmission] (
  [ID] int  NOT NULL IDENTITY(1,1),
  [RequestID] [nvarchar](256) NOT NULL,
  [CampusID] [nvarchar](32)	NOT NULL,
  [ClearanceName] [nvarchar] (256) NOT NULL,
  [Enable] [nvarchar](2) NOT NULL,
  [UpdateDate] DATETIME NOT NULL,
)
GO

ALTER TABLE [dbo].[ClearanceAppSubmission] SET (LOCK_ESCALATION = TABLE)
GO

ALTER TABLE ClearanceAppSubmission
  ADD CONSTRAINT DEFAULT_DATE_CONSTRAINT
    DEFAULT GETDATE() FOR UpdateDate
-- ----------------------------
-- Primary Key structure for table LibraryClearanceFeed
-- ----------------------------
ALTER TABLE [dbo].[ClearanceAppSubmission] ADD CONSTRAINT [PK_ClearanceAppSubmission_ID] PRIMARY KEY CLUSTERED ([ID])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)
ON [PRIMARY]
GO

