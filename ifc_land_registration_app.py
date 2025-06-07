import streamlit as st
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element as util
import ifcopenshell.guid as guid
import tempfile
import io
from typing import List, Optional

# ---------------------------------------------------------------------------
# 🇷🇴 Plan de situație IFC – Editor înregistrare teren (Streamlit)
# ---------------------------------------------------------------------------
# Rev‑10 (2025‑06‑07): Câmpul „Județ/Regiune” devine dropdown cu toate județele
#     României (inclusiv București). Valoarea implicită se preîncarcă din
#     PSet_Address dacă există.
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Plan de situație IFC", layout="centered")

# Logo
try:
    st.image("buildingsmart_romania_logo.jpg", width=300)
except Exception:
    pass

# ----------------------------------------------------------
# Date statice
# ----------------------------------------------------------
ROM_COUNTIES = [
    "Alba", "Arad", "Argeș", "Bacău", "Bihor", "Bistrița-Năsăud", "Botoșani",
    "Brașov", "Brăila", "București", "Buzău", "Caraș-Severin", "Călărași",
    "Cluj", "Constanța", "Covasna", "Dâmbovița", "Dolj", "Galați", "Giurgiu",
    "Gorj", "Harghita", "Hunedoara", "Ialomița", "Iași", "Ilfov", "Maramureș",
    "Mehedinți", "Mureș", "Neamț", "Olt", "Prahova", "Sălaj", "Satu Mare",
    "Sibiu", "Suceava", "Teleorman", "Timiș", "Tulcea", "Vâlcea", "Vaslui",
    "Vrancea",
]

# ----------------------------------------------------------
# Funcții helper
# ----------------------------------------------------------

def load_ifc_from_upload(uploaded_bytes: bytes):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
    temp.write(uploaded_bytes); temp.flush(); temp.close()
    return ifcopenshell.open(temp.name)


def list_sites(model):
    return model.by_type("IfcSite")


def find_pset_instance(product, pset_name):
    for rel in getattr(product, "HasAssociations", []):
        if rel.is_a("IfcRelDefinesByProperties"):
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet") and pdef.Name == pset_name:
                return pdef
    return None


def pset_or_create(model, product, pset_name):
    pset = find_pset_instance(product, pset_name)
    return pset or ifcopenshell.api.run("pset.add_pset", model, product=product, name=pset_name)


def update_single_value(model, product, pset_name, prop, value):
    pset = pset_or_create(model, product, pset_name)
    ifcopenshell.api.run("pset.edit_pset", model, pset=pset, properties={prop: value})


def get_single_value(product, pset_name, prop):
    pset = util.get_pset(product, pset_name)
    return pset.get(prop, "") if pset else ""


def get_project(model):
    projs = model.by_type("IfcProject")
    return projs[0] if projs else None


def create_beneficiar(model, project, nume, is_org):
    oh = project.OwnerHistory
    if is_org:
        actor = model.create_entity("IfcOrganization", Name=nume)
    else:
        parts = nume.split(maxsplit=1); given, family = (parts + [""])[:2]
        actor = model.create_entity("IfcPerson", GivenName=given, FamilyName=family)
    role = model.create_entity("IfcActorRole", Role="OWNER")
    model.create_entity(
        "IfcRelAssignsToActor",
        GlobalId=guid.new(), OwnerHistory=oh, Name="Beneficiar",
        RelatedObjects=[project], RelatingActor=actor, ActingRole=role,
    )
    return actor

# ----------------------------------------------------------
# UI
# ----------------------------------------------------------

st.title("Plan de situație IFC")

uploaded_file = st.file_uploader("Încarcă un fișier IFC", type=["ifc"], accept_multiple_files=False)

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

    # 1️⃣ Informații proiect
    st.subheader("Informații proiect")
    project_name      = st.text_input("Număr proiect", value=project.Name or "")
    project_long_name = st.text_input("Nume proiect", value=project.LongName or "")

    # 2️⃣ Beneficiar
    st.subheader("Beneficiar")
    beneficiar_type = st.radio("Tip beneficiar", ["Persoană fizică", "Organizație"], horizontal=True)
    beneficiar_nume = st.text_input("Nume beneficiar")

    # 3️⃣ Înregistrare teren + selector sit
    st.subheader("Înregistrare teren (PSet_LandRegistration)")
    idx = st.selectbox(
        "Alegeți situl de editat",
        range(len(sites)),
        format_func=lambda i: f"{sites[i].Name or '(Sit fără nume)'} – {sites[i].GlobalId}")
    site = sites[idx]

    land_title_id = st.text_input("Nr. Cărții funciare", value=get_single_value(site, "PSet_LandRegistration", "LandTitleID"))
    land_id       = st.text_input("Nr. Cadastral",       value=get_single_value(site, "PSet_LandRegistration", "LandId"))

    # 4️⃣ Adresă sit
    st.subheader("Adresă teren (PSet_Address)")
    strada  = st.text_input("Stradă")
    oras    = st.text_input("Oraș")

    default_judet = get_single_value(site, "PSet_Address", "Region")
    try:
        default_idx = ROM_COUNTIES.index(default_judet) if default_judet else 0
    except ValueError:
        default_idx = 0
    judet = st.selectbox("Județ", ROM_COUNTIES, index=default_idx)

    cod  = st.text_input("Cod poștal")

    # -------------------------- Aplică modificări --------------------------
    if st.button("Aplică modificările și generează descărcarea"):
        # Proiect
        project.Name = project_name
        project.LongName = project_long_name

        # Beneficiar
        if beneficiar_nume.strip():
            create_beneficiar(model, project, beneficiar_nume.strip(), is_org=(beneficiar_type=="Organizație"))

        # Înregistrare teren
        update_single_value(model, site, "PSet_LandRegistration", "LandTitleID", land_title_id)
        update_single_value(model, site, "PSet_LandRegistration", "LandId", land_id)

        # Adresă sit
        addr = {"Street": strada, "Town": oras, "Region": judet, "PostalCode": cod, "Country": "Romania"}
        for k, v in addr.items():
            if v:
                update_single_value(model, site, "PSet_Address", k, v)

        # Export IFC
        buf = io.BytesIO(model.to_string().encode("utf-8"))
        st.success("Modificările au fost aplicate! Folosiți butonul de mai jos pentru a descărca fișierul IFC actualizat.")
        st.download_button(
            label="Descarcă IFC actualizat",
            data=buf,
            file_name="updated.ifc",
            mime="application/x-industry-foundation-classes",
        )
