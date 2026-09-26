-- Migration owner remains separate from the application role; provision logins externally.
CREATE ROLE rac_application AUTHORIZATION dbo;
GRANT SELECT ON SCHEMA::dbo TO rac_application;
GRANT INSERT ON dbo.files TO rac_application;
GRANT INSERT ON dbo.apis TO rac_application;
GRANT INSERT ON dbo.api_contracts TO rac_application;
GRANT INSERT ON dbo.api_operations TO rac_application;
GRANT INSERT ON dbo.case_families TO rac_application;
GRANT INSERT ON dbo.responses TO rac_application;
GRANT INSERT ON dbo.test_cases TO rac_application;
GRANT INSERT ON dbo.reference_results TO rac_application;
GRANT INSERT ON dbo.datasets TO rac_application;
GRANT INSERT ON dbo.dataset_cases TO rac_application;
GRANT INSERT ON dbo.models TO rac_application;
GRANT INSERT ON dbo.prompts TO rac_application;
GRANT INSERT ON dbo.run_configs TO rac_application;
GRANT INSERT ON dbo.experiments TO rac_application;
GRANT INSERT ON dbo.experiment_runs TO rac_application;
GRANT INSERT ON dbo.run_attempts TO rac_application;
GRANT INSERT ON dbo.predictions TO rac_application;
GRANT INSERT ON dbo.evaluation_reports TO rac_application;
DENY DELETE ON SCHEMA::dbo TO rac_application;
DENY ALTER ON SCHEMA::dbo TO rac_application;
DENY INSERT, UPDATE, DELETE ON dbo.schema_migrations TO rac_application;
GRANT UPDATE (reference_id) ON dbo.dataset_cases TO rac_application;
GRANT UPDATE (started_at,finished_at) ON dbo.experiments TO rac_application;
GRANT UPDATE (request_file_id,result,started_at,finished_at) ON dbo.experiment_runs TO rac_application;
GRANT UPDATE (response_file_id,diagnostics_file_id,http_status,done_reason,error_kind,error_message,
 result,duration_ms,prompt_tokens,output_tokens,started_at,finished_at) ON dbo.run_attempts TO rac_application;
-- Lifecycle guards on these operational columns belong to the transactional repository.
