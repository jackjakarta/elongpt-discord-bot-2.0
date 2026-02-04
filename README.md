Version 2.0 of [ElonGPT-Discord-Bot](https://github.com/jackjakarta/ElonGPT-Discord-Bot) with slash commands.

### Bot Setup

To set up this bot on your own server, follow these steps:

1. Clone this repository to your local machine.

2. Consider creating a virtual environment (recommended but optional).

3. Install the necessary dependencies by running the following command:

   ```bash
   pip install -r requirements.txt
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

### Or build and run with Docker

Build:

```bash
docker build -t yourimagename:tag .
```

Run:

```bash
docker run -d -t \
-e OPENAI_API_KEY=your-api-key \
-e DISCORD_TOKEN=your-api-key \
-e CMC_PRO_API_KEY=your-api-key \
...rest of env vars \
--name elongpt-bot \
yourimagename:tag
```
