# PROGRESS: External Dependencies Needing Local Stubs

These packages are imported by code in this repo but are not available yet.
Each section lists the exact symbols used and which files use them.
They must be stubbed locally before the project can run end-to-end.

---

## 1. `spark_core`

### `spark_core.components.core_types.OutputTable`
Used in:
- `leverance/components/business/jn/jn_notat_business_component.py`
- `leverance/components/business/jn/jn_samtale_business_component.py`
- `leverance/components/business/jn/jn_prompts_business_component.py`
- `leverance/components/business/jn/jn_notat_feedback_business_component.py`
- `leverance/components/business/jn/jn_config_business_component.py`
- `leverance/components/business/jn/jn_model_business_component.py`

`OutputTable` is a data class / named tuple describing a database output table destination with fields: `db`, `schema`, `table`, `do_not_delete`.

### `spark_core.components.base_component.NonSessionComponent`
Used in all business components above.
Base class providing `__init__(self, app=None)` and likely `execute_sql(sql, params=None)` and `session` (SQLAlchemy session).

### `spark_core.database.db_utils.use_access_token_for_azure_sql`
Used in:
- `leverance/common/azure_helper.py`

Configures a SQLAlchemy engine to use Azure AD access token auth for Azure SQL.
Signature: `use_access_token_for_azure_sql(engine, tenant_id, client_id, client_secret)`

### `spark_core.testing.base_test_executor.BaseTestExecutor`
Used in:
- `leverance/components/business/jn/_test_jn_notat_business_component.py`

Base class for integration tests providing database setup/teardown.

---

## 2. `ork`

### `ork.project_handler.get_config_for_project`
Used in:
- `leverance/common/azure_helper.py`

Returns a project-specific config object by name and service.
Signature: `get_config_for_project(project_name: str, service: str) -> Config`

---

## 3. `dfd_azure_ml`

### `dfd_azure_ml.core.clients.azure_blob_client.AzureBlobClient`
Used in:
- `leverance/common/azure_helper.py`

Azure Blob Storage client wrapper.
Constructor: `AzureBlobClient(account_name, container_name, auth)`

### `dfd_azure_ml.core.clients.ml_auth_client.Authentication`
Used in:
- `leverance/common/azure_helper.py`

Authentication object for dfd_azure_ml clients.
Constructor: `Authentication(azure_identity_tenant_id, azure_identity_client_id, azure_identity_client_secret)`

---

## 4. `leverance` framework (external)

The external `leverance` framework provides the following symbols that are NOT in this repo.
Once available, this package should be installed alongside `leverance-jn` using the
Python namespace package mechanism (no `__init__.py` at the `leverance/` root).

### `leverance.core.runners.service_runner.ServiceRunner`
Used in all business components.
Base class providing: `__init__(service_name, request_uid, config_name)`, `execute_sql`, `session`, `app`.

### `leverance.core.logger_adapter.ServiceLoggerAdapter`
Used in all business components.
Provides: `service_info(component, msg, **kwargs)`, `service_warning(component, msg)`, `service_exception(component, msg)`.

### `leverance.core.common.timeout_handler.run_with_timeout`
Used in:
- `leverance/components/business/jn/jn_notat_business_component.py`

Decorator: `@run_with_timeout(timeout, result_by_timeout, log_besked, log_type)`

### `leverance.components.interaction.webservice.blueprints.jn.bp`
Used in:
- `leverance/interaction/jn_interaction_component.py`

Flask `Blueprint` object for the JN webservice API routes.

### `leverance.components.interaction.website.blueprints.jn.interaction_bp`
Used in:
- `leverance/interaction/jn_website_interaction_component.py`

Flask `Blueprint` object for the JN website interaction routes.

### `leverance.components.interaction.website.site_authentication.auth_required`
### `leverance.components.interaction.website.site_authentication.auth_required_site`
Used in:
- `leverance/interaction/jn_website_interaction_component.py`

Flask decorators for enforcing authentication on website routes.

---

## 5. Additional evaluation dependencies (lower priority)

### `spacy`
Used in: `leverance/evaluation/evaluate_notat.py`
Standard NLP library. Install via: `pip install spacy`

### `jiwer`
Used in: `leverance/evaluation/evaluate_notat.py`
Word Error Rate calculation. Install via: `pip install jiwer`

### `locust`
Used in: `tests/end_to_end_and_load_test/load_test/locustfile.py`
Load testing framework. Install via: `pip install locust`
