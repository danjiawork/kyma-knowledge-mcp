Feature: Kyma Questions

  @question
  Scenario: Ask how to configure event-driven autoscaling in Kyma using KEDA.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How can I autoscale my workload based on custom metrics or events in Kyma?"

    And response relates to
    """
    mentions KEDA or the ScaledObject custom resource
    """

    And response relates to
    """
    mentions enabling the KEDA module or providing a ScaledObject example
    """
