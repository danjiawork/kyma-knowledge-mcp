Feature: Kyma Questions

  @question
  Scenario: Ask how to bind and use a BTP service in a Kyma workload.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "How do I bind a SAP BTP service to my application running in Kyma?"

    And response relates to
    """
    mentions ServiceInstance or ServiceBinding resources
    """

    And response relates to
    """
    mentions the BTP Operator or btp-manager module
    """
