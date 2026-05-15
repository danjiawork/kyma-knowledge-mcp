Feature: Kyma Questions

  @question
  Scenario: Ask how to create a serverless Function in Kyma.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How do I create a serverless Function in Kyma?"

    And response relates to
    """
    mentions the Function custom resource or the serverless module
    """

    And response relates to
    """
    provides a YAML example or steps to define and deploy the Function
    """
