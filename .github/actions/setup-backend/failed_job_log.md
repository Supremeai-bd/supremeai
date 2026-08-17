----------------------------------------------------------------------------------------------
TOTAL                                              13257   4428   3204    531    64%
Coverage JSON written to file coverage.json
FAIL Required test coverage of 80% not reached. Total coverage: 63.80%
=========================== short test summary info ============================
FAILED tests/core/test_pubsub.py::test_pubsub_subscriber_error_isolation - NameError: name 'MagicMock' is not defined
FAILED tests/core/test_redis_cache.py::TestSecureRedisManagerOperations::test_set_no_client - assert True is False
FAILED tests/core/test_redis_cache.py::TestSecureRedisManagerOperations::test_get_no_client - AssertionError: assert 'value' is None
FAILED tests/core/test_redis_cache.py::TestSecureRedisManagerOperations::test_delete_no_client - assert True is False
FAILED tests/core/test_redis_cache.py::TestSecureRedisManagerOperations::test_set_cache_alias - assert True is False
FAILED tests/core/test_redis_cache.py::TestSecureRedisManagerOperations::test_get_cache_alias - AssertionError: assert 'v' is None
FAILED tests/core/test_redis_cache.py::TestSecureRedisManagerOperations::test_set_json_no_client - assert True is False
FAILED tests/core/test_redis_cache.py::TestSecureRedisManagerOperations::test_get_json_no_client - AssertionError: assert {'a': 1} is None
FAILED tests/core/test_redis_cache.py::TestIdempotencyLock::test_acquire_no_client_fail_closed - Failed: DID NOT RAISE IdempotencyUnavailableError
FAILED tests/core/test_swarm_orchestrator_coverage.py::TestCircuitBreakerCall::test_open_circuit_rejects_calls - Failed: DID NOT RAISE CircuitBreakerOpenError
FAILED tests/core/test_swarm_orchestrator_coverage.py::TestCircuitBreakerCall::test_open_circuit_stays_open_before_timeout - Failed: DID NOT RAISE CircuitBreakerOpenError
FAILED tests/core/test_swarm_orchestrator_coverage.py::TestSwarmOrchestratorExecuteTask::test_circuit_breaker_open_returns_workspace - assert False
 +  where False = any(<generator object TestSwarmOrchestratorExecuteTask.test_circuit_breaker_open_returns_workspace.<locals>.<genexpr> at 0x7fe8d5d22e90>)
FAILED tests/core/test_cache_optimization.py::test_idempotency_lock_fail_closed - Failed: DID NOT RAISE IdempotencyUnavailableError
FAILED tests/core/test_core_missing_coverage.py::TestSettingsValidators::test_get_cached_secret_caches_value - AssertionError: assert '' == 'secret-for-X'

  - secret-for-X
FAILED tests/core/test_core_missing_coverage.py::TestLLMGatewayMissingBranches::test_acompletion_provider_filtering_chain - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/core/test_core_missing_coverage.py::TestLLMGatewayMissingBranches::test_acompletion_messages_list_input - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/core/test_core_missing_coverage.py::TestLLMGatewayMissingBranches::test_acompletion_self_healer_on_failure - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/core/test_core_missing_coverage.py::TestNATSMessagingMissingBranches::test_get_worker_returns_none_on_missing - backend.tests.test_import_fallbacks.KeyValueError: missing
FAILED tests/test_admin_dashboard_full.py::TestGetHealthMap::test_all_offline - AttributeError: Settings(env='test', debug=True, allow_test_auth_bypass=True, allow_test_origin_bypass=True, PROJECT_NAME='SupremeAI 2.0', API_V1_STR='/api/v1', app_name='SupremeAI 2.0', docs_auth_enabled=True, docs_username='admin', docs_password=SecretStr('**********'), port=8080, host='0.0.0.0', cors_origins=['http://localhost:3000', 'http://localhost:8000'], user_cors_origins=[], admin_cors_origins=[], enforce_anti_hacking=False, service_role='user', otp_cooldown_seconds=300, allowed_hosts=[], gemini_rpm_limit=9, gemini_tpm_limit=240000, gemini_rpd_limit=475, groq_rpm_limit=28, groq_tpm_limit=28500, groq_rpd_limit=13680, openrouter_rpm_limit=19, openrouter_rpd_limit=45, cloudflare_rpd_limit=9000, nvidia_rpm_limit=38, nvidia_tpm_limit=38000, huggingface_rpm_limit=18, huggingface_rpd_limit=950, max_prompt_tokens=4000, max_response_tokens=1500, max_cost_per_task=0.01, enable_token_compression=True, security_context_ttl=86400, sec
FAILED tests/test_admin_dashboard_full.py::TestGetHealthMap::test_all_healthy - AttributeError: Settings(env='test', debug=True, allow_test_auth_bypass=True, allow_test_origin_bypass=True, PROJECT_NAME='SupremeAI 2.0', API_V1_STR='/api/v1', app_name='SupremeAI 2.0', docs_auth_enabled=True, docs_username='admin', docs_password=SecretStr('**********'), port=8080, host='0.0.0.0', cors_origins=['http://localhost:3000', 'http://localhost:8000'], user_cors_origins=[], admin_cors_origins=[], enforce_anti_hacking=False, service_role='user', otp_cooldown_seconds=300, allowed_hosts=[], gemini_rpm_limit=9, gemini_tpm_limit=240000, gemini_rpd_limit=475, groq_rpm_limit=28, groq_tpm_limit=28500, groq_rpd_limit=13680, openrouter_rpm_limit=19, openrouter_rpd_limit=45, cloudflare_rpd_limit=9000, nvidia_rpm_limit=38, nvidia_tpm_limit=38000, huggingface_rpm_limit=18, huggingface_rpd_limit=950, max_prompt_tokens=4000, max_response_tokens=1500, max_cost_per_task=0.01, enable_token_compression=True, security_context_ttl=86400, sec
FAILED tests/test_admin_dashboard_full.py::TestGetMetrics::test_metrics_with_keys - AttributeError: property 'openrouter_api_key' of 'Settings' object has no setter
FAILED tests/test_admin_dashboard_full.py::TestGetMetrics::test_metrics_no_keys - AttributeError: property 'openrouter_api_key' of 'Settings' object has no setter
FAILED tests/test_admin_dashboard_full.py::TestGetMetrics::test_metrics_psutil_failure - AttributeError: property 'openrouter_api_key' of 'Settings' object has no setter
FAILED tests/test_admin_dashboard_full.py::TestGetProviders::test_providers_with_keys - AttributeError: property 'openrouter_api_key' of 'Settings' object has no setter
FAILED tests/test_admin_dashboard_full.py::TestGetProviders::test_providers_no_keys - AttributeError: property 'openrouter_api_key' of 'Settings' object has no setter
FAILED tests/test_admin_dashboard_full.py::TestCodebaseExport::test_export_success - AttributeError: <module 'api.routes.admin_dashboard' from '/__w/supremeai/supremeai/backend/api/routes/admin_dashboard.py'> does not have the attribute 'export_codebase_to_markdown'
FAILED tests/test_admin_dashboard_full.py::TestCodebaseExport::test_export_failure - AttributeError: <module 'api.routes.admin_dashboard' from '/__w/supremeai/supremeai/backend/api/routes/admin_dashboard.py'> does not have the attribute 'export_codebase_to_markdown'
FAILED tests/test_admin_dashboard_full.py::TestLogsStream::test_logs_stream_no_log_file - AttributeError: 'coroutine' object has no attribute 'media_type'
FAILED tests/test_admin_god_security.py::TestAdminGodSecurity::test_enforce_allows_admin - TypeError: UserContext.__init__() got an unexpected keyword argument 'roles'
FAILED tests/test_admin_god_security.py::TestAdminGodSecurity::test_enforce_denies_non_admin - TypeError: UserContext.__init__() got an unexpected keyword argument 'roles'
FAILED tests/test_advanced.py::test_chromadb_local_vector_db - assert 0 == 1
 +  where 0 = len([])
FAILED tests/test_advanced.py::test_rag_pipeline - AssertionError: assert '12345' in ''
FAILED tests/test_api.py::test_health_returns_ok - AssertionError: assert 'degraded' == 'ok'

  - ok
  + degraded
FAILED tests/test_api_bootstrap.py::TestRegisterRouter::test_register_router_success - AssertionError: Cannot include an APIRouter instance that already includes this router. Did you mean to include a different router?
FAILED tests/test_api_bootstrap.py::TestRegisterRouter::test_register_router_no_prefix - AssertionError: Cannot include an APIRouter instance that already includes this router. Did you mean to include a different router?
FAILED tests/test_api_bootstrap.py::TestRegisterRouter::test_register_router_import_error_optional - ImportError: Module not found
FAILED tests/test_api_bootstrap.py::TestRegisterRouter::test_register_router_type_error_optional - TypeError: Bad type
FAILED tests/test_api_bootstrap.py::TestRegisterRouter::test_register_router_emits_error_on_failure - ImportError: Not found
FAILED tests/test_api_key_middleware.py::TestAPIKeyAuthMiddleware::test_rejects_invalid_api_key - assert 200 == 401
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_api_key_middleware.py::TestAPIKeyAuthMiddleware::test_rejects_revoked_api_key - assert 200 == 403
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_api_key_middleware.py::TestAPIKeyAuthMiddleware::test_rejects_expired_api_key - assert 200 == 403
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_api_key_middleware.py::TestAPIKeyAuthMiddleware::test_rate_limit_exceeded - assert 200 == 429
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_api_keys_coverage.py::TestCreateAPIKey::test_create_api_key_success - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_keys_coverage.py::TestCreateAPIKey::test_create_api_key_unauthorized - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_keys_coverage.py::TestListAPIKeys::test_list_api_keys_returns_keys - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_keys_coverage.py::TestListAPIKeys::test_list_api_keys_empty - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_keys_coverage.py::TestRevokeAPIKey::test_revoke_api_key_success - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_keys_coverage.py::TestRevokeAPIKey::test_revoke_api_key_not_found - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_keys_coverage.py::TestRotateAPIKey::test_rotate_api_key_success - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_keys_coverage.py::TestRotateAPIKey::test_rotate_api_key_not_found - RuntimeError: There is no current event loop in thread 'MainThread'.
FAILED tests/test_api_zero_coverage.py::TestApiErrors::test_raise_unauthorized - Failed: DID NOT RAISE HTTPException
FAILED tests/test_api_zero_coverage.py::TestApiErrors::test_raise_forbidden - Failed: DID NOT RAISE HTTPException
FAILED tests/test_api_zero_coverage.py::TestApiErrors::test_raise_not_found - Failed: DID NOT RAISE HTTPException
FAILED tests/test_api_zero_coverage.py::TestApiErrors::test_raise_bad_request - Failed: DID NOT RAISE HTTPException
FAILED tests/test_api_zero_coverage.py::TestApiErrors::test_raise_conflict - Failed: DID NOT RAISE HTTPException
FAILED tests/test_api_zero_coverage.py::TestApiDeps::test_get_fitness_engine - ModuleNotFoundError: No module named 'core.error_bus'
FAILED tests/test_api_zero_coverage.py::TestApiDeps::test_get_current_user_token - ModuleNotFoundError: No module named 'core.error_bus'
FAILED tests/test_auth_middleware.py::TestAuthMiddleware::test_middleware_invalid_api_token - AssertionError: assert True is False
 +  where True = <AsyncMock id='139979513846736'>.called
FAILED tests/test_auth_middleware.py::TestAuthMiddleware::test_middleware_no_api_token_env - AssertionError: Expected 'mock' to not have been called. Called 1 times.
Calls: [call({'type': 'http', 'path': '/api/test', 'headers': []}, <MagicMock id='139979523551376'>, <AsyncMock id='139979521366608'>)].
FAILED tests/test_auth_middleware.py::TestVerifyAdminSessionFailClosed::test_missing_jwt_secret - AttributeError: 'Settings' object has no attribute 'jwt_secret'
FAILED tests/test_autonoguard_middleware.py::TestAutonoGuardMiddleware::test_initializes_on_first_request - AssertionError: Expected 'initialize' to have been called once. Called 0 times.
FAILED tests/test_autonoguard_middleware.py::TestAutonoGuardMiddleware::test_blocks_unauthorized_request - assert 200 == 401
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_autonoguard_middleware.py::TestOperationContext::test_context_defaults - pydantic_core._pydantic_core.ValidationError: 1 validation error for OperationContext
headers
  Field required [type=missing, input_value={'admin_id': 'admin', 'ip...test', 'method': 'POST'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
FAILED tests/test_billing_api_coverage.py::TestBillingGetBalance::test_get_balance_returns_wallet_data - ImportError: cannot import name 'get_balance' from 'api.routes.billing_api' (/__w/supremeai/supremeai/backend/api/routes/billing_api.py)
FAILED tests/test_billing_api_coverage.py::TestBillingGetBalance::test_get_balance_no_wallet_returns_zero - ImportError: cannot import name 'get_balance' from 'api.routes.billing_api' (/__w/supremeai/supremeai/backend/api/routes/billing_api.py)
FAILED tests/test_billing_api_coverage.py::TestBillingGetBalance::test_get_balance_unauthorized - ImportError: cannot import name 'get_balance' from 'api.routes.billing_api' (/__w/supremeai/supremeai/backend/api/routes/billing_api.py)
FAILED tests/test_billing_api_coverage.py::TestBillingTopUp::test_top_up_success - ImportError: cannot import name 'TopUpRequest' from 'api.routes.billing_api' (/__w/supremeai/supremeai/backend/api/routes/billing_api.py)
FAILED tests/test_billing_api_coverage.py::TestBillingTopUp::test_top_up_invalid_amount - ImportError: cannot import name 'TopUpRequest' from 'api.routes.billing_api' (/__w/supremeai/supremeai/backend/api/routes/billing_api.py)
FAILED tests/test_billing_api_coverage.py::TestBillingTopUp::test_top_up_unauthorized - ImportError: cannot import name 'TopUpRequest' from 'api.routes.billing_api' (/__w/supremeai/supremeai/backend/api/routes/billing_api.py)
FAILED tests/test_billing_api_coverage.py::TestBillingWebhook::test_webhook_valid_event - TypeError: 'coroutine' object is not subscriptable
FAILED tests/test_billing_api_coverage.py::TestBillingWebhook::test_webhook_invalid_signature - Failed: DID NOT RAISE HTTPException
FAILED tests/test_billing_api_integration.py::test_billing_wallet_unauthorized - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: user_wallets
[SQL: SELECT user_wallets.id, user_wallets.user_id, user_wallets.balance_usd, user_wallets.monthly_allowance_usd, user_wallets.version, user_wallets.created_at, user_wallets.updated_at
FROM user_wallets
WHERE user_wallets.user_id = ?]
[parameters: ('test_admin@supremeai.com',)]
(Background on this error at: https://sqlalche.me/e/20/e3q8)
FAILED tests/test_billing_api_integration.py::test_billing_history_unauthorized - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: transaction_ledger
[SQL: SELECT transaction_ledger.id, transaction_ledger.transaction_id, transaction_ledger.user_id, transaction_ledger.amount_usd, transaction_ledger.transaction_type, transaction_ledger.description, transaction_ledger.timestamp
FROM transaction_ledger
WHERE transaction_ledger.user_id = ? ORDER BY transaction_ledger.timestamp DESC]
[parameters: ('test_admin@supremeai.com',)]
(Background on this error at: https://sqlalche.me/e/20/e3q8)
FAILED tests/test_billing_api_integration.py::test_billing_checkout_unauthorized - assert 200 == 401
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_code_validator.py::TestAICodeValidator::test_code_with_async_function - assert False is True
FAILED tests/test_code_validator.py::TestCodeValidator::test_validate_syntax_valid - TypeError: CodeValidator.validate_syntax() missing 1 required positional argument: 'language'
FAILED tests/test_code_validator.py::TestCodeValidator::test_validate_syntax_invalid - TypeError: CodeValidator.validate_syntax() missing 1 required positional argument: 'language'
FAILED tests/test_code_validator.py::TestCodeValidator::test_validate_url_valid - AssertionError: assert None is True
 +  where None = <built-in method get of dict object at 0x7fe8d4628300>('valid')
 +    where <built-in method get of dict object at 0x7fe8d4628300> = {'is_valid': True, 'scheme': 'https', 'netloc': 'example.com'}.get
FAILED tests/test_code_validator.py::TestCodeValidator::test_validate_url_invalid - AssertionError: assert None is False
 +  where None = <built-in method get of dict object at 0x7fe8d466e380>('valid')
 +    where <built-in method get of dict object at 0x7fe8d466e380> = {'is_valid': False, 'scheme': '', 'netloc': ''}.get
FAILED tests/test_code_validator.py::TestCodeValidator::test_validate_url_empty - AssertionError: assert None is False
 +  where None = <built-in method get of dict object at 0x7fe8d4641080>('valid')
 +    where <built-in method get of dict object at 0x7fe8d4641080> = {'is_valid': False, 'scheme': '', 'netloc': ''}.get
FAILED tests/test_billing_zero_cost.py::TestBillingZeroCost::test_free_tier_exists - AssertionError: assert 'free' in [{'id': 'price_basic_monthly', 'name': 'Basic Plan', 'price': 9.99, 'currency': 'usd', ...}, {'id': 'price_premium_mon...': 'usd', ...}, {'id': 'price_enterprise_monthly', 'name': 'Enterprise Plan', 'price': 199.99, 'currency': 'usd', ...}]
FAILED tests/test_billing_zero_cost.py::TestBillingZeroCost::test_free_tier_cost_zero - TypeError: list indices must be integers or slices, not str
FAILED tests/test_billing_zero_cost.py::TestBillingZeroCost::test_pro_tier_exists - AssertionError: assert 'pro' in [{'id': 'price_basic_monthly', 'name': 'Basic Plan', 'price': 9.99, 'currency': 'usd', ...}, {'id': 'price_premium_mon...': 'usd', ...}, {'id': 'price_enterprise_monthly', 'name': 'Enterprise Plan', 'price': 199.99, 'currency': 'usd', ...}]
FAILED tests/test_billing_zero_cost.py::TestBillingZeroCost::test_record_usage_calls_stripe_when_configured - assert 2.0 == 10.0
FAILED tests/test_config.py::test_env_override - AssertionError: assert 'dummy_admin_hash' == 'mock_hash_va...for_test_pass'

  - mock_hash_value_for_test_pass
  + dummy_admin_hash
FAILED tests/test_byoc_endpoints.py::test_byoc_deployment_fails_without_credentials - KeyError: 'detail'
FAILED tests/test_config_additional.py::test_settings_raises_when_production_secret_missing - Failed: DID NOT RAISE ValueError
FAILED tests/test_config_cache.py::test_config_cache_get_fallback - assert None == 0.95
FAILED tests/test_config_coverage.py::test_parse_cors_origins_production_strips_localhost - AttributeError: 'types.SimpleNamespace' object has no attribute 'field_name'
FAILED tests/test_celery_app.py::test_celery_app_exposed_from_workers - AttributeError: <module 'core.queue.task_queue_enhanced' from '/__w/supremeai/supremeai/backend/core/queue/task_queue_enhanced.py'> does not have the attribute 'celery_app'
FAILED tests/test_config_coverage.py::test_set_jwt_secret_returns_placeholder_in_local - AttributeError: set_jwt_secret
FAILED tests/test_config_coverage.py::test_set_jwt_secret_raises_in_production_when_missing - AttributeError: set_jwt_secret
FAILED tests/test_config_coverage.py::test_set_jwt_secret_keeps_provided_value - AttributeError: set_jwt_secret
FAILED tests/test_celery_app.py::test_celery_app_has_name - AttributeError: <module 'core.queue.task_queue_enhanced' from '/__w/supremeai/supremeai/backend/core/queue/task_queue_enhanced.py'> does not have the attribute 'celery_app'
FAILED tests/test_config_coverage.py::test_validate_config_noop_for_non_production - AttributeError: 'Settings' object has no attribute 'validate_production_completeness'
FAILED tests/test_config_coverage.py::test_validate_config_raises_when_production_keys_missing - AttributeError: 'Settings' object has no attribute 'validate_production_completeness'
FAILED tests/test_config_coverage.py::test_validate_config_passes_when_production_keys_present - AttributeError: 'Settings' object has no attribute 'validate_production_completeness'
FAILED tests/test_config_coverage.py::test_settings_construction_defaults - AssertionError: assert 84 in (86, 128)
 +  where 84 = len('supremeai_secure_jwt_secret_value_at_least_64_bytes_long_test_string_pad_pad_pad_pad')
 +    where 'supremeai_secure_jwt_secret_value_at_least_64_bytes_long_test_string_pad_pad_pad_pad' = Settings(env='local', debug=True, allow_test_auth_bypass=False, allow_test_origin_bypass=False, PROJECT_NAME='SupremeA..._timeout_seconds=30, self_heal_approval_webhook='', self_heal_approval_timeout_hours=24, auto_remediation_dry_run=True).jwt_secret
FAILED tests/test_core_remaining_zero.py::TestDailyLearner::test_goal_decomposition - AttributeError: 'DailyLearner' object has no attribute 'decompose_goal'
FAILED tests/test_core_remaining_zero.py::TestDailyLearner::test_score_priority - AttributeError: 'DailyLearner' object has no attribute 'score_priority'
FAILED tests/test_e2e.py::test_e2e_mobile_and_studio_task_execution - AssertionError: assert ('title' in {'error': {'title': 'Internal Server Error', 'detail': '403: Action blocked by constitutional rules. Admin authorization required.', 'instance': '/task/execute'}} or 'success' in {'error': {'title': 'Internal Server Error', 'detail': '403: Action blocked by constitutional rules. Admin authorization required.', 'instance': '/task/execute'}})
FAILED tests/test_core_remaining_zero.py::TestDailyLearner::test_scan_research - AttributeError: <core.evolution.daily_learner.DailyLearner object at 0x7fe8d5c79f90> does not have the attribute '_scan_arxiv'
FAILED tests/test_email_service.py::TestEmailService::test_get_settings_returns_settings - AttributeError: <module 'core.email_service' from '/__w/supremeai/supremeai/backend/core/email_service.py'> does not have the attribute 'settings'
FAILED tests/test_email_service.py::TestEmailService::test_get_settings_fallback - AttributeError: <module 'core.email_service' from '/__w/supremeai/supremeai/backend/core/email_service.py'> does not have the attribute 'settings'
FAILED tests/test_email_service.py::TestEmailService::test_from_email_default - AssertionError: assert 'onboarding@supremeai.dev' == 'noreply@supremeai.dev'

  - noreply@supremeai.dev
  ?    ^^^^
  + onboarding@supremeai.dev
  ? + + + ^^^^
FAILED tests/test_email_service.py::TestEmailService::test_send_welcome_email - TypeError: EmailService.send_welcome_email() got an unexpected keyword argument 'to_email'
FAILED tests/test_core_remaining_zero.py::TestEvolutionReActAgent::test_execute_task - AttributeError: <core.evolution.evolution_react_agent.EvolutionReActAgent object at 0x7fe8d4486890> does not have the attribute 'execute'
FAILED tests/test_email_service.py::TestEmailService::test_send_password_reset - TypeError: EmailService.send_password_reset() got an unexpected keyword argument 'to_email'
FAILED tests/test_email_service.py::TestEmailService::test_send_billing_notification - TypeError: EmailService.send_billing_notification() got an unexpected keyword argument 'to_email'
FAILED tests/test_email_service.py::TestEmailService::test_send_email_failure_emits_error - TypeError: EmailService._send_email() got an unexpected keyword argument 'body'
FAILED tests/test_email_service.py::TestEmailService::test_send_email_success - TypeError: EmailService._send_email() got an unexpected keyword argument 'body'
FAILED tests/test_email_service.py::TestEmailService::test_send_email_network_error - TypeError: EmailService._send_email() got an unexpected keyword argument 'body'
FAILED tests/test_error_pattern_db.py::TestErrorPatternDB::test_get_prevention_strategy_empty - AssertionError: assert False
 +  where False = isinstance('No historical data - use default validation', dict)
FAILED tests/test_coverage_gaps.py::TestDecisionEngine::test_decide - AssertionError: assert {'action': 'p...'trace': None} == {'action': 'p...'trace': None}

  Omitting 3 identical items, use -vv to show
  Left contains 1 more item:
  {'reason': None}

  Full diff:
    {
        'action': 'proceed',
        'confidence': 1.0,
  +     'reason': None,
        'trace': None,
    }
FAILED tests/test_error_pattern_db.py::TestErrorPatternDB::test_multiple_errors_same_type - AssertionError: assert False
 +  where False = isinstance('No historical data - use default validation', dict)
FAILED tests/test_error_remediation.py::TestErrorRemediation::test_init_no_qdrant - AttributeError: 'ErrorRemediation' object has no attribute 'qdrant'
FAILED tests/test_events_routes_coverage.py::TestDashboardStream::test_dashboard_stream_returns_sse_response - AssertionError: assert False
 +  where False = isinstance(<coroutine object dashboard_stream at 0x7f4f85e33140>, <class 'sse_starlette.sse.EventSourceResponse'>)
FAILED tests/test_events_routes_coverage.py::TestDashboardStream::test_event_generator_yields_heartbeat - NameError: name 'asyncio' is not defined
FAILED tests/test_cross_provider_consistency.py::TestCrossProviderConsistency::test_chat_task_returns_text_from_any_provider - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_events_routes_coverage.py::TestDashboardStream::test_event_generator_yields_data - AttributeError: 'function' object has no attribute 'event_generator'
FAILED tests/test_events_routes_coverage.py::TestDashboardStream::test_event_generator_disconnect - NameError: name 'asyncio' is not defined
FAILED tests/test_cross_provider_consistency.py::TestCrossProviderConsistency::test_bengali_task_prefers_moonshot - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_cross_provider_consistency.py::TestCrossProviderConsistency::test_code_task_routes_to_deepseek - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_cross_provider_consistency.py::TestCrossProviderConsistency::test_streaming_consistency_across_providers - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_evolution_engine.py::test_run_daily_evolution_all_failure_triggers_repeated_failures - ExceptionGroup: Multiple exceptions occurred in asynchronous callbacks (3 sub-exceptions)
FAILED tests/test_cross_provider_consistency.py::TestCrossProviderConsistency::test_error_handling_consistent - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_evolution_routes_coverage.py::TestQuarantineSkill::test_quarantine_skill_success - TypeError: 'coroutine' object is not subscriptable
FAILED tests/test_evolution_routes_coverage.py::TestQuarantineSkill::test_quarantine_skill_not_found - Failed: DID NOT RAISE HTTPException
FAILED tests/test_evolution_routes_coverage.py::TestGetSwarmGraph::test_get_swarm_graph_returns_graph - TypeError: argument of type 'coroutine' is not iterable
FAILED tests/test_evolution_routes_coverage.py::TestForgeDynamicSkill::test_forge_skill_success - TypeError: 'coroutine' object is not subscriptable
FAILED tests/test_evolution_routes_coverage.py::TestForgeDynamicSkill::test_forge_skill_failure - Failed: DID NOT RAISE HTTPException
FAILED tests/test_evolution_routes_coverage.py::TestGetEvolutionLogs::test_get_evolution_logs_returns_logs - TypeError: argument of type 'coroutine' is not iterable
FAILED tests/test_evolution_self_improvement.py::TestEvolutionSelfImprovement::test_register_missing_path_triggers_generation - TypeError: object NoneType can't be used in 'await' expression
FAILED tests/test_evolution_self_improvement.py::TestEvolutionSelfImprovement::test_consecutive_penalty_reset_after_refactor - assert 3 == 0
FAILED tests/test_factual_verifier.py::TestFactualVerifier::test_verify_math_correct - AssertionError: assert None is True
 +  where None = <built-in method get of dict object at 0x7f4f757b9e80>('is_correct')
 +    where <built-in method get of dict object at 0x7f4f757b9e80> = {'is_verified': True, 'expression_sympy': '4', 'claimed_result': '4'}.get
FAILED tests/test_factual_verifier.py::TestFactualVerifier::test_verify_math_incorrect - AssertionError: assert None is False
 +  where None = <built-in method get of dict object at 0x7f4f75e3f6c0>('is_correct')
 +    where <built-in method get of dict object at 0x7f4f75e3f6c0> = {'is_verified': False, 'expression_sympy': '4', 'claimed_result': '5'}.get
FAILED tests/test_factual_verifier.py::TestFactualVerifier::test_verify_math_invalid_expression - assert None is False
 +  where None = <built-in method get of dict object at 0x7f4eaf9ebd80>('is_correct')
 +    where <built-in method get of dict object at 0x7f4eaf9ebd80> = {'is_verified': False, 'error': "Sympy error: Sympify of expression 'could not parse 'invalid @@@ expression'' failed,...ion being raised:\nSyntaxError: invalid syntax (<string>, line 1), Fallback error: invalid syntax (<unknown>, line 0)"}.get
FAILED tests/test_factual_verifier.py::TestFactualVerifier::test_verify_math_no_claimed_result - assert 'is_correct' in {'is_verified': False, 'error': "Sympy error: Sympify of expression 'could not parse ''' failed, because of exception being raised:\nSyntaxError: invalid syntax (<string>, line 0), Fallback error: could not convert string to float: ''"}
FAILED tests/test_factual_verifier.py::TestFactualVerifier::test_verify_with_web_search - AttributeError: <core.factual_verifier.FactualVerifier object at 0x7f4f7571f850> does not have the attribute '_ddgs'
FAILED tests/test_factual_verifier.py::TestFactualVerifier::test_verify_with_web_search_no_results - AttributeError: <core.factual_verifier.FactualVerifier object at 0x7f4f75940150> does not have the attribute '_ddgs'
FAILED tests/test_dock_actions_coverage.py::TestDockActions::test_run_dock_integration_success - TypeError: 'coroutine' object is not subscriptable
FAILED tests/test_dock_actions_coverage.py::TestDockActions::test_run_dock_integration_missing_token - Failed: DID NOT RAISE HTTPException
FAILED tests/test_github_agent.py::test_github_agent_repo_connect - RuntimeError: GitHub token is required for real API operations.
FAILED tests/test_github_agent.py::test_github_agent_analyze - RuntimeError: GitHub token is required for real API operations.
FAILED tests/test_github_agent.py::test_github_agent_pr_creation - AttributeError: 'GitHubAgent' object has no attribute 'create_improvement_pr'
FAILED tests/test_graph_service.py::test_graph_service_real_connection - assert True is False
 +  where True = <tools.graph_service.GraphService object at 0x7f4f756c1d90>.dry_run
FAILED tests/test_health.py::test_health_when_redis_healthy - AttributeError: module 'services' has no attribute 'model_router'
FAILED tests/test_mcp_servers_integration.py::TestCloudDeployMCPExtended::test_deploy_service_missing_render_api_key - ImportError: module tools.mcp.mcp_cloud_deploy not in sys.modules
FAILED tests/test_mcp_servers_integration.py::TestCloudDeployMCPExtended::test_deploy_service_missing_railway_token - ImportError: module tools.mcp.mcp_cloud_deploy not in sys.modules
FAILED tests/test_mcp_servers_integration.py::TestCloudDeployMCPExtended::test_deploy_service_missing_oracle_api_key - ImportError: module tools.mcp.mcp_cloud_deploy not in sys.modules
FAILED tests/test_mcp_servers_integration.py::TestCloudDeployMCPExtended::test_get_logs_missing_api_key - ImportError: module tools.mcp.mcp_cloud_deploy not in sys.modules
FAILED tests/test_mcp_servers_integration.py::TestGithubCICDMCPExtended::test_create_pr_missing_token - ImportError: module tools.mcp.mcp_github_cicd not in sys.modules
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_execute_sql_missing_db_url - AssertionError: assert 'Failed to co...t to database' == 'SUPABASE_DAT...ot configured'

  - SUPABASE_DATABASE_URL not configured
  + Failed to connect to database
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_execute_sql_destructive_with_admin - KeyError: 'success'
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_execute_sql_select_json_format - KeyError: 'row_count'
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_create_table_success - KeyError: 'success'
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_run_migration_missing_db_url - AssertionError: assert 'Failed to co...t to database' == 'SUPABASE_DAT...ot configured'

  - SUPABASE_DATABASE_URL not configured
  + Failed to connect to database
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_run_migration_already_applied - KeyError: 'message'
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_list_tables_missing_db_url - AssertionError: assert 'Failed to co...t to database' == 'SUPABASE_DAT...ot configured'

  - SUPABASE_DATABASE_URL not configured
  + Failed to connect to database
FAILED tests/test_mcp_servers_integration.py::TestSupabaseMCPExtended::test_list_tables_success - KeyError: 'count'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_execute_sql_select_json - KeyError: 'row_count'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_execute_sql_select_markdown - assert '# Query Results' in '{"error": "Failed to connect to database"}'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_execute_sql_insert - KeyError: 'success'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_execute_sql_with_params - KeyError: 'row_count'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_execute_sql_sql_error - assert 'SQL syntax error' in '{"error": "Failed to connect to database"}'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_execute_sql_no_rows - assert 'No rows returned' in '{"error": "Failed to connect to database"}'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_execute_sql_rows_limited - assert 'Showing 100 of 150 rows' in '{"error": "Failed to connect to database"}'
FAILED tests/test_mcp_servers_integration.py::TestInputValidation::test_supabase_create_table_without_if_not_exists - KeyError: 'success'
FAILED tests/test_health.py::test_health_when_redis_down - AttributeError: module 'services' has no attribute 'model_router'
FAILED tests/test_media_r2.py::test_media_route_generate_upload_url - AttributeError: module 'services' has no attribute 'model_router'
FAILED tests/test_microvm_sandbox.py::TestMicroVMHealthCheck::test_health_check - TypeError: argument of type 'coroutine' is not iterable
FAILED tests/test_health.py::test_health_when_redis_unconfigured - AttributeError: module 'services' has no attribute 'model_router'
FAILED tests/test_immune_system.py::test_auto_remediation_success - assert False is True
FAILED tests/test_immune_system.py::test_rollback_monitor_triggers_rollback - assert False is True
FAILED tests/test_minio_client.py::test_get_presigned_url_returns_url - AssertionError: assert False
 +  where False = <built-in method startswith of str object at 0x7f4fb23a5960>('http')
 +    where <built-in method startswith of str object at 0x7f4fb23a5960> = ''.startswith
FAILED tests/test_internal_routes_coverage.py::TestRunDailyEvolution::test_run_daily_evolution_success - AssertionError: assert <coroutine object run_daily_evolution at 0x7fe8d52fa770> == {'status': 'completed', 'logs': []}
FAILED tests/test_internal_routes_coverage.py::TestRunDailyEvolution::test_run_daily_evolution_invalid_days - Failed: DID NOT RAISE HTTPException
FAILED tests/test_knowledge_qa.py::TestKnowledgeQAService::test_init_with_defaults - assert <memory.chromadb_store.ChromaDBStore object at 0x7fe8c71aef90> is None
 +  where <memory.chromadb_store.ChromaDBStore object at 0x7fe8c71aef90> = <services.knowledge_qa.KnowledgeQAService object at 0x7fe8c71af0d0>.vector_store
FAILED tests/test_lifespan.py::TestAppLifespan::test_handles_teardown_errors - AttributeError: module 'services' has no attribute 'model_router'
FAILED tests/test_llm_gateway.py::test_acompletion_cache_hit - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/test_llm_gateway_coverage.py::test_acompletion_accepts_messages_param - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/test_llm_gateway_coverage.py::test_acompletion_medium_difficulty_routing - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/test_llm_gateway_coverage.py::test_acompletion_stream_returns_generator - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/test_llm_gateway_coverage.py::test_acompletion_provider_filtering - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/test_llm_gateway_coverage.py::test_stream_completion_empty_content - AttributeError: property 'cache' of 'LLMGateway' object has no setter
FAILED tests/test_llm_router.py::TestRouteResult::test_route_result_creation - AttributeError: OPENAI
FAILED tests/test_llm_router.py::TestBengaliNormalizer::test_detect_script_mixed - AssertionError: assert 'roman' == 'mixed'

  - mixed
  + roman
FAILED tests/test_multicloud.py::test_cloud_distribution_endpoint - AttributeError: module 'services' has no attribute 'parallel_router'
FAILED tests/test_new_endpoints_sprint5.py::TestOnboardingFlow::test_complete_onboarding_new_user - assert 404 == 200
 +  where 404 = <Response [404 Not Found]>.status_code
FAILED tests/test_new_endpoints_sprint5.py::TestOnboardingFlow::test_complete_onboarding_existing_api_key - assert 404 == 200
 +  where 404 = <Response [404 Not Found]>.status_code
FAILED tests/test_new_endpoints_sprint5.py::TestOnboardingFlow::test_get_onboarding_status - assert 404 == 200
 +  where 404 = <Response [404 Not Found]>.status_code
FAILED tests/test_provider_failover_chain.py::TestProviderFailoverChain::test_primary_provider_success - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_output_validator.py::TestMultiAICodeGenerator::test_generate_with_consensus_full_agreement - TypeError: MultiAICodeGenerator.generate_with_consensus() missing 1 required positional argument: 'code_claude'
FAILED tests/test_output_validator.py::TestMultiAICodeGenerator::test_generate_with_consensus_partial_agreement - TypeError: MultiAICodeGenerator.generate_with_consensus() missing 1 required positional argument: 'code_claude'
FAILED tests/test_output_validator.py::TestMultiAICodeGenerator::test_generate_with_consensus_no_agreement - TypeError: MultiAICodeGenerator.generate_with_consensus() missing 1 required positional argument: 'code_claude'
FAILED tests/test_output_validator.py::TestMultiAICodeGenerator::test_generate_with_consensus_empty_strings - TypeError: MultiAICodeGenerator.generate_with_consensus() missing 1 required positional argument: 'code_claude'
FAILED tests/test_provider_failover_chain.py::TestProviderFailoverChain::test_fallback_on_primary_failure - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_output_validator.py::TestEnhancedConfidenceScorer::test_load_rules_missing_path_returns_empty - AssertionError: assert {'hallucinati... 'scores': {}} == {}

  Left contains 2 more items:
  {'hallucination_patterns': [], 'scores': {}}

  Full diff:
  - {}
  + {
  +     'hallucination_patterns': [],
  +     'scores': {},
  + }
FAILED tests/test_output_validator.py::TestEnhancedConfidenceScorer::test_load_rules_invalid_json - AssertionError: assert {'hallucinati... 'scores': {}} == {}

  Left contains 2 more items:
  {'hallucination_patterns': [], 'scores': {}}

  Full diff:
  - {}
  + {
  +     'hallucination_patterns': [],
  +     'scores': {},
  + }
FAILED tests/test_payments.py::test_create_checkout_session_mock - assert 401 == 200
 +  where 401 = <Response [401 Unauthorized]>.status_code
FAILED tests/test_provider_failover_chain.py::TestProviderFailoverChain::test_all_providers_fail - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_payments.py::test_webhook_ignored_if_missing_config - AttributeError: 'Settings' object has no attribute 'stripe_webhook_secret'
FAILED tests/test_provider_failover_chain.py::TestProviderFailoverChain::test_streaming_fallback - TypeError: Header value must be str or bytes, not <class 'unittest.mock.MagicMock'>
FAILED tests/test_performance_guardian.py::test_anomaly_detector_detects_outlier - assert False is True
FAILED tests/test_rbac.py::test_authorize - AssertionError: assert False is True
 +  where False = authorize('viewer', 'write', context={'bypass_rbac': True})
FAILED tests/test_pgbouncer_pool.py::test_connect - AssertionError: expected call not found.
Expected: create_pool(dsn='test_dsn', min_size=5, max_size=30, max_inactive_connection_lifetime=300, statement_cache_size=0, command_timeout=30)
  Actual: create_pool(dsn='test_dsn', min_size=3, max_size=12, max_inactive_connection_lifetime=300, statement_cache_size=0, command_timeout=30)
FAILED tests/test_resource_guard.py::TestResourceGuard::test_verify_path_accepts_allowed_path - AssertionError: assert (False or PosixPath('/__w/supremeai/supremeai/backend/test.txt') == (PosixPath('/tmp/tmp2y5ggamq') / 'test.txt'))
 +  where False = exists()
 +    where exists = PosixPath('/__w/supremeai/supremeai/backend/test.txt').exists
 +  and   PosixPath('/tmp/tmp2y5ggamq') = resolve()
 +    where resolve = PosixPath('/tmp/tmp2y5ggamq').resolve
 +      where PosixPath('/tmp/tmp2y5ggamq') = Path('/tmp/tmp2y5ggamq')
FAILED tests/test_resource_guard.py::TestResourceGuard::test_read_text_success - FileNotFoundError: [Errno 2] No such file or directory: '/__w/supremeai/supremeai/backend/read_test.txt'
FAILED tests/test_resource_guard.py::TestResourceGuard::test_write_text_success - AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/tmp/tmpzakjn_t1/write_test.txt').exists
FAILED tests/test_resource_guard.py::TestResourceGuard::test_symlink_resolution - AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/__w/supremeai/supremeai/backend/link.txt').exists
FAILED tests/test_resource_guard.py::TestResourceGuard::test_verify_path_supports_sandbox_root - AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/__w/supremeai/supremeai/backend/sandbox.txt').exists
FAILED tests/test_resource_guard.py::TestResourceGuard::test_verify_path_supports_persistent_data_dir - AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/__w/supremeai/supremeai/backend/data.txt').exists
FAILED tests/test_sprint_c_tools.py::TestBrowserAgent::test_fetch_page_success - RuntimeError: Playwright is not installed.
FAILED tests/test_sprint_c_tools.py::TestDiagramToArchitecture::test_mock_output - AttributeError: 'DiagramToArchitecture' object has no attribute '_mock_output'
FAILED tests/test_stream.py::test_stream_endpoint_requires_auth - assert 200 == 401
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_supabase_schema_bootstrap.py::test_insert_task_history_retries_after_schema_cache_error - AttributeError: 'SupabaseDB' object has no attribute 'client'
FAILED tests/test_telemetry.py::test_setup_tracing_noop - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'otel_trace'
FAILED tests/test_telemetry.py::test_setup_tracing_with_endpoint - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'BatchSpanProcessor'
FAILED tests/test_telemetry.py::test_setup_tracing_without_endpoint_no_exporter - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'TracerProvider'
FAILED tests/test_telemetry.py::test_trace_span_no_tracer - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'get_tracer'
FAILED tests/test_telemetry.py::test_trace_span_with_tracer - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'get_tracer'
FAILED tests/test_telemetry.py::test_trace_span_sets_ok_status_on_success - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'get_tracer'
FAILED tests/test_telemetry.py::test_trace_span_records_exception_on_error - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'get_tracer'
FAILED tests/test_telemetry.py::test_trace_span_unknown_kind_defaults_to_internal - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'get_tracer'
FAILED tests/test_telemetry.py::test_trace_span_sets_attributes_multiple - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'get_tracer'
FAILED tests/test_telemetry.py::test_tracer_shared_globally_after_setup - AttributeError: <module 'core.telemetry' from '/__w/supremeai/supremeai/backend/core/telemetry/__init__.py'> does not have the attribute 'BatchSpanProcessor'
FAILED tests/test_token_deductor.py::test_acquire_distributed_lock_fail_closed_in_production - AttributeError: property 'configured' of 'UpstashRedisQueue' object has no setter
FAILED tests/test_token_deductor.py::test_deduct_tokens_success_happy_path - assert False is True
FAILED tests/test_tools_cli_zero.py::TestCLI::test_parse_args_defaults - ImportError: cannot import name 'parse_args' from 'tools.cli' (/__w/supremeai/supremeai/backend/tools/cli.py)
FAILED tests/test_tools_cli_zero.py::TestBandwidthOptimizerAdditional::test_optimize_request - AttributeError: 'BandwidthOptimizer' object has no attribute 'optimize_request'
FAILED tests/test_tools_cli_zero.py::TestBandwidthOptimizerAdditional::test_cache_response - TypeError: BandwidthOptimizer.__init__() got an unexpected keyword argument 'cache_size'
FAILED tests/test_tools_cli_zero.py::TestConversationManagerAdditional::test_update_message - AttributeError: 'ConversationManager' object has no attribute 'create_conversation'
FAILED tests/test_tools_cli_zero.py::TestConversationManagerAdditional::test_delete_message - AttributeError: 'ConversationManager' object has no attribute 'create_conversation'
FAILED tests/test_universal_rules_extended.py::TestApplyExtendedRules::test_apply_task_classification - AssertionError: assert 'CONVERSATIONAL' == 'RESEARCH'

  - RESEARCH
  + CONVERSATIONAL
FAILED tests/tools/test_browser_agent.py::test_navigate_and_interact_fallback_scraper - RuntimeError: Playwright is not installed.
FAILED tests/tools/test_browser_agent.py::test_navigate_and_interact_network_error - RuntimeError: Playwright is not installed.
FAILED tests/tools/test_browser_agent.py::test_execute_recipe_success - AssertionError: assert 'failed' == 'success'

  - success
  + failed
FAILED tests/tools/test_browser_agent.py::test_execute_recipe_failure - AssertionError: assert 'Page load timeout' in 'Playwright is not installed'
FAILED tests/tools/test_code_smell_detector.py::TestDetectDuplicateFunctions::test_duplicate_detection_crashes_due_to_body_bug - Failed: DID NOT RAISE TypeError
FAILED tests/tools/test_code_smell_detector.py::TestDetectDuplicateFunctions::test_unique_bodies_also_crashes - Failed: DID NOT RAISE TypeError
FAILED tests/tools/test_code_smell_detector.py::TestDetectDuplicateFunctions::test_single_function_crashes - Failed: DID NOT RAISE TypeError
FAILED tests/test_prod_docs_security.py::test_docs_disabled_in_production - AssertionError: 2026-07-25 01:31:13.297 | INFO     | core.security.secret_vault:__init__:68 - Infisical missing or no credentials found. Bypassing Cloud Vault.
  2026-07-25 01:31:13.342 | WARNING  | core.llm.llm_gateway:_load_routing_policy:105 - [LLMGateway] Routing policy not found at '/__w/supremeai/supremeai/backend/core/config/routing_policy.json'. Using default fallback config.
  2026-07-25 01:31:17.142 | INFO     | core.skill_manager:__init__:45 - SkillManager initialized for dynamic skill dispatch.
  2026-07-25 01:31:17.143 | INFO     | core.skill_manager:__init__:45 - SkillManager initialized for dynamic skill dispatch.
  2026-07-25 01:31:17.159 | INFO     | utils.firestore_helpers:get_firestore_db:59 - Firestore client initialized for project: supremeai-a
  2026-07-25 01:31:17.164 | INFO     | brain.model_router:__init__:54 - Initializing refactored ModelRouter (LiteLLM Wrapper)
  2026-07-25 01:31:17.531 | INFO     | core.messaging.events:get_firebase_auth:52 - Firebase Admin initialized via GOOGLE_APPLICATION_CREDENTIALS
  2026-07-25 01:31:17.531 | INFO     | core.messaging.events:get_firebase_auth:63 - Firebase Admin SDK ready ✅
  2026-07-25 01:31:18.155 | INFO     | brain.model_router:__init__:54 - Initializing refactored ModelRouter (LiteLLM Wrapper)
  2026-07-25 01:31:18.155 | INFO     | brain.model_router:__init__:54 - Initializing refactored ModelRouter (LiteLLM Wrapper)
  2026-07-25 01:31:18.155 | INFO     | brain.model_router:__init__:54 - Initializing refactored ModelRouter (LiteLLM Wrapper)
  2026-07-25 01:31:18.155 | INFO     | memory.long_term_memory:__init__:26 - Initialized MemoryManager.
  2026-07-25 01:31:18.156 | INFO     | core.skill_manager:__init__:45 - SkillManager initialized for dynamic skill dispatch.
  2026-07-25 01:31:18.157 | INFO     | core.skill_manager:__init__:45 - SkillManager initialized for dynamic skill dispatch.
  2026-07-25 01:31:18.165 | WARNING  | api.routes:<module>:48 - Router import failed for auth_router: Traceback (most recent call last):
    File "/__w/supremeai/supremeai/backend/api/routes/__init__.py", line 40, in <module>
      from .auth import router as auth_router
    File "/__w/supremeai/supremeai/backend/api/routes/auth.py", line 26, in <module>
      SECRET_KEY = settings.jwt_secret
                   ^^^^^^^^^^^^^^^^^^^
    File "/__w/supremeai/supremeai/backend/core/config.py", line 477, in jwt_secret
      raise ValueError("JWT secret must be >= 64 bytes entropy in all environments.")
  ValueError: JWT secret must be >= 64 bytes entropy in all environments.

  2026-07-25 01:31:18.175 | INFO     | core.observability.audit_logger:__init__:46 - AuditLogger: using pooled Postgres backend (write-behind batched).
  2026-07-25 01:31:18.344 | INFO     | tools.ai_agents.browser_agent:__init__:35 - Initialized BrowserAgent
  2026-07-25 01:31:18.362 | WARNING  | core.utils.lazy_loader:lazy_import:29 - ⚠️ [LazyLoader] Optional package 'chromadb' is not available in light mode. Please install it via 'poetry install --with ml'.
  2026-07-25 01:31:18.364 | WARNING  | core.llm.llm_gateway:_load_routing_policy:105 - [LLMGateway] Routing policy not found at '/__w/supremeai/supremeai/backend/core/config/routing_policy.json'. Using default fallback config.
  2026-07-25 01:31:18.365 | INFO     | core.observability.audit_logger:__init__:46 - AuditLogger: using pooled Postgres backend (write-behind batched).
  2026-07-25 01:31:18.371 | INFO     | tools.social.marketplace_agent:__init__:6 - MarketplaceAgent initialized.
  2026-07-25 01:31:18.465 | WARNING  | storage.r2_storage_client:__init__:21 - Cloudflare R2 credentials missing. R2StorageClient will run in dry-run/mock mode.
  2026-07-25 01:31:18.553 | INFO     | brain.model_router:__init__:54 - Initializing refactored ModelRouter (LiteLLM Wrapper)
  2026-07-25 01:31:18.572 | INFO     | tools.social.email_agent:__init__:32 - EmailAgent initialized with auth_method=oauth
  2026-07-25 01:31:18.578 | WARNING  | core.security.secure_credential_store:__init__:45 - ⚠️ Non-Base64 encryption key detected in current context. Natively deriving valid Fernet key layout.
  2026-07-25 01:31:18.583 | WARNING  | tools.repo_discovery_agent:__init__:15 - RepoDiscoveryAgent initialized without a token; real API operations disabled.
  2026-07-25 01:31:19.998 | WARNING  | api.routes:<module>:434 - Router import failed for graph_router: Traceback (most recent call last):
    File "/__w/supremeai/supremeai/backend/api/routes/__init__.py", line 426, in <module>
      from .graph import router as graph_router
    File "/__w/supremeai/supremeai/backend/api/routes/graph.py", line 6, in <module>
      from api.routes.auth import optional_current_user
    File "/__w/supremeai/supremeai/backend/api/routes/auth.py", line 26, in <module>
      SECRET_KEY = settings.jwt_secret
                   ^^^^^^^^^^^^^^^^^^^
    File "/__w/supremeai/supremeai/backend/core/config.py", line 477, in jwt_secret
      raise ValueError("JWT secret must be >= 64 bytes entropy in all environments.")
  ValueError: JWT secret must be >= 64 bytes entropy in all environments.

  /usr/local/lib/python3.11/site-packages/pydantic/_internal/_generate_schema.py:663: ArbitraryTypeWarning: <built-in function any> is not a Python type (it may be an instance of an object), Pydantic will allow any object with no validation since we cannot even enforce that the input is an instance of the given type. To get rid of this error wrap the type with `pydantic.SkipValidation`.
    warnings.warn(
  2026-07-25 01:31:21.953 | INFO     | core.app_builder:<module>:75 - ✅ Sentry SDK initialized successfully.
  2026-07-25 01:31:21.959 | DEBUG    | logging:callHandlers:1706 - Router registered: 'api.routes.memory' -> prefix=''
  2026-07-25 01:31:21.959 | DEBUG    | logging:callHandlers:1706 - Router registered: 'api.routes.task' -> prefix=''
  2026-07-25 01:31:21.960 | DEBUG    | logging:callHandlers:1706 - Router registered: 'api.routes.markdown' -> prefix='/api/v1'
  2026-07-25 01:31:21.960 | DEBUG    | logging:callHandlers:1706 - Router registered: 'api.routes.simulator' -> prefix=''
  2026-07-25 01:31:21.960 | DEBUG    | logging:callHandlers:1706 - Router registered: 'api.routes.site_actions' -> prefix=''
Error: Process completed with exit code 1.
