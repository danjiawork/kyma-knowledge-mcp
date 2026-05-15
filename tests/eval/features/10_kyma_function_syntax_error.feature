Feature: Kyma Function Troubleshooting

  @cluster
  Scenario: The Function has a syntax error in its JavaScript source code.
    Given the application context:
    """
    {
        "resourceType": "Function",
        "groupVersion": "serverless.kyma-project.io/v1alpha2",
        "resourceName": "my-function-0",
        "namespace": "test-function-10"
    }
    """
    When I say "Why is my Kyma Function not working?"

    And message content at index 0 contains "Function"
    And message content at index 0 contains "my-function-0"

    And response relates to 
    """
    points out that the Function has a syntax error in its source code and provides a description of the error.
    """
    
    And response relates to 
    """
    provides an example of how to fix the Function JavaScript source code.
    """
