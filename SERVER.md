# Server Setup Documentation

Complete documentation for building the media server stack from scratch.

**OS:** Xubuntu  
**Docker:** Docker Compose for all services  
**Backups:** `/mnt/sync/Google/Backups`

## Table of Contents

1. [System Setup](#system-setup)
2. [Plex Media Server](#plex-media-server)
3. [Docker Containers](#docker-containers)
4. [Scripts & Automation](#scripts--automation)
5. [Backup Strategy](#backup-strategy)
6. [System Information](#system-information)

---

> Replace `SERVER_IP` with your server's IP and `STORAGE_IP` with your storage/NAS IP throughout this guide and in docker-compose files.

## System Setup

Follow these steps to set up the base system and storage.

**1. Update system**

```bash
sudo apt update && sudo apt upgrade -y
```

**2. Install system dependencies**

```bash
sudo apt update
sudo apt install -y python3 python3-pip ffmpeg mediainfo cifs-utils curl git
```

**3. Create application directories**

```bash
mkdir -p ~/docker ~/scripts
```

Backups are stored in `/mnt/sync/Google/Backups/` (on the mounted NAS share). Ensure `/mnt/sync` is synced to cloud storage (e.g., Google Drive).

**4. Create SMB credentials file**

```bash
cat > ~/smbcreds.txt << 'EOF'
username=YOUR_SMB_USERNAME
password=YOUR_SMB_PASSWORD
EOF
chmod 600 ~/smbcreds.txt
```

**5. Configure SMB mounts** via `/etc/fstab`:
- `//STORAGE_IP/Media` → `/mnt/media`
- `//STORAGE_IP/Sync` → `/mnt/sync`

**6. Configure firewall (ufw)**

Enable the firewall and allow SSH and other services:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

## Plex Media Server

**1. Add Plex repository with GPG key**

```bash
curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | sudo gpg --dearmor -o /etc/apt/keyrings/plexmediaserver.gpg
echo "deb [signed-by=/etc/apt/keyrings/plexmediaserver.gpg] https://downloads.plex.tv/repo/deb public main" | sudo tee /etc/apt/sources.list.d/plexmediaserver.list > /dev/null
```

**2. Install and enable Plex**

```bash
sudo apt update
sudo apt install -y plexmediaserver
sudo systemctl start plexmediaserver
sudo systemctl enable plexmediaserver
sudo ufw allow 32400/tcp   # Allow Plex through firewall
```

## Docker Containers

**1. Install Docker**

Add Docker's official repository and GPG key:

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Install Docker and Compose v2:

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

**2. Add user to docker group**

The docker group is created automatically during Docker installation. Add your user:

```bash
sudo usermod -aG docker <username>
```

The group change takes effect on next login. To use docker immediately without logging out, run:

```bash
newgrp docker
```

**3. Restore docker directories** from backup or git:

```bash
cp -r /backup/docker/* ~/docker/
```

**4. Review Docker containers**

All Docker containers located in `~/docker/<service>/` with `docker-compose.yml`.

| Service | Container | Purpose | Port |
|---------|-----------|---------|------|
| sonarr | sonarr | TV show management | 8989 |
| radarr | radarr | Movie management | 7878 |
| prowlarr | prowlarr | Indexer management | 9696 |
| bazarr | bazarr | Subtitle management | 6767 |
| cleanuparr | cleanuparr | Cleanup automation | 11011 |
| tautulli | tautulli | Plex monitoring | 8181 |
| filebrowser | filebrowser | File management | 8082 |
| gitea | gitea | Git hosting | 3000 (HTTP)<br>2222 (SSH) |
| uptime-kuma | uptime-kuma | Uptime monitoring | 3001 |
| watchtower | watchtower | Auto-update containers | — |
| flaresolverr | flaresolverr | Cloudflare solver | 8191 |
| signal-api | signal-api | Signal messenger (used for uptime-kuma alerts) | 8088 |
| monitor | monitor | Monitoring stack | 9090 (Prometheus)<br>3003 (Grafana)<br>8083 (cAdvisor) |

**5. Start all Docker containers**

```bash
cd ~/docker
for dir in */; do
  echo "Starting $dir"
  cd "$dir"
  docker compose up -d
  cd ..
done
```

## Scripts & Automation

See [README.md](README.md) for setup and configuration of scripts.

---

## Backup Strategy

Weekly backups run Sunday at 3 AM via `backuparr.sh`:

**Backs up:**
- Sonarr, Radarr, Prowlarr configurations
- Cleanuparr config
- Tautulli database and cache
- qBittorrent config
- Docker container data folders
- Scripts directory

**Backed up to:** `/mnt/sync/Google/Backups/`

**Note:** Plex Media Server is installed natively (not in Docker), and its metadata database at `/var/lib/plexmediaserver/` is not included in these backups. This is intentional — the library data is derived from scanning your actual media files and can be rebuilt. If you need to preserve Plex library metadata and watched/play history, manually back up this directory separately.

---

## System Information

**Reboot Schedule:** Daily at 5 AM  
**Backup Schedule:** Weekly Sunday at 3 AM  
**Mount Check Interval:** Every 5 minutes

**Critical Files:**
- `~/smbcreds.txt` - SMB credentials (must be created before mounts work)
- `~/scripts/config.yml` - API keys and configuration
- `/etc/fstab` - Mount point configuration

**Cloud Backup:**
- `/mnt/sync` should be synced to cloud storage (e.g. Google Drive) in case of local NAS failure

**Schedules:**
- All containers auto-restart on system reboot
- Watchtower auto-updates other containers (scheduled 6 AM daily)
- Mount points auto-mount on boot with systemd automount
- Backups are differential (rsync with --delete)
- Config.yml is gitignored - keep local only
