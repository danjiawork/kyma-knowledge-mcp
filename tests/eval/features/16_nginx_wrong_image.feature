Feature: Deployment Troubleshooting

  @cluster
  Scenario: The name of the image in the Deployment is misspelled to 'ngix' instead of 'nginx'.
    Given the application context:
    """
    {
        "resourceType": "Deployment",
        "groupVersion": "apps/v1",
        "resourceName": "nginx",
        "namespace": "test-deployment-16"
    }
    """
    When I say "What is causing the Deployment to not have minimum availability?"
    

    And message content at index 0 contains "Deployment"
    And message content at index 0 contains "nginx"

    And response relates to 
    """
    points out that the image 'ngix' does not exist
    """

    And response relates to 
    """
    points out that the image name have a typo
    """

    And response relates to 
    """
    points out that the image name should be 'nginx'
    """
