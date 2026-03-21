# Prompt Anonymiser

Anonymises sensitive information in your prompts before sending them to an external AI model. Personal data — names, emails, phone numbers, addresses, and more — is detected locally and replaced with opaque placeholders (e.g. `[NAME_1]`, `[EMAIL_1]`). The external model never sees your real data. When the response arrives, placeholders are swapped back so you read the answer with your original information restored.

---

## Prerequisites

All platforms require:

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11 or newer | |
| Ollama | Latest | Runs the local anonymisation model |
| phi3:3.8b model | — | Pulled via Ollama |
| Anthropic API key | — | For Claude Haiku responses |

---

## macOS

### 1. Install Ollama

```bash
brew install ollama
```

Or download the macOS app from [ollama.com](https://ollama.com) and drag it to Applications.

### 2. Pull the model

```bash
ollama pull phi3:3.8b
```

### 3. Install Python 3.11+

```bash
brew install python@3.11
```

Or download from [python.org](https://python.org).

### 4. Configure your API key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 5. Run the app

```bash
chmod +x start.sh
./start.sh
```

Open **http://localhost:8000** in your browser.

---

## Windows

### 1. Install Ollama

Download and run the Windows installer from [ollama.com](https://ollama.com). Ollama installs as a background service and starts automatically.

### 2. Pull the model

Open Command Prompt or PowerShell:

```powershell
ollama pull phi3:3.8b
```

### 3. Install Python 3.11+

Download from [python.org](https://python.org). During installation, check **"Add Python to PATH"**.

Verify:

```powershell
python --version
```

### 4. Configure your API key

Create a `.env` file in the project root (next to `README.md`):

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 5. Run the app

Open PowerShell in the project root:

```powershell
# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r app\requirements.txt

# Start the app
cd app
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

If you see a script execution error, run this first:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Open **http://localhost:8000** in your browser.

### 5a. Optional: create a startup script

Save the following as `start.bat` in the project root for convenience:

```bat
@echo off
call .venv\Scripts\activate.bat
cd app
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Run it with `start.bat` from the project root.

---

## Linux

### 1. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Start the Ollama service:

```bash
ollama serve &
```

Or use systemd if available on your distro:

```bash
sudo systemctl enable --now ollama
```

### 2. Pull the model

```bash
ollama pull phi3:3.8b
```

### 3. Install Python 3.11+

**Debian / Ubuntu:**

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip
```

**Fedora / RHEL:**

```bash
sudo dnf install -y python3.11
```

**Arch:**

```bash
sudo pacman -S python
```

### 4. Configure your API key

```bash
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env
```

### 5. Run the app

```bash
chmod +x start.sh
./start.sh
```

Open **http://localhost:8000** in your browser.

---

## Stopping the app

Press `Ctrl+C` in the terminal where the app is running.

To also stop Ollama (if you started it manually):

```bash
# macOS / Linux
pkill ollama

# Windows — right-click the Ollama tray icon → Quit
```

---

## Troubleshooting

**"please ensure Ollama is running"**
Ollama is not reachable. Start it with `ollama serve` (macOS/Linux) or launch the Ollama app (Windows), then refresh the page.

**"ANTHROPIC_API_KEY not set"**
The `.env` file is missing or in the wrong location. It must be in the project root (same folder as `README.md`), not inside `app/`.

**Port 8000 already in use**
Another process is using the port. Either stop that process or change the port:
```bash
uvicorn main:app --host 127.0.0.1 --port 8080 --reload
```
Then open **http://localhost:8080**.

**phi3:3.8b not found**
Run `ollama pull phi3:3.8b` and wait for the download to complete (~2 GB).
