Version 2.0 of [ElonGPT-Discord-Bot](https://github.com/jackjakarta/ElonGPT-Discord-Bot) with slash commands.

### Bot Setup

To set up this bot on your own server, follow these steps:

1. Clone this repository to your local machine.

2. Consider creating a virtual environment (recommended but optional).

3. Install the necessary dependencies by running the following command:

   ```bash
   pip install -r requirements.txt
   ```

   For development (formatting, linting, and `dev.py` hot-reload), also install the dev tooling:

   ```bash
   pip install -r requirements-dev.txt
   ```

4. Configure your environment variables following the template provided at `.env.op`.

5. Start the bot by executing the following command:

   ```bash
   python main.py
   ```

6. Or, run dev mode with hot reload:

   ```bash
   python dev.py
   ```

### Or build and run with Docker Compose

With a `.env` file in place (see step 4 above), build and start the bot:

```bash
docker compose up -d --build
```

The container runs as a non-root user with a read-only root filesystem and all
Linux capabilities dropped (see `docker-compose.yml`). To run a prebuilt image
from GHCR instead of building locally:

```bash
ELONGPT_IMAGE=ghcr.io/<user>/elongpt:<tag> docker compose up -d
```

Tail logs and stop with:

```bash
docker compose logs -f
docker compose down
```
