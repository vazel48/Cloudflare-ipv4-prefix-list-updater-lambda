import os
import json
import logging
import boto3
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2_client = boto3.client("ec2")

def lambda_handler(event, context):
    """
    This Lambda updates an AWS Prefix List with the latest CloudFlare IPv4 ranges
    on a daily schedule (triggered by an EventBridge rule).
    IPv6 addresses are intentionally excluded.
    """

    # 1. Read the Prefix List ID from environment variables
    prefix_list_id = os.environ.get("PREFIX_LIST_ID")
    if not prefix_list_id:
        logger.error("PREFIX_LIST_ID is not set in Lambda environment variables.")
        raise ValueError("PREFIX_LIST_ID is not set in Lambda environment variables.")

    logger.info(f"Using PrefixListId: {prefix_list_id}")

    # 2. Fetch CloudFlare IPv4 IPs using urllib
    try:
        with urllib.request.urlopen("https://api.cloudflare.com/client/v4/ips", timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        logger.info("Successfully fetched CloudFlare IP addresses.")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.error(f"Error fetching CloudFlare IP addresses: {e}")
        raise RuntimeError(f"Error fetching CloudFlare IP addresses: {e}")

    if "result" not in data:
        logger.error("Unexpected response from CloudFlare: missing 'result' field.")
        raise RuntimeError("Unexpected response from CloudFlare: missing 'result' field.")

    ipv4_cidrs = data["result"].get("ipv4_cidrs", [])
    cf_cidrs = set(ipv4_cidrs)  # Only IPv4

    # Захист від повністю порожнього списку адрес (щоб не стерти Prefix List):
    if not cf_cidrs:
        logger.error("CloudFlare returned an empty list of IPv4 addresses. Skipping update to avoid wiping out the Prefix List.")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "CloudFlare returned an empty list of IPv4 addresses. No changes were made to the Prefix List."
            })
        }

    # 3. Describe the current Prefix List to get the current version
    response_pl = ec2_client.describe_managed_prefix_lists(PrefixListIds=[prefix_list_id])
    prefix_list_info = response_pl["PrefixLists"][0]
    current_version = prefix_list_info["Version"]
    logger.info(f"Current PrefixList version: {current_version}")

    # 4. Get the current Prefix List entries
    existing_entries = []
    response_entries = ec2_client.get_managed_prefix_list_entries(
        PrefixListId=prefix_list_id,
        MaxResults=100
    )
    existing_entries.extend(response_entries["Entries"])
    existing_cidrs = set(entry["Cidr"] for entry in existing_entries)
    logger.info(f"Currently stored CIDRs in PrefixList: {existing_cidrs}")

    # 5. Determine which CIDRs need to be added vs. removed
    cidrs_to_add = cf_cidrs - existing_cidrs
    cidrs_to_remove = existing_cidrs - cf_cidrs

    logger.info(f"CIDRs to add: {cidrs_to_add}")
    logger.info(f"CIDRs to remove: {cidrs_to_remove}")

    if not cidrs_to_add and not cidrs_to_remove:
        logger.info("No changes needed. CloudFlare IPv4 IPs are already up-to-date.")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "No changes needed. CloudFlare IPv4 IPs are already up-to-date.",
                "prefix_list_id": prefix_list_id
            })
        }

    add_requests = [
        {"Cidr": cidr, "Description": f"CloudFlare_{i}"}
        for i, cidr in enumerate(sorted(cidrs_to_add))
    ]
    remove_requests = [
        {"Cidr": cidr}
        for cidr in sorted(cidrs_to_remove)
    ]

    # 6. Modify the prefix list
    try:
        ec2_client.modify_managed_prefix_list(
            PrefixListId=prefix_list_id,
            CurrentVersion=current_version,
            AddEntries=add_requests,
            RemoveEntries=remove_requests
        )
        logger.info("Successfully updated CloudFlare IPv4 IPs in the Prefix List.")
    except ec2_client.exceptions.ClientError as e:
        logger.error(f"Failed to update prefix list: {e}")
        raise RuntimeError(f"Failed to update prefix list: {e}")

    # 7. Return success
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Successfully updated CloudFlare IPv4 IPs in Prefix List.",
            "prefix_list_id": prefix_list_id,
            "added": list(cidrs_to_add),
            "removed": list(cidrs_to_remove)
        })
    }
