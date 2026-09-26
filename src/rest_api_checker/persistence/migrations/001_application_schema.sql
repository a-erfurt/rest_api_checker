-- database_design_v1.md sections 2-4. Reviewed application schema, SQL Server 2022.
-- Runtime never executes this file. All FK actions are explicitly NO ACTION.
CREATE TABLE dbo.files (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 name NVARCHAR(512) NOT NULL,
 content VARBINARY(MAX) NOT NULL,
 sha256 CHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL UNIQUE NONCLUSTERED,
 size_bytes AS DATALENGTH(content),
 CONSTRAINT ck_files_hash CHECK (DATALENGTH(sha256)=64 AND sha256 NOT LIKE '%[^0-9a-f]%'),
 CONSTRAINT ck_files_name CHECK (DATALENGTH(name)>0 AND DATALENGTH(name)=DATALENGTH(RTRIM(name)))
);
CREATE TABLE dbo.apis (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 name NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL UNIQUE NONCLUSTERED,
 description NVARCHAR(MAX) NULL,
 CHECK (DATALENGTH(name)>0 AND DATALENGTH(name)=DATALENGTH(RTRIM(name)))
);
CREATE TABLE dbo.api_contracts (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 api_id BIGINT NOT NULL REFERENCES dbo.apis(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 openapi_version VARCHAR(32) NOT NULL,
 file_id BIGINT NOT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 imported_at DATETIMEOFFSET(7) NOT NULL,
 UNIQUE NONCLUSTERED(api_id,file_id),
 CHECK (DATALENGTH(openapi_version)>0 AND DATALENGTH(openapi_version)=DATALENGTH(RTRIM(openapi_version)))
);
CREATE TABLE dbo.api_operations (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 contract_id BIGINT NOT NULL REFERENCES dbo.api_contracts(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 http_method VARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
 path_template NVARCHAR(512) COLLATE Latin1_General_100_BIN2 NOT NULL,
 UNIQUE NONCLUSTERED(contract_id,http_method,path_template),
 CHECK (DATALENGTH(http_method)>0 AND DATALENGTH(http_method)=DATALENGTH(RTRIM(http_method))),
 CHECK (DATALENGTH(path_template)>0 AND DATALENGTH(path_template)=DATALENGTH(RTRIM(path_template)))
);
CREATE TABLE dbo.case_families (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 api_id BIGINT NOT NULL REFERENCES dbo.apis(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 code NVARCHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
 UNIQUE NONCLUSTERED(api_id,code),
 CHECK (DATALENGTH(code)>0 AND DATALENGTH(code)=DATALENGTH(RTRIM(code)))
);
CREATE TABLE dbo.responses (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 status_code INT NOT NULL,
 content_type NVARCHAR(MAX) NULL,
 body_file_id BIGINT NOT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 observed_at DATETIMEOFFSET(7) NULL
);
CREATE TABLE dbo.test_cases (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 source_namespace NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL,
 native_case_id NVARCHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
 operation_id BIGINT NOT NULL REFERENCES dbo.api_operations(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 response_id BIGINT NOT NULL REFERENCES dbo.responses(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 family_id BIGINT NOT NULL REFERENCES dbo.case_families(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 origin VARCHAR(32) COLLATE Latin1_General_100_BIN2 NOT NULL,
 parent_case_id BIGINT NULL REFERENCES dbo.test_cases(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 source_file_id BIGINT NOT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 source_pointer NVARCHAR(512) COLLATE Latin1_General_100_BIN2 NOT NULL,
 description NVARCHAR(MAX) NULL,
 UNIQUE NONCLUSTERED(source_namespace,native_case_id),
 CHECK (DATALENGTH(source_namespace)>0 AND DATALENGTH(source_namespace)=DATALENGTH(RTRIM(source_namespace))),
 CHECK (DATALENGTH(native_case_id)>0 AND DATALENGTH(native_case_id)=DATALENGTH(RTRIM(native_case_id))),
 CHECK (DATALENGTH(source_pointer)=DATALENGTH(RTRIM(source_pointer))),
 CHECK (parent_case_id IS NULL OR parent_case_id<>id),
 CHECK ((origin='natural_observation' AND DATALENGTH(origin)=19)
     OR (origin='synthetic_conformant_control' AND DATALENGTH(origin)=28)
     OR (origin='synthetic_inconsistency' AND DATALENGTH(origin)=23))
);
CREATE TABLE dbo.reference_results (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 case_id BIGINT NOT NULL REFERENCES dbo.test_cases(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 version INT NOT NULL CHECK (version>0),
 c1 VARCHAR(15) COLLATE Latin1_General_100_BIN2 NOT NULL,
 c2 VARCHAR(15) COLLATE Latin1_General_100_BIN2 NOT NULL,
 c3 VARCHAR(15) COLLATE Latin1_General_100_BIN2 NOT NULL,
 source_file_id BIGINT NOT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 source_pointer NVARCHAR(512) COLLATE Latin1_General_100_BIN2 NOT NULL,
 notes NVARCHAR(MAX) NULL,
 UNIQUE NONCLUSTERED(case_id,version), UNIQUE NONCLUSTERED(id,case_id),
 CHECK (DATALENGTH(source_pointer)=DATALENGTH(RTRIM(source_pointer))),
 CHECK ((c1 IN ('PASS','FAIL') AND DATALENGTH(c1)=4) OR (c1='NOT_APPLICABLE' AND DATALENGTH(c1)=14)),
 CHECK ((c2 IN ('PASS','FAIL') AND DATALENGTH(c2)=4) OR (c2='NOT_APPLICABLE' AND DATALENGTH(c2)=14)),
 CHECK ((c3 IN ('PASS','FAIL') AND DATALENGTH(c3)=4) OR (c3='NOT_APPLICABLE' AND DATALENGTH(c3)=14)),
 CHECK ((c1='PASS' AND c2='PASS' AND c3 IN ('PASS','FAIL'))
     OR (c1='PASS' AND c2='FAIL' AND c3='NOT_APPLICABLE')
     OR (c1='FAIL' AND c2='NOT_APPLICABLE' AND c3='NOT_APPLICABLE'))
);
CREATE TABLE dbo.datasets (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 name NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL,
 version NVARCHAR(32) COLLATE Latin1_General_100_BIN2 NOT NULL,
 purpose VARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
 UNIQUE NONCLUSTERED(name,version),
 CHECK (DATALENGTH(name)>0 AND DATALENGTH(name)=DATALENGTH(RTRIM(name))),
 CHECK (DATALENGTH(version)>0 AND DATALENGTH(version)=DATALENGTH(RTRIM(version))),
 CHECK ((purpose='development' AND DATALENGTH(purpose)=11) OR (purpose='evaluation' AND DATALENGTH(purpose)=10))
);
CREATE TABLE dbo.dataset_cases (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 dataset_id BIGINT NOT NULL REFERENCES dbo.datasets(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 case_id BIGINT NOT NULL REFERENCES dbo.test_cases(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 reference_id BIGINT NULL,
 case_code NVARCHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
 position INT NOT NULL CHECK (position>0),
 UNIQUE NONCLUSTERED(dataset_id,case_id), UNIQUE NONCLUSTERED(dataset_id,case_code),
 UNIQUE NONCLUSTERED(dataset_id,position), UNIQUE NONCLUSTERED(id,dataset_id),
 FOREIGN KEY(reference_id,case_id) REFERENCES dbo.reference_results(id,case_id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 CHECK (DATALENGTH(case_code)>0 AND DATALENGTH(case_code)=DATALENGTH(RTRIM(case_code)))
);
CREATE TABLE dbo.models (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 name NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL,
 family NVARCHAR(64) NOT NULL,
 parameters_b DECIMAL(7,2) NULL CHECK (parameters_b IS NULL OR parameters_b>0),
 quantization VARCHAR(32) COLLATE Latin1_General_100_BIN2 NOT NULL,
 context_length INT NOT NULL CHECK (context_length>0),
 digest VARCHAR(71) COLLATE Latin1_General_100_BIN2 NOT NULL,
 architecture VARCHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
 metadata_file_id BIGINT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 UNIQUE NONCLUSTERED(name,digest),
 CHECK (DATALENGTH(name)>0 AND DATALENGTH(name)=DATALENGTH(RTRIM(name))),
 CHECK (DATALENGTH(family)>0 AND DATALENGTH(family)=DATALENGTH(RTRIM(family))),
 CHECK (DATALENGTH(quantization)>0 AND DATALENGTH(quantization)=DATALENGTH(RTRIM(quantization))),
 CHECK (DATALENGTH(digest)>0 AND DATALENGTH(digest)=DATALENGTH(RTRIM(digest))),
 CHECK (DATALENGTH(architecture)>0 AND DATALENGTH(architecture)=DATALENGTH(RTRIM(architecture)))
);
CREATE TABLE dbo.prompts (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 name NVARCHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
 version NVARCHAR(32) COLLATE Latin1_General_100_BIN2 NOT NULL,
 strategy VARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
 file_id BIGINT NOT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 parent_prompt_id BIGINT NULL REFERENCES dbo.prompts(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 UNIQUE NONCLUSTERED(name,version),
 CHECK (DATALENGTH(name)>0 AND DATALENGTH(name)=DATALENGTH(RTRIM(name))),
 CHECK (DATALENGTH(version)>0 AND DATALENGTH(version)=DATALENGTH(RTRIM(version))),
 CHECK (parent_prompt_id IS NULL OR parent_prompt_id<>id),
 CHECK ((strategy='direct' AND DATALENGTH(strategy)=6) OR (strategy='checklist' AND DATALENGTH(strategy)=9)
     OR (strategy='explicit' AND DATALENGTH(strategy)=8))
);
CREATE TABLE dbo.run_configs (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 temperature DECIMAL(5,3) NOT NULL CHECK (temperature>=0),
 top_p DECIMAL(5,3) NOT NULL CHECK (top_p BETWEEN 0 AND 1),
 top_k INT NOT NULL CHECK (top_k>=0),
 min_p DECIMAL(5,3) NOT NULL CHECK (min_p BETWEEN 0 AND 1),
 repeat_penalty DECIMAL(5,3) NOT NULL CHECK (repeat_penalty>0),
 repeat_last_n INT NOT NULL CHECK (repeat_last_n>=0),
 draft_num_predict INT NOT NULL CHECK (draft_num_predict>=0),
 num_ctx INT NOT NULL CHECK (num_ctx>0), num_predict INT NOT NULL CHECK (num_predict>0),
 think BIT NULL, stream BIT NOT NULL, timeout_seconds INT NOT NULL CHECK (timeout_seconds>0)
);
CREATE TABLE dbo.experiments (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 name NVARCHAR(128) NOT NULL,
 kind VARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
 dataset_id BIGINT NOT NULL REFERENCES dbo.datasets(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 setup_file_id BIGINT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 schedule_seed BIGINT NULL, started_at DATETIMEOFFSET(7) NULL, finished_at DATETIMEOFFSET(7) NULL,
 notes NVARCHAR(MAX) NULL,
 UNIQUE NONCLUSTERED(id,dataset_id),
 CHECK (DATALENGTH(name)>0 AND DATALENGTH(name)=DATALENGTH(RTRIM(name))),
 CHECK ((kind='comparison' AND DATALENGTH(kind)=10) OR (kind='sensitivity' AND DATALENGTH(kind)=11)
     OR (kind='evaluation' AND DATALENGTH(kind)=10))
);
CREATE TABLE dbo.experiment_runs (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 experiment_id BIGINT NOT NULL, dataset_id BIGINT NOT NULL, dataset_case_id BIGINT NOT NULL,
 model_id BIGINT NOT NULL REFERENCES dbo.models(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 prompt_id BIGINT NOT NULL REFERENCES dbo.prompts(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 run_config_id BIGINT NOT NULL REFERENCES dbo.run_configs(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 repetition SMALLINT NOT NULL CHECK (repetition>0), seed BIGINT NOT NULL,
 run_order INT NOT NULL CHECK (run_order>0),
 request_file_id BIGINT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 result VARCHAR(20) COLLATE Latin1_General_100_BIN2 NULL,
 started_at DATETIMEOFFSET(7) NULL, finished_at DATETIMEOFFSET(7) NULL,
 UNIQUE NONCLUSTERED(experiment_id,dataset_case_id,model_id,prompt_id,repetition),
 UNIQUE NONCLUSTERED(experiment_id,run_order), UNIQUE NONCLUSTERED(id,request_file_id),
 FOREIGN KEY(experiment_id,dataset_id) REFERENCES dbo.experiments(id,dataset_id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 FOREIGN KEY(dataset_case_id,dataset_id) REFERENCES dbo.dataset_cases(id,dataset_id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 CHECK (result IS NULL OR (result='valid' AND DATALENGTH(result)=5)
     OR (result='parser_failure' AND DATALENGTH(result)=14) OR (result='technical_failure' AND DATALENGTH(result)=17)),
 CHECK ((result IS NULL AND finished_at IS NULL) OR
     (result IS NOT NULL AND finished_at IS NOT NULL AND request_file_id IS NOT NULL))
);
CREATE TABLE dbo.run_attempts (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 run_id BIGINT NOT NULL, attempt SMALLINT NOT NULL CHECK (attempt IN (1,2)),
 request_file_id BIGINT NOT NULL,
 response_file_id BIGINT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 diagnostics_file_id BIGINT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 http_status SMALLINT NULL, done_reason NVARCHAR(128) NULL,
 error_kind VARCHAR(64) COLLATE Latin1_General_100_BIN2 NULL, error_message NVARCHAR(MAX) NULL,
 result VARCHAR(20) COLLATE Latin1_General_100_BIN2 NULL,
 duration_ms BIGINT NULL CHECK (duration_ms IS NULL OR duration_ms>=0),
 prompt_tokens INT NULL CHECK (prompt_tokens IS NULL OR prompt_tokens>=0),
 output_tokens INT NULL CHECK (output_tokens IS NULL OR output_tokens>=0),
 prepared_at DATETIMEOFFSET(7) NOT NULL, started_at DATETIMEOFFSET(7) NULL, finished_at DATETIMEOFFSET(7) NULL,
 UNIQUE NONCLUSTERED(run_id,attempt), UNIQUE NONCLUSTERED(id,run_id),
 FOREIGN KEY(run_id,request_file_id) REFERENCES dbo.experiment_runs(id,request_file_id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 CHECK (error_kind IS NULL OR (DATALENGTH(error_kind)>0 AND DATALENGTH(error_kind)=DATALENGTH(RTRIM(error_kind)))),
 CHECK (result IS NULL OR (result='valid' AND DATALENGTH(result)=5)
     OR (result='parser_failure' AND DATALENGTH(result)=14) OR (result='technical_failure' AND DATALENGTH(result)=17)),
 CHECK ((result IS NULL AND finished_at IS NULL) OR
     (result IS NOT NULL AND finished_at IS NOT NULL AND diagnostics_file_id IS NOT NULL))
);
CREATE TABLE dbo.predictions (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 run_id BIGINT NOT NULL UNIQUE NONCLUSTERED, attempt_id BIGINT NOT NULL UNIQUE NONCLUSTERED,
 c1 VARCHAR(15) COLLATE Latin1_General_100_BIN2 NOT NULL, c1_reason NVARCHAR(MAX) NOT NULL,
 c2 VARCHAR(15) COLLATE Latin1_General_100_BIN2 NOT NULL, c2_reason NVARCHAR(MAX) NOT NULL,
 c3 VARCHAR(15) COLLATE Latin1_General_100_BIN2 NOT NULL, c3_reason NVARCHAR(MAX) NOT NULL,
 FOREIGN KEY(attempt_id,run_id) REFERENCES dbo.run_attempts(id,run_id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 CHECK ((c1 IN ('PASS','FAIL') AND DATALENGTH(c1)=4) OR (c1='NOT_APPLICABLE' AND DATALENGTH(c1)=14)),
 CHECK ((c2 IN ('PASS','FAIL') AND DATALENGTH(c2)=4) OR (c2='NOT_APPLICABLE' AND DATALENGTH(c2)=14)),
 CHECK ((c3 IN ('PASS','FAIL') AND DATALENGTH(c3)=4) OR (c3='NOT_APPLICABLE' AND DATALENGTH(c3)=14))
);
CREATE TABLE dbo.evaluation_reports (
 id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
 experiment_id BIGINT NOT NULL REFERENCES dbo.experiments(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 baseline_report_id BIGINT NULL REFERENCES dbo.evaluation_reports(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 created_at DATETIMEOFFSET(7) NOT NULL, code_version VARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL,
 input_file_id BIGINT NOT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 file_id BIGINT NOT NULL REFERENCES dbo.files(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
 CHECK (baseline_report_id IS NULL OR baseline_report_id<>id),
 CHECK (DATALENGTH(code_version)>0 AND DATALENGTH(code_version)=DATALENGTH(RTRIM(code_version)))
);
CREATE INDEX ix_membership_case ON dbo.dataset_cases(case_id);
CREATE INDEX ix_membership_reference ON dbo.dataset_cases(reference_id);
CREATE INDEX ix_case_family ON dbo.test_cases(family_id);
CREATE INDEX ix_case_operation ON dbo.test_cases(operation_id);
CREATE INDEX ix_case_parent ON dbo.test_cases(parent_case_id);
CREATE INDEX ix_run_outcome ON dbo.experiment_runs(experiment_id,result,run_order);
GO
CREATE TRIGGER dbo.files_immutable ON dbo.files INSTEAD OF UPDATE, DELETE AS
BEGIN
 THROW 51000, 'Archived files are immutable', 1;
END;
GO
