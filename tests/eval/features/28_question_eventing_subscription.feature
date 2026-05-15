Feature: Kyma Questions

  @question
  Scenario: Ask how to subscribe to events in Kyma.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How can I subscribe to events in Kyma?"

    And response relates to
    """
    mentions the Subscription custom resource
    """

    And response relates to
    """
    mentions the event source or event type that the Subscription listens to
    """
