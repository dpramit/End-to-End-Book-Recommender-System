# End-to-End-Book-Recommender-System


## Workflow

This is the order in which the project is built/extended. Each stage feeds the next one, so when adding a new pipeline step, follow this same sequence:

- config.yaml           # central place for paths, URLs, and pipeline parameters
- entity                # dataclasses/config objects that carry the config values around type-safely
- config/configuration.py  # reads config.yaml and builds the entity objects above
- components            # the actual pipeline stages (data ingestion, transformation, model training, etc.)
- pipeline               # orchestrates the components in sequence to produce artifacts
- main.py                # entry point that runs the full training pipeline end-to-end
- app.py                 # Streamlit UI that serves recommendations using the trained artifacts


# How to run?

These local steps are intentionally small and sequential. Complete each one before moving forward so environment, dependencies, and runtime behavior stay predictable.

### STEP 01- Create a conda environment after opening the repository

Isolates project dependencies from your system Python so package versions don't clash with other projects.
For further reading: Conda environment management guide: https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html

```bash
# Create an isolated Python 3.7.10 environment named "books"
conda create -n books python=3.7.10 -y
```

```bash
# Activate the environment so subsequent pip/python commands use it
# Activate the environment so pip/python point to this env
conda activate books
```


### STEP 02- install the requirements

Installs all Python packages the pipeline and app depend on (pinned in requirements.txt).
This keeps dependency versions reproducible across machines and helps reduce environment-specific bugs during model training and app serving.
For further reading: pip requirements file format: https://pip.pypa.io/en/stable/reference/requirements-file-format/

```bash
# Install pinned dependencies used by both training and the Streamlit app
pip install -r requirements.txt
```

Tip: If installation fails, confirm the environment is active and retry with an updated installer using `python -m pip install --upgrade pip`.


### STEP 03- Run the app.py file

Launches the Streamlit web app locally (defaults to http://localhost:8501) using the pre-trained artifacts under `artifacts/`. Run `python main.py` first if you need to (re)generate those artifacts from raw data.
For further reading: Streamlit app basics and run options: https://docs.streamlit.io/develop/concepts/architecture/run-your-app

```bash
# Start the Streamlit app on port 8501 (default)
streamlit run app.py
```

```bash
# If recommendations appear empty or stale, regenerate artifacts first
# Re-run the full training pipeline to refresh artifacts/
python main.py
```



# Streamlit App Docker Image Deployment (Azure)

This section deploys the app as a Docker container running on a standalone Azure VM (as opposed to running it locally via `streamlit run`).

Deployment flow summary:
1. Provision Azure infrastructure (resource group + VM + port rule).
2. Prepare the VM (Docker + source code).
3. Build and run the image.
4. Optionally publish to ACR for reuse.

## 1. Login to Azure and create a resource group + Ubuntu VM

Note: Open port 8501 on the VM's Network Security Group, or the app will run but remain unreachable from outside the VM.
For further reading:
1. Azure Resource Groups: https://learn.microsoft.com/azure/azure-resource-manager/management/manage-resource-groups-portal
2. Azure VM quickstart (CLI): https://learn.microsoft.com/azure/virtual-machines/linux/quick-create-cli

```bash
# Authenticate the Azure CLI against your Azure account
az login

# Resource group: a logical container that groups all resources for this project (VM, ACR, etc.)
az group create --name books_recommender_rg --location eastus



# Provision an Ubuntu VM to host the Docker container; --generate-ssh-keys creates/reuses a local SSH keypair for access
az vm create \
  --resource-group books_recommender_rg \
  --name books-recommender-vm \
  --image Ubuntu2204 \
  --admin-username azureuser \
  --generate-ssh-keys \
  --size Standard_B2s

# Open port 8501 in the VM's firewall (NSG) so the Streamlit app is reachable from the internet
az vm open-port --resource-group books_recommender_rg --name books-recommender-vm --port 8501
```

Why this matters: the VM hosts Docker, and the NSG rule is what allows browser access to Streamlit from your local machine.

## 2. SSH into the VM and run the following commands

```bash
# Connect to the VM using your SSH key and VM public IP (from az vm create output)
# Use your own key path and VM public IP address
ssh -i <path-to-private-key>.pem azureuser@<vm-public-ip>

```

Set up the VM with package updates and Docker before building the image.
For further reading: Docker Engine installation on Ubuntu: https://docs.docker.com/engine/install/ubuntu/

```bash
# Refresh package metadata
sudo apt-get update -y

# Upgrade installed packages
sudo apt-get upgrade -y

# Download Docker install script

curl -fsSL https://get.docker.com -o get-docker.sh

# Install Docker engine/CLI
sudo sh get-docker.sh

# Add the current user to the docker group so docker commands don't need sudo
sudo usermod -aG docker azureuser

# Reload group membership without needing to log out/in
newgrp docker
```

```bash
# Optional verification command
# Confirm Docker is installed and accessible without sudo
docker --version
```

```bash
# Pull the project source onto the VM
# Clone your repository onto the VM
git clone https://github.com/<your-username>/End-to-End-Book-Recommender-System.git

# Enter the project directory
cd End-to-End-Book-Recommender-System
```

Build the Docker image from the repo's Dockerfile and tag it as stapp:latest.
For further reading: Docker build reference: https://docs.docker.com/reference/cli/docker/buildx/build/

```bash
# Building from Dockerfile captures app code + dependencies into an immutable image
# Build the app image from Dockerfile in the current directory
docker build -t stapp:latest . 
```

Note: this repository's `requirements.txt` includes `-e .`, so Docker must copy the full project before dependency installation (already handled in `Dockerfile`).

```bash
# List local images to confirm the build succeeded
# Show all local images and verify stapp exists
docker images -a  
```

Run the image as a background (-d) container and map VM port 8501 to container port 8501.
For further reading: Docker run reference: https://docs.docker.com/reference/cli/docker/container/run/

```bash
# Port mapping publishes the Streamlit service through the VM public IP
# Run container in detached mode and expose Streamlit on port 8501
docker run -d -p 8501:8501 stapp 
```

The app is now reachable at `http://<vm-public-ip>:8501/`.

```bash
# Confirm the container is running and capture container_id
# List running containers and capture the container ID
docker ps  
```

```bash
# Stop the running container (replace container_id with the value from docker ps)
# Stop a specific running container
docker stop container_id
```

```bash
# Remove stopped containers to free disk space
# Remove all stopped containers to free storage
docker rm $(docker ps -a -q)
```



## 3. (Optional) Push the image to Azure Container Registry (ACR)

Useful if you want to store/version the image in the cloud and deploy it elsewhere (e.g. Azure Container Instances/AKS) instead of building it fresh on every VM.
For further reading: Azure Container Registry overview: https://learn.microsoft.com/azure/container-registry/container-registry-intro

Before creating ACR, ensure your subscription is registered for the Container Registry provider.

```bash
az provider register --namespace Microsoft.ContainerRegistry
az provider show --namespace Microsoft.ContainerRegistry --query registrationState -o tsv
```

If you see `az: command not found` on the Ubuntu VM, install Azure CLI first:

```bash
# Install Microsoft package signing key and repository
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Verify installation
az version

# Re-authenticate after installation
az login
```

```bash
# Create a private container registry to store the image
 az acr create --resource-group books_recommender_rg --name booksrecommenderacr --sku Basic

# Authenticate Docker against the registry
az acr login --name booksrecommenderacr
```

If `az login` or `az acr login` fails with `Error Code: 530035` (device unregistered / blocked by tenant policy):

1. Try explicit tenant + device code login (works in many restricted SSH/VM flows):

```bash
az login --tenant <your-tenant-id> --use-device-code
```

2. If your organization still blocks Azure CLI sign-in on that VM, use ACR admin credentials instead of `az acr login`:

```bash
# Run these from a machine/account that CAN access Azure (Portal or CLI)
az acr update -n booksrecommenderacr --admin-enabled true
az acr credential show -n booksrecommenderacr

# Then, on the VM, login Docker directly with the returned username/password
docker login booksrecommenderacr.azurecr.io -u <acr-username> -p <acr-password>
```

Security note: never commit or share real tokens/passwords in this repository. If credentials were exposed previously, rotate them immediately in Azure.

If tenant policy continues to block sign-in, contact your Azure AD admin and share Correlation ID + Timestamp from the error page.

If Docker is not installed on the machine where you run this command, use `--expose-token` for non-Docker auth flows:

```bash
az acr login --name booksrecommenderacr --expose-token
```

Important: run the next Docker tag/push commands on the same machine where `stapp:latest` exists (your Ubuntu VM if you built it there).

This is optional but useful when you want repeatable deployments without rebuilding the image on each VM.

```bash
# Retag the local image with the registry path, then push it
# Tag local image with ACR registry path
docker tag stapp:latest booksrecommenderacr.azurecr.io/stapp:latest

# Push tagged image to ACR
docker push booksrecommenderacr.azurecr.io/stapp:latest
```

```bash
# Remove the local ACR-tagged copy (the registry copy remains)
# Remove only the local ACR-tagged image copy
docker rmi booksrecommenderacr.azurecr.io/stapp:latest
```

```bash
# Pull the image from ACR on this or another machine
# Pull image from ACR (for another VM/machine)
docker pull booksrecommenderacr.azurecr.io/stapp:latest
```





