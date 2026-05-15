Feature: Kyma Developer Questions

  @question
  Scenario: Ask how to contribute to the Kyma api-gateway module.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How can I contribute to the Kyma api-gateway module?"

    And response relates to
    """
    mentions contribution guidelines, a CONTRIBUTING file, or a pull request process
    """

    And response relates to
    """
    mentions how to run tests or set up a local development environment for api-gateway
    """
