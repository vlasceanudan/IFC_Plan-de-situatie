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

Any Python from 3.10 to 3.14 works with the current `requirements.txt`
(`ifcopenshell>=0.8.4`). A dev container configuration is included for easy
setup in VS Code or GitHub Codespaces.

> **Note on the deployed app.** Streamlit Community Cloud **ignores `runtime.txt`**
> (that's a Heroku convention); it picks the Python version from the app's
> dashboard (**Manage app → Settings → General → Python version**) and currently
> builds on Python 3.14. The `runtime.txt` file is kept only as a hint for other
> tooling and has no effect on the Streamlit deployment.

## Testing

Install the dev dependencies and run the test suite:

```bash
pip install -r requirements-dev.txt
pytest
```

The tests exercise the IFC helper functions (property-set round-trip and the
no-duplicate-beneficiary behaviour) against an in-memory model, without launching
the Streamlit UI.

## Usage

After launching the app you will be prompted to upload an IFC file. The interface lets you edit project metadata, beneficiary details, land registration fields and the site address. When you apply the changes, an updated IFC file becomes available for download.

## Demo

A live demo is available at [https://ifcplan-de-situatie-v0.streamlit.app/](https://ifcplan-de-situatie-v0.streamlit.app/).

## Repository contents

- `ifc_land_registration_app.py` – Streamlit application.
- `requirements.txt` – runtime Python dependencies.
- `requirements-dev.txt` – additional dependencies for running the tests.
- `tests/` – pytest tests for the IFC helper functions.
- `runtime.txt` – Python version hint (ignored by Streamlit Community Cloud, see note above).
- `buildingsmart_romania_logo.jpg` – Logo displayed in the app.

