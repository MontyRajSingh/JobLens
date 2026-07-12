# Deploying JobLens on Google Cloud Platform (GCP)

This guide walks you through deploying JobLens to a Google Compute Engine (GCE) VM instance running Docker Compose under the **GCP Always Free Tier**.

The stack consists of:
- `frontend`: Nginx serving the React build on port `80` and proxying `/api` requests.
- `api`: FastAPI on the internal Docker network.
- `db`: Postgres with a persistent Docker volume.

---

## 1. Create the GCP VM Instance

To stay within the **GCP Always Free Tier**, you must configure the instance with the following specifications:

1. Go to the [Google Cloud Console Compute Engine](https://console.cloud.google.com/compute/).
2. Click **Create Instance**.
3. Set the following settings:
   - **Name**: `joblens-vm`
   - **Region**: Select `us-central1` (Iowa), `us-east1` (South Carolina), or `us-west1` (Oregon).
   - **Machine configuration**: General-purpose > **E2**.
   - **Machine type**: **`e2-micro`** (2 vCPUs, 1 GB memory).
   - **Boot disk**: Click **Change**:
     - Operating System: **Ubuntu**
     - Version: **Ubuntu 22.04 LTS** or **Ubuntu 24.04 LTS**
     - Boot disk type: **Standard Persistent Disk**
     - Size: **30 GB** (This is the maximum free tier size).
     - Click **Select**.
   - **Firewall**: Check both:
     - [x] **Allow HTTP traffic**
     - [x] **Allow HTTPS traffic**
4. Click **Create**.

---

## 2. Configure a Static External IP (Recommended)

By default, GCP VM instances are assigned an ephemeral external IP address that changes when the instance restarts. To make it static:
1. Go to **VPC Network** > **IP addresses**.
2. Find the ephemeral external IP assigned to your instance.
3. Click the actions menu (three dots) and select **Reserve static external IP address**.
4. Give it a name and click **Reserve**.

---

## 3. SSH into the VM and Configure Swap Space

Because the `e2-micro` instance only has 1 GB of RAM, running PostgreSQL, FastAPI, Nginx, and Chrome (scraping) simultaneously will trigger Out-of-Memory (OOM) errors. To solve this, you **must** configure a swap file.

Connect to your instance via SSH and run the following commands:

```bash
# Create a 2GB swap file
sudo fallocate -l 2G /swapfile

# Set the correct permissions
sudo chmod 600 /swapfile

# Mark the file as swap space
sudo mkswap /swapfile

# Enable the swap file
sudo swapon /swapfile

# Make the swap file persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify swap is active
free -h
```

---

## 4. Install Docker and Docker Compose

Update packages and install Docker:

```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker Engine and plugins
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
sudo docker --version
sudo docker compose version
```

---

## 5. Clone and Configure JobLens

On the VM, clone the repository and set up the environment variables:

```bash
git clone <your-github-repo-url> JobLens
cd JobLens

# Copy the GCP environment variables template
cp .env.gcp.example .env.gcp
nano .env.gcp
```

At minimum, set a strong Postgres password:
```bash
POSTGRES_PASSWORD=<your-secure-password>
```

---

## 6. Build and Start the Application

Build and launch the containers in detached mode:

```bash
sudo docker compose --env-file .env.gcp -f docker-compose.gcp.yml up -d --build
```

Verify service statuses:
```bash
sudo docker compose --env-file .env.gcp -f docker-compose.gcp.yml ps
sudo docker compose --env-file .env.gcp -f docker-compose.gcp.yml logs -f api
```

Health check checks:
```bash
curl http://localhost/health
curl http://localhost/api/v1/jobs?limit=1
```

From your local machine, open:
```text
http://<your-static-external-ip>/
```

---

## 7. Database Reseeding and Persistence

By default, on the first start, the database seeds from `output/jobs_master.csv` since `SKIP_RESEED=false`.

Once the database has successfully seeded, you can make the Postgres data persistent independently of git changes. Open `.env.gcp` and update `SKIP_RESEED`:

```bash
SKIP_RESEED=true
```

Then restart the services to apply the change:
```bash
sudo docker compose --env-file .env.gcp -f docker-compose.gcp.yml up -d
```

---

## 8. Run Scrapers Manually

To trigger a scrape manually inside the container environment:

```bash
sudo docker compose --env-file .env.gcp -f docker-compose.gcp.yml run --rm api python main.py --sources naukri wellfound --max-jobs 20
sudo docker compose --env-file .env.gcp -f docker-compose.gcp.yml restart api
```

---

## 9. Set up TLS / HTTPS (Caddy Example)

To configure HTTPS, point your domain's `A` record to your static external IP, and install Caddy on the VM to act as an automatic HTTPS reverse proxy.

1. Install Caddy:
   ```bash
   sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
   sudo apt update
   sudo apt install caddy
   ```

2. Open and edit `/etc/caddy/Caddyfile`:
   ```caddy
   yourdomain.com {
       reverse_proxy localhost:80
   }
   ```

3. Restart Caddy to enable HTTPS automatically via Let's Encrypt:
   ```bash
   sudo systemctl restart caddy
   ```
