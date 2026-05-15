Feature: Kyma Developer Questions

  @question
  Scenario: Ask how to create a new Kyma module.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How do I create a new Kyma module and integrate it with the lifecycle-manager?"

    And response relates to
    """
    mentions a module template, operator scaffolding, or the modulectl tool
    """

    And response relates to
    """
    mentions registering the module with lifecycle-manager or creating a ModuleTemplate CR
    """
