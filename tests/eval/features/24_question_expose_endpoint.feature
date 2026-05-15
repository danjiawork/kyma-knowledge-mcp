Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask how to expose an endpoint in a Kyma cluster.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How can I expose my endpoint using Kyma?"
    

    And response relates to 
    """
    propose to use the APIRule custom resource and mentions access strategies 
    """
