Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask to compare kyma with k8s environments provided by hyperscalers.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "What is the difference between Kyma and other Kubernetes environments provided by hyperscalers?"
    
    And response relates to 
    """
    points out that kyma provides support for SAP services
    """
