---
description: Deploy APAS (FastAPI + React) to PythonAnywhere
---

# Deploying APAS to PythonAnywhere

This guide covers deploying the FastAPI backend (which serves the pre-built React frontend) to PythonAnywhere.

## Prerequisites
- A PythonAnywhere account.
- The project code pushed to GitHub: `https://github.com/peter202309/APAS.git`

## Step 1: Pull Code to PythonAnywhere

1. Log in to PythonAnywhere and open a **Bash** console.
2. Clone the repository (if not done yet):
   ```bash
   git clone https://github.com/peter202309/APAS.git
   ```
   *If already cloned, pull the latest changes:*
   ```bash
   cd APAS
   git pull
   ```

## Step 2: Set up Virtual Environment

1. In the Bash console, create a virtual environment (assuming Python 3.10):
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 apas-env
   ```
   *(If `mkvirtualenv` command is not found, verify your account set up or use `python3.10 -m venv venv` and activate manually, but strict usage of `mkvirtualenv` is recommended on PA).*

2. Install dependencies:
   ```bash
   workon apas-env
   pip install -r APAS/requirements.txt
   ```
   *Note: Playwright installation might take time. Running Playwright browsers on PythonAnywhere requires specific system dependencies that might not be available on free tiers. For now, we install it to satisfy imports.*

## Step 3: Configure Web App

1. Go to the **Web** tab.
2. **Code** section:
   - **Source code**: `/home/yourusername/APAS`
   - **Working directory**: `/home/yourusername/APAS`
3. **Virtualenv** section:
   - Enter path: `/home/yourusername/.virtualenvs/apas-env`

## Step 4: Configure WSGI File

1. Click the link to edit the **WSGI configuration file** (e.g., `/var/www/yourusername_pythonanywhere_com_wsgi.py`).
2. Delete the default content and paste the following:

   ```python
   import sys
   import os

   # 1. Add project directory to path
   path = '/home/yourusername/APAS'  # CHANGE THIS to your actual path
   if path not in sys.path:
       sys.path.append(path)

   # 2. Set environment variables if needed
   # os.environ['SOME_VAR'] = 'value'

   # 3. Import FastAPI app and wrap with a2wsgi
   from apps.backend.main import app as application_asgi
   from a2wsgi import ASGIMiddleware

   application = ASGIMiddleware(application_asgi)
   ```
   *Replace `yourusername` with your actual PythonAnywhere username.*

## Step 5: Reload

1. Go back to the **Web** tab.
2. Click the green **Reload** button at the top.
3. Open your site URL (`yourusername.pythonanywhere.com`). You should see the APAS Dashboard.

## Troubleshooting

- **Static Files 404**: Ensure `apps/frontend/dist` exists on the server. We configured FastAPI to serve these, so specific Static Files mappings in the Web tab are NOT required, provided the build files were pushed to git.
- **Import Errors**: Check the **Error Log** linked in the Web tab.
