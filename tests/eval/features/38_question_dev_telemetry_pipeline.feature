Feature: Kyma Developer Questions

  @question
  Scenario: Ask how the telemetry-manager pipeline works internally.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How does the telemetry-manager pipeline work internally in Kyma?"

    And response relates to
    """
    mentions LogPipeline, TracePipeline, or MetricPipeline custom resources
    """

    And response relates to
    """
    mentions the OTel Collector or how telemetry-manager processes and forwards signals
    """
