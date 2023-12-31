from config import *

# Import the Secret Manager client library.
from google.cloud import secretmanager
import google_crc32c
import json

# GCP project in which to store secrets in Secret Manager.
project_id = "gmail-neon-op-integration"

secrets = {
    "N_APIkey": N_APIkey,
    "O_APIkey": O_APIkey,
    "O_APIuser": O_APIuser,
}

def create_secret(project_id: str, secret_id: str, payload: str) -> secretmanager.CreateSecretRequest:
    """
    Create a new secret with the given name, then create a secret version. A secret is a logical wrapper
    around a collection of secret versions. Secret versions hold the actual
    secret material.
    """
    # Create the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the parent project.
    parent = f"projects/{project_id}"

    # Create the secret.
    secret = client.create_secret(
        request={
            "parent": parent,
            "secret_id": secret_id,
            "secret": {"replication": {"automatic": {}}},
        }
    )

    # Convert the string payload into a bytes. This step can be omitted if you
    # pass in bytes instead of a str for the payload argument.
    payload_bytes = payload.encode("UTF-8")

    # Calculate payload checksum. Passing a checksum in add-version request
    # is optional.
    crc32c = google_crc32c.Checksum()
    crc32c.update(payload_bytes)

    # Add the secret version.
    version = client.add_secret_version(
        request={
            "parent": secret.name, 
            "payload": {
                "data": payload_bytes,
                "data_crc32c": int(crc32c.hexdigest(), 16),
                }
            }
    )


def main():
    keys = json.dumps(secrets)
    create_secret(project_id, "matthew", keys)

if __name__ == "__main__":
    main()