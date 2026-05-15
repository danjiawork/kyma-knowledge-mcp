Feature: Subscription Troubleshooting

  @cluster
  Scenario: The Subscription is set-up to forward events to redis svc instead of func1 service.
    Given the application context:
    """
    {
        "resourceType": "Subscription",
        "groupVersion": "eventing.kyma-project.io/v1alpha2",
        "resourceName": "sub1",
        "namespace": "test-subscription-14"
    }
    """
    When I say "Why the events are not being received by my function func1?"
    

    And message content at index 0 contains "Subscription"
    And message content at index 0 contains "sub1"

    And response relates to 
    """
    points out that the sink configured in the Subscription is incorrect
    """

    And response relates to 
    """
    provides the reason that the Subscription is set-up to forward events to redis svc instead of func1 service
    """
