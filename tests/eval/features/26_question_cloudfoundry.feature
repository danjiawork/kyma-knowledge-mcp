Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask to compare kyma and cloud foundry.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "What is the difference between Kyma and Cloud Foundry?"
  
    And response relates to 
    """
    points out that kyma runs on k8s (kubernetes) and that Cloud Foundry is PaaS (Platform as a service)
    """
