Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask how to add a module.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How to add a module?"
    

    And response has 1 message

    And response relates to 
    """
    provides instructions on how to add modules via the Kyma dashboard
    """
