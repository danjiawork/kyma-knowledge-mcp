Feature: Pod Troubleshooting

  @cluster
  Scenario: Check issue with the Kyma Function
    Given the application context:
    """
    {
        "resourceType": "Pod",
        "groupVersion": "v1",
        "resourceName": "pod-check",
        "namespace": "test-pod-3"
    }
    """
    When I say "Why is the Pod in error state?"

    # Verify actual cluster data in message
    And message content at index 0 contains "pod-check"
    And message content at index 0 contains "test-pod-3"
    And message content at index 0 contains "busybox"

    And response relates to 
    """
    points out that the Pod is in an error state
    """

    And response relates to 
    """
    identifies that the busybox image does not contain the kubectl binary, causing a command not found error
    """

    And response relates to 
    """
    recommends replacing the busybox image with a kubectl-enabled image such as bitnami/kubectl
    """

    And response relates to 
    """
    provides a corrected Pod spec or step-by-step remediation to fix the issue
    """
