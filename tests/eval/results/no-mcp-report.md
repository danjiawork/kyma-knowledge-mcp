# Consistency Check Report — No-MCP Combined Baseline

Run: 2026-04-12_15-54
Runs: 5
Tests: 34

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Passed |
| ❌ | Failed |
| — | Not run |

## Results

| Test | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Passed |
|------|--------|--------|--------|--------|--------|--------|
| 20_question_kyma_regions | ❌ | ❌ | ❌ | ❌ | ❌ | **0/5** |
| 21_question_add_module | ❌ | ❌ | ❌ | ❌ | ❌ | **0/5** |
| 24_question_expose_endpoint | ❌ | ❌ | ❌ | ❌ | ❌ | **0/5** |
| 23_question_use_istio | ✅ | ❌ | ❌ | ❌ | ❌ | 1/5 |
| 02_bitnami_wrong_rbac | ❌ | ❌ | ✅ | ✅ | ❌ | 2/5 |
| 01_bitnami_role_missing | ✅ | ✅ | ✅ | ❌ | ✅ | 4/5 |
| 04_k8s_improper_storage | ✅ | ❌ | ✅ | ✅ | ✅ | 4/5 |
| 13_kyma_subscription_source | ✅ | ✅ | ❌ | ✅ | ✅ | 4/5 |
| 14_kyma_subscription_sink_url | ✅ | ✅ | ✅ | ✅ | ❌ | 4/5 |
| 26_question_cloudfoundry | ✅ | ❌ | ✅ | ✅ | ✅ | 4/5 |
| 03_busybox_no_kubectl_binary | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 05_k8s_incorrect_liveness | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 06_k8s_wrong_svc_labels | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 08_kyma_app_syntax_err | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 10_kyma_function_syntax_error | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 11_kyma_function_no_replicas | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 12_kyma_subscription_sink | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 15_nginx_oom | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 16_nginx_wrong_image | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 19_question_what_is_kyma | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 21_question_add_module | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 22_question_kyma_modules | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 24_question_expose_endpoint | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 25_question_hyperscalers | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 27_question_serverless_function | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 28_question_eventing_subscription | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 29_question_telemetry_tracing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 30_question_btp_service_binding | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 31_question_keda_autoscaling | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 32_question_kyma_cli_install | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 33_question_dev_contribute_api_gateway | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 34_question_dev_serverless_tests | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 35_question_dev_eventing_architecture | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 36_question_dev_lifecycle_manager | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 37_question_dev_create_module | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |
| 38_question_dev_telemetry_pipeline | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 5/5 |

## Summary

- 🔴 **Always failing** (3): 20_question_kyma_regions, 21_question_add_module\*, 24_question_expose_endpoint\*
- 🟡 **Flaky** (7): 23_question_use_istio (1/5), 02_bitnami_wrong_rbac (2/5), 01_bitnami_role_missing (4/5), 04_k8s_improper_storage (4/5), 13_kyma_subscription_source (4/5), 14_kyma_subscription_sink_url (4/5), 26_question_cloudfoundry (4/5)
- 🟢 **Always passing** (24): 03_busybox_no_kubectl_binary, 05_k8s_incorrect_liveness, 06_k8s_wrong_svc_labels, 08_kyma_app_syntax_err, 10_kyma_function_syntax_error, 11_kyma_function_no_replicas, 12_kyma_subscription_sink, 15_nginx_oom, 16_nginx_wrong_image, 19_question_what_is_kyma, 22_question_kyma_modules, 25_question_hyperscalers, 27_question_serverless_function, 28_question_eventing_subscription, 29_question_telemetry_tracing, 30_question_btp_service_binding, 31_question_keda_autoscaling, 32_question_kyma_cli_install, 33_question_dev_contribute_api_gateway, 34_question_dev_serverless_tests, 35_question_dev_eventing_architecture, 36_question_dev_lifecycle_manager, 37_question_dev_create_module, 38_question_dev_telemetry_pipeline
