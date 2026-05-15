Feature: Function Troubleshooting

  @cluster
  Scenario: The Pod of the Serverless Function is not ready because the function is configured with 0 replicas.
    Given the application context:
    """
    {
        "resourceType": "Function",
        "groupVersion": "serverless.kyma-project.io/v1alpha2",
        "resourceName": "func1",
        "namespace": "test-function-11"
    }
    """
    When I say "Why is the pod of the serverless Function not ready?"
    

    And message content at index 0 contains "Function"
    And message content at index 0 contains "func1"

    And response relates to 
    """
    points out that the Pod is not ready
    """
    
    And response relates to 
    """
    points out that the Function is configured with 0 replicas
    """
