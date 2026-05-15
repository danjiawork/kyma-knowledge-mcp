Feature: Kyma Questions

  @question
  Scenario: Unrelated to existing cluster resources, ask at which regions kyma is available.
    Given the application context:
    """
    {
        "resourceType": "Cluster",
        "groupVersion": "",
        "resourceName": "",
        "namespace": ""
    }
    """
    When I say "at which regions is kyma available?"
    

    And response relates to 
    """
    mentions centralus US Central (IA) for Azure, eu-central-1 (Frankfurt) for AWS (amazon web services) and us-east4 (Virginia) for GCP (google cloud platform)
    """
