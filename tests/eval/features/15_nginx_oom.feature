Feature: Deployment Troubleshooting

  @cluster
  Scenario: The ngnix Deployment is configured to an insufficient amount of memory and will run out of memory.
    Given the application context:
    """
    {
        "resourceType": "Deployment",
        "groupVersion": "apps/v1",
        "resourceName": "nginx",
        "namespace": "test-deployment-15"
    }
    """
    When I say "Why is the Deployment not available?"
    

    And message content at index 0 contains "Deployment"
    And message content at index 0 contains "nginx"

    And response relates to 
    """
    points out that the Container has an insufficient amount of memory
    """

    And response relates to 
    """
    points out that either the memory limit or the memory request should be increased
    """
