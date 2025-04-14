# CloudFlare Prefix List Updater (AWS Lambda)

This AWS Lambda function automatically updates an AWS EC2 Managed Prefix List with the latest **CloudFlare IPv4** ranges.
It is designed to run on a scheduled basis (e.g. via EventBridge rule) to ensure that your AWS infrastructure always allows access to the current CloudFlare IPs.

⚠️ Only IPv4 is supported. IPv6 ranges are intentionally ignored.

## 🚀 Features

- Fetches latest IPv4 ranges from CloudFlare API
- Compares with existing AWS Prefix List
- Adds missing IPs and removes outdated ones
- Skips update if CloudFlare returns an empty list (to avoid data loss)
- Logs each step of the process

## 📦 Requirements

- An AWS EC2 **Managed Prefix List** (already created)
- Lambda environment variable `PREFIX_LIST_ID` with the Prefix List ID
- IAM role with permissions:
  - `ec2:DescribeManagedPrefixLists`
  - `ec2:GetManagedPrefixListEntries`
  - `ec2:ModifyManagedPrefixList`

## 🛠️ Setup

1. Create or choose an existing managed prefix list in AWS VPC.
2. Deploy the Lambda function (just paste the code to Lambda).
3. Set the environment variable `PREFIX_LIST_ID` in Lambda config.
4. (Optional) Schedule the function with EventBridge rule (e.g. once per day).



