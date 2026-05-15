Feature: Kyma Developer Questions

  @question
  Scenario: Ask how the lifecycle-manager manages module installation internally.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How does the Kyma lifecycle-manager manage module installation internally?"

    And response relates to
    """
    mentions the Kyma custom resource or ModuleTemplate
    """

    And response relates to
    """
    mentions the reconciliation loop or how lifecycle-manager installs and updates modules
    """
