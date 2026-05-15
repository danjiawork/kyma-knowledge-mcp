Feature: Kyma Developer Questions

  @question
  Scenario: Ask about the internal architecture of the eventing-manager.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "What is the internal architecture of the Kyma eventing-manager?"

    And response relates to
    """
    mentions controllers, reconcilers, or the operator pattern used in eventing-manager
    """

    And response relates to
    """
    mentions NATS or the event backend that eventing-manager manages
    """
