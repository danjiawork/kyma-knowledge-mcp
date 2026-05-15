Feature: Kyma Questions

  @question
  Scenario: Ask how to enable distributed tracing in Kyma.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How do I enable distributed tracing for my application in Kyma?"

    And response relates to
    """
    mentions the Telemetry module or TracePipeline custom resource
    """

    And response relates to
    """
    mentions an OTLP endpoint or a tracing backend such as Jaeger or Zipkin
    """
