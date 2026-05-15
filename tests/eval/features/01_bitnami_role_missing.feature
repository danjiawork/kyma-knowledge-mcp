Feature: Pod Troubleshooting

  @cluster
  Scenario: Check issue with the Kyma Function
    Given the application context:
    """
    {
        "resourceType": "Pod",
        "groupVersion": "v1",
        "resourceName": "pod-check",
        "namespace": "test-pod-1"
    }
    """
    When I say "Why is the Pod in error state?"

    # Verify actual cluster data in message
    And message content at index 0 contains "pod-check"
    And message content at index 0 contains "test-pod-1"
    And message content at index 0 contains "ServiceAccount"
    And message content at index 0 contains "test-pod-1-sa"
    
    And response relates to 
    """
    points out that the Pod is in an error state
    """
    
    And response relates to 
    """
    points out that the Pod has no permissions
    """
    
    And response relates to 
    """
    provides a step-by-step guide on how to fix the issue
    """
