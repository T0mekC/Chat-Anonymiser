# AWS Deployment Guide — Chat Anonymiser

This guide walks through deploying the Chat Anonymiser to AWS EC2 so it can be accessed by others via a browser. The application runs on a single EC2 instance — Ollama, FastAPI, and nginx all on the same machine.

**Estimated time:** 30–45 minutes on first run.

**Cost:** ~$0.042/hr while running (t3.medium). Stop the instance after each use — see [Stopping the instance](#stopping-and-starting-the-instance).

---

## Prerequisites

- An AWS account with permission to create EC2 instances, IAM roles, and SSM parameters
- Your Anthropic API key (`sk-ant-...`)
- The project pushed to a Git repository (GitHub, GitLab, etc.) that the EC2 instance can clone

---

## Overview

```
Browser → EC2 (port 80)
            └─ nginx → uvicorn (port 8000)
                          └─ FastAPI app
                               ├─ Ollama / phi3:3.8b  (local, port 11434)
                               └─ SSM Parameter Store  (Anthropic API key)
```

The instance has no SSH port open. You access it via **AWS Systems Manager Session Manager** — no key pair needed.

---

## Step 1 — Store the API key in Parameter Store

1. Open the [AWS Systems Manager console](https://console.aws.amazon.com/systems-manager/parameters).
2. In the left sidebar click **Parameter Store**, then **Create parameter**.
3. Fill in:
   - **Name:** `/chat-anonymiser/anthropic-api-key`
   - **Tier:** Standard
   - **Type:** SecureString
   - **KMS key source:** My current account → select `alias/aws/ssm` (default)
   - **Value:** your Anthropic API key (`sk-ant-...`)
4. Click **Create parameter**.

---

## Step 2 — Create an IAM role for the EC2 instance

1. Open the [IAM console](https://console.aws.amazon.com/iam/home#/roles) and click **Create role**.
2. **Trusted entity type:** AWS service → **EC2** → Next.
3. On the *Add permissions* screen, search for and tick:
   - `AmazonSSMManagedInstanceCore` — enables Session Manager access
   - `CloudWatchAgentServerPolicy` — enables application log forwarding
4. Click **Next**, name the role `chat-anonymiser-ec2-role`, then **Create role**.
5. After creation, open the role and click **Add permissions → Create inline policy**.
6. Switch to the **JSON** editor and paste the policy below, replacing `<region>` and `<account-id>`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ssm:GetParameter",
      "Resource": "arn:aws:ssm:<region>:<account-id>:parameter/chat-anonymiser/anthropic-api-key"
    }
  ]
}
```

7. Name the policy `chat-anonymiser-ssm-read` and click **Create policy**.

> **Tip:** Find your account ID in the top-right corner of the AWS console next to your account name.

---

## Step 3 — Create a security group

1. Open the [EC2 console](https://console.aws.amazon.com/ec2/v2/home#SecurityGroups) → **Security Groups** → **Create security group**.
2. Fill in:
   - **Name:** `chat-anonymiser-sg`
   - **Description:** Chat Anonymiser — HTTP only
   - **VPC:** leave as default
3. Under **Inbound rules** click **Add rule**:
   - **Type:** HTTP | **Port:** 80 | **Source:** Anywhere-IPv4 (`0.0.0.0/0`)
4. Leave **Outbound rules** as the default (allow all).
5. Click **Create security group**.

> Port 22 (SSH) is intentionally left closed — access is via Session Manager only.

---

## Step 4 — Launch the EC2 instance

1. Open the [EC2 console](https://console.aws.amazon.com/ec2/v2/home#Instances) → **Launch instances**.

2. **Name:** `chat-anonymiser`

3. **AMI:** Search for *Amazon Linux 2023 AMI* and select it (64-bit x86).

4. **Instance type:** `c7i-flex.large` (2 vCPU / 4 GB RAM — required for Ollama). Verify free-tier eligibility in your account's [Free Tier dashboard](https://console.aws.amazon.com/billing/home#/freetier) before launching; fall back to `t3.medium` (~$0.042/hr) if not eligible.

5. **Key pair:** select **Proceed without a key pair** — Session Manager is the access method.

6. **Network settings** → click **Edit**:
   - **Security group:** select existing → `chat-anonymiser-sg`
   - Leave subnet and auto-assign public IP as defaults

7. **Configure storage:** 20 GiB gp3, tick **Encrypted**, KMS key: `aws/ebs` (default).

8. **Advanced details** → scroll to **Metadata options**:
   - **IMDSv2:** Required

9. **Advanced details** → **IAM instance profile:** `chat-anonymiser-ec2-role`

10. Click **Launch instance**.

---

## Step 5 — (Optional) Assign an Elastic IP

Without an Elastic IP the instance gets a new public IP each time it starts.

1. In the EC2 console go to **Elastic IPs** → **Allocate Elastic IP address** → **Allocate**.
2. Select the newly allocated IP → **Actions → Associate Elastic IP address**.
3. Select your `chat-anonymiser` instance → **Associate**.

---

## Step 6 — Connect and run the setup script

Wait about 2 minutes after launch for the instance to reach *running* state and the SSM agent to register.

1. In the EC2 console, select the `chat-anonymiser` instance.
2. Click **Connect** → **Session Manager** → **Connect**.

   A browser terminal opens. You are logged in as `ssm-user`. Switch to `ec2-user`:

   ```bash
   sudo su - ec2-user
   ```

3. Edit the setup script to add your repository URL, then run it:

   ```bash
   # Clone the repo first so you can edit the script
   git clone <your-repo-url> /home/ec2-user/anonymiser

   # Open the script and replace <your-repo-url> with your actual URL
   nano /home/ec2-user/anonymiser/deploy/setup_ec2.sh
   # Change the REPO_URL line, then save with Ctrl+O, exit with Ctrl+X

   # Run the setup
   bash /home/ec2-user/anonymiser/deploy/setup_ec2.sh
   ```

   The script will:
   - Install nginx, Python 3.11, and git
   - Install Ollama and pull the phi3:3.8b model (~2 GB download — takes a few minutes)
   - Create a Python virtual environment and install app dependencies
   - Install and start the `anonymiser` systemd service (uvicorn)
   - Configure and start nginx

   When complete it prints: `Deploy complete. App is at http://<public-ip>`

4. Open that URL in your browser — the Chat Anonymiser should load.

---

## Verification

Run these from the Session Manager terminal to confirm everything is healthy:

```bash
# Check both services are running
sudo systemctl status anonymiser
sudo systemctl status ollama
sudo systemctl status nginx

# Tail app logs
sudo journalctl -u anonymiser -f

# Quick HTTP smoke test
curl -s http://localhost/
```

The `curl` should return the HTML of the app's index page.

---

## Stopping and starting the instance

**Stop** (pauses billing for compute — EBS storage still charged):

EC2 console → select instance → **Instance state → Stop instance**

**Start:**

EC2 console → select instance → **Instance state → Start instance**

Both `ollama` and `anonymiser` services are configured to start automatically on boot, so the app will be available a minute or two after the instance starts.

> If you did **not** assign an Elastic IP, the public IP changes on every start. Check the new IP in EC2 → Instances → Public IPv4 address.

---

## Updating the app

Connect via Session Manager and run:

```bash
sudo su - ec2-user
cd /home/ec2-user/anonymiser
git pull
/home/ec2-user/anonymiser/.venv/bin/pip install -q -r app/requirements.txt
sudo systemctl restart anonymiser
```

---

## Troubleshooting

**Session Manager "Connect" button is greyed out**
The SSM agent hasn't registered yet. Wait 2–3 minutes after launch, then try again. If it persists, verify the IAM instance profile is attached: EC2 → Instance → Security tab → IAM role.

**App returns 502 Bad Gateway**
uvicorn hasn't started yet or crashed. Check:
```bash
sudo systemctl status anonymiser
sudo journalctl -u anonymiser -n 50
```

**"Ollama is not running" error in the browser**
Ollama may still be loading the model. Check:
```bash
sudo systemctl status ollama
sudo journalctl -u ollama -n 20
```

**ANTHROPIC_API_KEY error on startup**
The app couldn't read the key from SSM. Verify:
1. The parameter name is exactly `/chat-anonymiser/anthropic-api-key`
2. The IAM role has the `chat-anonymiser-ssm-read` inline policy
3. The region in the inline policy ARN matches the region where the parameter was created

**phi3:3.8b model is missing**
Re-run the pull manually:
```bash
sudo systemctl stop anonymiser
ollama pull phi3:3.8b
sudo systemctl start anonymiser
```
