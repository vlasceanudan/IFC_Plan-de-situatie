# IFC Plan de situație

This repository contains a small Streamlit application for enriching IFC files with site and land registration information in Romanian.

## Running locally

1. Install the requirements (and Node dependencies):
   ```bash
   pip install -r requirements.txt
   npm install
   ```
   The fragment converter requires Node 18+ to be available on the system.
   When deploying to Streamlit Cloud, create a `packages.txt` file containing
   the following lines so Node gets installed:

   ```
   nodejs
   npm
   ```
2. Launch the app:
   ```bash
   streamlit run ifc_land_registration_app.py
   ```
3. Open the presented local URL in your browser.

Python 3.12 is expected (see `runtime.txt`). A dev container configuration is included for easy setup in VS Code or GitHub Codespaces.

## Usage

After launching the app you will be prompted to upload an IFC file. The interface lets you edit project metadata, beneficiary details, land registration fields and the site address. When you apply the changes, an updated IFC file becomes available for download.

Large IFC files are converted to the lightweight **Fragments** format before visualization to keep the viewer responsive. The conversion relies on the included `convert_to_fragments.js` script and Node. If Node isn't present, the app falls back to client-side conversion which can be slower for big models.

## Demo

A live demo is available at [https://ifcplan-de-situatie-v0.streamlit.app/](https://ifcplan-de-situatie-v0.streamlit.app/).

## Repository contents

- `ifc_land_registration_app.py` – Streamlit application.
- `requirements.txt` – Python dependencies.
- `runtime.txt` – Python runtime version for deployments.
- `buildingsmart_romania_logo.jpg` – Logo displayed in the app.

