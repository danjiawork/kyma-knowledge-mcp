Feature: Kyma Function Troubleshooting

  @cluster
  Scenario: The Serverless Function has a syntax error; it calls Dates() instead of Date().
    Given the application context:
    """
    {
        "resourceType": "Function",
        "groupVersion": "serverless.kyma-project.io/v1alpha2",
        "resourceName": "func1",
        "namespace": "test-function-8"
    }
    """
    When I say "Why is my application not reachable?"
    

    And message content at index 0 contains "Function"
    And message content at index 0 contains "func1"

    And response relates to
    """
    The response identifies that there is a problem with the function or provides troubleshooting information about func1
    """
