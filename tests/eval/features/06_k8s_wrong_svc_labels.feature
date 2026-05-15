Feature: Service Troubleshooting

  @cluster
  Scenario: Service selector/Pod label mismatch leaves no endpoints; response grounded in real resource analysis (no generic fallback).
    Given the application context:
    """
    {
        "resourceType": "Service",
        "groupVersion": "v1",
        "resourceName": "test-service-6",
        "namespace": "test-service-6"
    }
    """
    When I say "Why is my application not reachable?"
    

    # Verify actual cluster data in message
    And message content at index 0 contains "test-service-6"

    And response relates to 
    """
    identifies that the Service selector labels do not match the Pod/Deployment labels, resulting in no endpoints
    """
    
    And response relates to 
    """
    explains how to align Service selector with Pod/Deployment labels (or update Deployment labels) to restore routing
    """
    
    And response relates to 
    """
    provides a step-by-step fix with kubectl examples to patch labels or selectors
    """
