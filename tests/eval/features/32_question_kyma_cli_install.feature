Feature: Kyma Questions

  @question
  Scenario: Ask how to provision a Kyma cluster using the Kyma CLI.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How do I provision or install Kyma on a Kubernetes cluster using the CLI?"

    And response relates to
    """
    mentions the kyma CLI or the 'kyma deploy' command
    """

    And response relates to
    """
    mentions lifecycle-manager or steps to apply Kyma to a cluster
    """
