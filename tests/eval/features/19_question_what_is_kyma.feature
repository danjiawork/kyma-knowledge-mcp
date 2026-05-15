Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask what kyma is.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "What is Kyma?"
    

    And response relates to 
    """
    mentions 'Kubernetes' or 'k8s'
    """
