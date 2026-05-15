Feature: Deployment Troubleshooting

  @cluster
  Scenario: PVC requests ReadWriteMany but default StorageClass (AWS EBS) supports only ReadWriteOnce, keeping the PVC pending and preventing the deployment from becoming ready.
    Given the application context:
    """
    {
        "resourceType": "Deployment",
        "groupVersion": "apps/v1",
        "resourceName": "nginx-deployment",
        "namespace": "test-deployment-4"
    }
    """
    When I say "Why is the deployment not getting ready?"
    

    # Verify actual cluster data in message
    And message content at index 0 contains "test-deployment-4"
    And message content at index 0 contains "PersistentVolumeClaim"
    And message content at index 0 contains "example-pvc"

    And response relates to 
    """
    indicates that the PersistentVolumeClaim (PVC) is in a pending state
    """

    And response relates to 
    """
    indicates that the issue is related to PersistentVolume (PV) and storage configuration
    """ 
    
    When I say "Can you check the PV?"

    And response relates to 
    """
    states that AWS EBS-backed PersistentVolumes do not support ReadWriteMany (RWX), only ReadWriteOnce (RWO)
    """
