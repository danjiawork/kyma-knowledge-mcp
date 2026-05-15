Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask about Kyma Modules.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "What modules does Kyma offer and what they do?"
    

    And response relates to 
    """
    mentions the eventing, serverless and telemetry
    """
