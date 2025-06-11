# ---------------------------------------------------------------------------
# 🇷🇴 Plan de situație IFC – Editor înregistrare teren (Streamlit)
# Rev-12  (2025-06-12)
#   • Zero-copy export for large IFCs (temp-file + streamed handle)
#   • Removed st.on_session_end() to keep compatibility with older Streamlit
#   • Safer download filename, minor tidy-ups
# ---------------------------------------------------------------------------

import streamlit as st
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element as util
import ifcopenshell.guid as guid
import tempfile
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Streamlit page setup & styling
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Plan de situație IFC", layout="centered")
st.markdown(
    """
    <style>
        #MainMenu, header, footer {visibility: hidden;}
        .streamlit-expanderHeader {font-size: 1.2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
try:
    st.image("buildingsmart_romania_logo.jpg", width=300)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------
ROM_COUNTIES_BASE = [
    "Alba", "Arad", "Argeș", "Bacău", "Bihor", "Bistrița-Năsăud", "Botoșani",
    "Brașov", "Brăila", "București", "Buzău", "Caraș-Severin", "Călărași",
    "Cluj", "Constanța", "Covasna", "Dâmbovița", "Dolj", "Galați", "Giurgiu",
    "Gorj", "Harghita", "Hunedoara", "Ialomița", "Iași", "Ilfov", "Maramureș",
    "Mehedinți", "Mureș", "Neamț", "Olt", "Prahova", "Sălaj", "Satu Mare",
    "Sibiu", "Suceava", "Teleorman", "Timiș", "Tulcea", "Vâlcea", "Vaslui",
    "Vrancea",
]
DEFAULT_JUDET_PROMPT = "--- Selectați județul ---"
UI_ROM_COUNTIES = [DEFAULT_JUDET_PROMPT] + ROM_COUNTIES_BASE

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def load_ifc_from_upload(uploaded_mv: memoryview):
    """Persist upload to a temp file → open with IfcOpenShell → delete file."""
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tf:
            tf.write(uploaded_mv)
            tmp_path = tf.name
        return ifcopenshell.open(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def list_sites(model):
    return model.by_type("IfcSite")


def pset_or_create(model, product, pset_name):
    pset = None
    for rel in getattr(product, "HasAssociations", []):
        if rel.is_a("IfcRelDefinesByProperties"):
            pd = rel.RelatingPropertyDefinition
            if pd.is_a("IfcPropertySet") and pd.Name == pset_name:
                pset = pd
                break
    return pset or ifcopenshell.api.run("pset.add_pset", model, product=product, name=pset_name)


def update_single_value(model, product, pset_name, prop, value):
    pset = pset_or_create(model, product, pset_name)
    ifcopenshell.api.run("pset.edit_pset", model, pset=pset, properties={prop: value})


def get_single_value(product, pset_name, prop):
    props = util.get_pset(product, pset_name)
    return props.get(prop, "") if props else ""


def get_project(model):
    projs = model.by_type("IfcProject")
    return projs[0] if projs else None


def create_beneficiar(model, project, nume, is_org):
    oh = project.OwnerHistory
    if is_org:
        actor = model.create_entity("IfcOrganization", Name=nume)
    else:
        parts = nume.split(maxsplit=1)
        given, family = (parts + [""])[:2]
        actor = model.create_entity("IfcPerson", GivenName=given, FamilyName=family)

    role = model.create_entity("IfcActorRole", Role="OWNER")
    model.create_entity(
        "IfcRelAssignsToActor",
        GlobalId=guid.new(),
        OwnerHistory=oh,
        Name="Beneficiar",
        RelatedObjects=[project],
        RelatingActor=actor,
        ActingRole=role,
    )
    return actor


def stream_ifc_for_download(model, original_name: str):
    """
    Write IFC to a temp file on disk (no RAM copy),
    stream that open file handle through download_button,
    then delete the file immediately after.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
    tmp_path = Path(tmp.name)
    tmp.close()  # just needed the path

    with st.spinner("Se scrie fișierul IFC…"):
        model.write(str(tmp_path))

    file_handle = tmp_path.open("rb")
    st.download_button(
        label="Descarcă IFC îmbunătățit",
        data=file_handle,
        file_name=f"{Path(original_name).stem}_imbunatatit.ifc",
        mime="application/x-industry-foundation-classes",
    )
    file_handle.close()
    try:
        tmp_path.unlink(missing_ok=True)
    except Exception:
        pass  # If removal fails (e.g. handle still locked), OS will clean up later


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------
st.title("Plan de situație IFC - Îmbogățire cu informații")

uploaded_file = st.file_uploader(
    "Încarcă un fișier IFC", type=["ifc"], accept_multiple_files=False
)

if uploaded_file:
    model = load_ifc_from_upload(uploaded_file.getbuffer())

    project = get_project(model)
    if project is None:
        st.error("Nu există niciun IfcProject în model.")
        st.stop()

    sites = list_sites(model)
    if not sites:
        st.error("Nu s-a găsit niciun IfcSite în modelul încărcat.")
        st.stop()

    # ------------- Project info -----------------
    with st.expander("Informații proiect", expanded=True):
        project_name = st.text_input("Număr proiect", value=project.Name or "")
        project_long_name = st.text_input("Nume proiect", value=project.LongName or "")

    # ------------- Beneficiary ------------------
    with st.expander("Beneficiar", expanded=True):
        beneficiar_type = st.radio(
            "Tip beneficiar", ["Persoană fizică", "Persoană juridică"], horizontal=True
        )
        beneficiar_nume = st.text_input("Nume beneficiar")

    # ------------- Land registration ------------
    with st.expander("Date teren (PSet_LandRegistration)", expanded=True):
        site_options = {
            i: f"{sites[i].Name or '(Sit fără nume)'} – {sites[i].GlobalId}"
            for i in range(len(sites))
        }
        idx = st.selectbox(
            "Alegeți IfcSite-ul de editat",
            options=list(site_options.keys()),
            format_func=lambda i: site_options[i],
        )
        site = sites[idx]

        land_title_id = st.text_input(
            "Nr. Cărții funciare",
            value=get_single_value(site, "PSet_LandRegistration", "LandTitleID"),
        )
        land_id = st.text_input(
            "Nr. Cadastral",
            value=get_single_value(site, "PSet_LandRegistration", "LandId"),
        )

    # ------------- Address ----------------------
    with st.expander("Adresă teren (PSet_Address)", expanded=True):
        strada = st.text_input("Stradă", value=get_single_value(site, "PSet_Address", "Street"))
        oras = st.text_input("Oraș", value=get_single_value(site, "PSet_Address", "Town"))

        default_region = get_single_value(site, "PSet_Address", "Region")
        try:
            default_idx = ROM_COUNTIES_BASE.index(default_region) + 1
        except ValueError:
            default_idx = 0

        judet_selection = st.selectbox("Județ", UI_ROM_COUNTIES, index=default_idx)
        cod = st.text_input("Cod poștal", value=get_single_value(site, "PSet_Address", "PostalCode"))

    # ------------- Apply / export ---------------
    if st.button("Aplică modificările și generează descărcarea"):
        # Update project
        project.Name = project_name
        project.LongName = project_long_name

        if beneficiar_nume.strip():
            create_beneficiar(
                model, project, beneficiar_nume.strip(), is_org=(beneficiar_type == "Persoană juridică")
            )

        update_single_value(model, site, "PSet_LandRegistration", "LandTitleID", land_title_id)
        update_single_value(model, site, "PSet_LandRegistration", "LandId", land_id)

        address_props = {
            "Street": strada,
            "Town": oras,
            "Region": judet_selection if judet_selection != DEFAULT_JUDET_PROMPT else "",
            "PostalCode": cod,
            "Country": "Romania",
        }
        for prop, val in address_props.items():
            update_single_value(model, site, "PSet_Address", prop, val.strip())

        st.success(
            "Modificările au fost aplicate! Folosiți butonul de mai jos pentru a descărca fișierul IFC actualizat."
        )
        stream_ifc_for_download(model, uploaded_file.name)
