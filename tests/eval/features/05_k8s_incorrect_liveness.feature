Feature: Deployment Troubleshooting

  @cluster
  Scenario: The Pod is in an error state because the liveness and readiness probes are incorrectly configured.
    Given the application context:
    """
    {
        "resourceType": "Deployment",
        "groupVersion": "apps/v1",
        "resourceName": "nginx-deployment",
        "namespace": "test-deployment-5"
    }
    """
    When I say "Why is the deployment not getting ready?"
    

    # Verify actual cluster data in message
    And message content at index 0 contains "test-deployment-5"

    And response relates to 
    """
    indicates that the Deployment is not becoming ready due to failing health probes
    """

    And response relates to 
    """
    explains that misconfigured liveness and readiness probes prevent the Pod from starting and cause restarts
    """ 
    
    And response relates to 
    """
    provides corrected liveness and readiness probe configuration for the Pod
    """
