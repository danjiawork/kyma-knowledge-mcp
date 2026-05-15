Feature: Subscription Troubleshooting

  @cluster
  Scenario: The Subscription is configured with an invalid sink URL
    Given the application context:
    """
    {
        "resourceType": "Subscription",
        "groupVersion": "eventing.kyma-project.io/v1alpha2",
        "resourceName": "my-sub",
        "namespace": "test-subscription-12"
    }
    """
    When I say "How to fix my subscription?"
    

    And response relates to 
    """
    points out that the Subscription is configured with an invalid sink URL because it does not end with the required suffix svc.cluster.local
    """
