Feature: Kyma Developer Questions

  @question
  Scenario: Ask how to run serverless module tests locally.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How do I run the Kyma serverless module tests locally during development?"

    And response relates to
    """
    mentions make targets, go test, or a specific test command for the serverless module
    """

    And response relates to
    """
    mentions prerequisites such as a local cluster, kind, or a Kubernetes environment
    """
