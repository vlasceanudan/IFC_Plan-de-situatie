# IFC Plan de situație

This repository contains a small Streamlit application for enriching IFC files with site and land registration information in Romanian.

## Running locally

1. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the app:
   ```bash
   streamlit run ifc_land_registration_app.py
   ```
3. Open the presented local URL in your browser.

Python 3.12 is expected (see `runtime.txt`). A dev container configuration is included for easy setup in VS Code or GitHub Codespaces.

## Usage

After launching the app you will be prompted to upload an IFC file. The interface lets you edit project metadata, beneficiary details, land registration fields and the site address. When you apply the changes, an updated IFC file becomes available for download.

The app is multipage. In the sidebar you can switch to **"Vizualizare IFC 3D"** which opens a viewer for inspecting your model directly in the browser.


## Demo

A live demo is available at [https://ifcplan-de-situatie-v0.streamlit.app/](https://ifcplan-de-situatie-v0.streamlit.app/).

## Repository contents

- `ifc_land_registration_app.py` – Streamlit application.
- `requirements.txt` – Python dependencies.
- `runtime.txt` – Python runtime version for deployments.
- `buildingsmart_romania_logo.jpg` – Logo displayed in the app.
- `pages/1_3D_Viewer.py` – Optional page that renders a 3D preview of the IFC model.

