# HERDOC Ansible configuration

This playbook configures an Ubuntu or Debian Linux VM with Python, a dedicated `herdoc` system account, an isolated virtual environment, managed application files, a protected environment file, and a systemd service. `inventory.example.ini` is the portable template and uses `vboxuser`. Since Ansible is installed on the target VM, run the controller as `vboxuser` and set `ansible_connection=local` in the ignored local `inventory.ini`; this avoids a machine-specific address. If using a separate Linux controller, set `ansible_host` to the target's reachable address instead. Never commit the local inventory or database/JWT values.

The playbook copies only the backend app, Alembic files, and dependency/configuration files, so it does not copy `.env` files or local test databases. The database must be reachable from the VM. Set these values in the operator's shell before running the playbook; do not put them in inventory or commit them:

- `HERDOC_DATABASE_URL`: SQLAlchemy MySQL URL for the target database
- `HERDOC_JWT_SECRET`: random secret of at least 32 characters

Ubuntu shell example (enter real values privately on the VM):

```powershell
read -rsp 'MySQL URL: ' HERDOC_DATABASE_URL; echo
export HERDOC_DATABASE_URL
export HERDOC_JWT_SECRET="$(openssl rand -hex 32)"
test -f ansible/inventory.ini || cp ansible/inventory.example.ini ansible/inventory.ini
# Edit the host line: use ansible_connection=local with ansible_user=vboxuser.
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --ask-become-pass
unset HERDOC_DATABASE_URL HERDOC_JWT_SECRET
```

Run these commands from the repository root on the Ubuntu Ansible controller. Confirm `whoami` reports `vboxuser`; the local connection runs against that VM and `--ask-become-pass` supplies sudo access. The database must be reachable from the VM. Database schema migrations run once before the service starts.

Run Ansible from a Linux control node with Ansible installed; this Windows environment has no Ansible CLI or WSL distribution. Report a deployment only after the live playbook completes successfully.
