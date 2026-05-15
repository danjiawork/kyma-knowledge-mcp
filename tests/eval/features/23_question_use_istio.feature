Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask how to use Istio.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How can I use Istio in Kyma?"
    

    And response relates to
    """
    correctly describes that Istio is available in Kyma as a default or preinstalled module (not something the user needs to separately install from scratch)
    """
