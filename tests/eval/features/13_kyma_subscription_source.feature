Feature: Subscription Troubleshooting

  @cluster
  Scenario: The Subscription is configured with an invalid source configuration.
    Given the application context:
    """
    {
        "resourceType": "Subscription",
        "groupVersion": "eventing.kyma-project.io/v1alpha2",
        "resourceName": "my-sub",
        "namespace": "test-subscription-13"
    }
    """
    When I say "How exactly to fix my subscription?"
    

    And response relates to 
    """
    points out that the Subscription is configured with an invalid source configuration
    """

    And response relates to 
    """
    provides an example of how the source should be configured
    """
