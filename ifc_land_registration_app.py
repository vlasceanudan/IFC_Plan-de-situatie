import streamlit as st
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element as util
import ifcopenshell.guid as guid
import tempfile
import io
import os
import base64
import re
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# 🇷🇴 Plan de situație IFC – Editor înregistrare teren (Streamlit)
# ---------------------------------------------------------------------------
# Rev‑10 (2025‑06‑07): Câmpul „Județ/Regiune” devine dropdown cu toate județele
#     României (inclusiv București). Valoarea implicită se preîncarcă din
#     PSet_Address dacă există. Adăugat placeholder pentru selecție județ.
#     Corectat load_ifc_from_upload pentru memoryview.
#     Corectat create_beneficiar: eliminat GlobalId pentru IfcOrganization/IfcPerson.

#     Corectat exportul IFC pentru a folosi model.to_string() cu BytesIO.
# ---------------------------------------------------------------------------

THREE_VERSION = "0.160.1"

_THREE_RE = re.compile(r'(["\'])(/three[^"\']*)\1')


def _rewrite_imports(src: str) -> str:
    """Rewrite Three.js imports to use esm.sh with explicit version."""

    def repl(match: re.Match) -> str:
        quote = match.group(1)
        url = match.group(2)
        parts = urlsplit(url)
        path = parts.path
        query = f"?{parts.query}" if parts.query else ""

        after = path[len("/three") :]
        version_spec = ""
        subpath = ""
        if after.startswith("@"):  # e.g. /three@^0.160/examples...
            after = after[1:]
            if "/" in after:
                version_spec, subpath = after.split("/", 1)
                subpath = "/" + subpath
            else:
                version_spec = after
        else:
            subpath = after

        if version_spec:
            if version_spec.startswith((">=", "^", "~")):
                version = THREE_VERSION
            else:
                version = re.sub(r"^[^0-9]*", "", version_spec)
        else:
            version = THREE_VERSION

        return f"{quote}https://esm.sh/three@{version}{subpath}{query}{quote}"

    return _THREE_RE.sub(repl, src)

st.set_page_config(page_title="Plan de situație IFC", layout="centered")

# Global style adjustments
st.markdown(
    """
    <style>
        /* Hide Streamlit default header and footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Slightly larger font for expander headers */
        .streamlit-expanderHeader {
            font-size: 1.2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Logo
try:
    st.image("buildingsmart_romania_logo.jpg", width=300)
except Exception:
    pass

# ----------------------------------------------------------
# Date statice
# ----------------------------------------------------------
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

# ----------------------------------------------------------
# Funcții helper
# ----------------------------------------------------------

def load_ifc_from_upload(uploaded_file_mv: memoryview):
    tmp_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as temp_file:
            temp_file.write(uploaded_file_mv)
            tmp_file_path = temp_file.name
        model = ifcopenshell.open(tmp_file_path)
        return model
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

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
    pset_properties = util.get_pset(product, pset_name)
    return pset_properties.get(prop, "") if pset_properties else ""


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

st.title("Plan de situație IFC - Îmbogățire cu informații")

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

    if uploaded_file:
        b64_ifc = base64.b64encode(uploaded_file.getvalue()).decode()
        viewer_html = f"""
        <div id='viewer-container' style='width: 100%; height: 600px;'></div>
        <script type='module'>
            import * as OBC from 'https://esm.sh/openbim-components@1.5.1';
            import * as FRAGS from 'https://esm.sh/@thatopen/fragments@3.0.7';

            const components = new OBC.Components();
            const worlds = components.get(OBC.Worlds);
            const world = worlds.create(OBC.SimpleScene, OBC.SimpleCamera, OBC.SimpleRenderer);

            world.scene = new OBC.SimpleScene(components);
            world.scene.setup();
            const container = document.getElementById('viewer-container');
            world.renderer = new OBC.SimpleRenderer(components, container);

            world.camera = new OBC.SimpleCamera(components);
            components.init();

            const workerUrl = 'https://thatopen.github.io/engine_fragment/resources/worker.mjs';
            const workerText = await (await fetch(workerUrl)).text();
            const workerFile = new File([workerText], 'worker.mjs', {{ type: 'text/javascript' }});
            const workerBlobURL = URL.createObjectURL(workerFile);
            const fragments = new FRAGS.FragmentsModels(workerBlobURL);
            world.camera.controls.addEventListener('update', () => fragments.update());
            world.camera.controls.addEventListener('rest', () => fragments.update(true));

            const importer = new FRAGS.IfcImporter();
            importer.wasm = {{ absolute: true, path: 'https://unpkg.com/web-ifc@0.0.68/' }};

            const base64Data = '{b64_ifc}';
            const ifcBytes = Uint8Array.from(atob(base64Data), c => c.charCodeAt(0));
            const fragmentBytes = await importer.process({{ bytes: ifcBytes }});
            const model = await fragments.load(fragmentBytes, {{ modelId: 'uploaded' }});
            model.useCamera(world.camera.three);
            world.scene.three.add(model.object);
            await fragments.update(true);
        </script>
        """
        st.components.v1.html(viewer_html, height=600)

    with st.expander("Informații proiect", expanded=True):
        project_name      = st.text_input("Număr proiect", value=project.Name or "")
        project_long_name = st.text_input("Nume proiect", value=project.LongName or "")

    with st.expander("Beneficiar", expanded=True):
        beneficiar_type = st.radio("Tip beneficiar", ["Persoană fizică", "Persoană juridică"], horizontal=True)
        beneficiar_nume = st.text_input("Nume beneficiar")

    with st.expander("Date teren (PSet_LandRegistration)", expanded=True):
        site_options = {i: f"{sites[i].Name or '(Sit fără nume)'} – {sites[i].GlobalId}" for i in range(len(sites))}
        idx = st.selectbox(
            "Alegeți IfcSite-ul de editat",
            options=list(site_options.keys()),
            format_func=lambda i: site_options[i]
        )
        site = sites[idx]

        land_title_id = st.text_input("Nr. Cărții funciare", value=get_single_value(site, "PSet_LandRegistration", "LandTitleID"))
        land_id       = st.text_input("Nr. Cadastral",       value=get_single_value(site, "PSet_LandRegistration", "LandId"))

    with st.expander("Adresă teren (PSet_Address)", expanded=True):
        strada  = st.text_input("Stradă", value=get_single_value(site, "PSet_Address", "Street"))
        oras    = st.text_input("Oraș",   value=get_single_value(site, "PSet_Address", "Town"))

        default_judet_val_from_ifc = get_single_value(site, "PSet_Address", "Region")
        default_select_idx = 0

        if default_judet_val_from_ifc:
            try:
                original_list_idx = ROM_COUNTIES_BASE.index(default_judet_val_from_ifc)
                default_select_idx = original_list_idx + 1
            except ValueError:
                pass

        judet_selection = st.selectbox("Județ", UI_ROM_COUNTIES, index=default_select_idx)

        cod  = st.text_input("Cod poștal", value=get_single_value(site, "PSet_Address", "PostalCode"))

    if st.button("Aplică modificările și generează descărcarea"):
        project.Name = project_name
        project.LongName = project_long_name

        if beneficiar_nume.strip():
            create_beneficiar(model, project, beneficiar_nume.strip(), is_org=(beneficiar_type == "Persoană juridică"))

        update_single_value(model, site, "PSet_LandRegistration", "LandTitleID", land_title_id)
        update_single_value(model, site, "PSet_LandRegistration", "LandId", land_id)

        actual_judet_to_save = judet_selection if judet_selection != DEFAULT_JUDET_PROMPT else ""
        
        address_props = {
            "Street": strada, 
            "Town": oras, 
            "Region": actual_judet_to_save,
            "PostalCode": cod, 
            "Country": "Romania"
        }
        
        has_address_data = any(v for k, v in address_props.items() if k != "Country" and v.strip())

        # Actualizăm proprietățile de adresă
        # PSet-ul va fi creat de update_single_value dacă nu există
        for prop_name, prop_value in address_props.items():
            # Setăm proprietatea doar dacă are valoare sau este "Country"
            # sau dacă PSet-ul există deja și vrem să ștergem valoarea (setând-o la "")
            # Logica actuală: dacă prop_value e gol (ex. "" din UI), va fi setat ca "" în IFC
            if prop_value or prop_name == "Country":
                 update_single_value(model, site, "PSet_Address", prop_name, prop_value.strip())
            elif get_single_value(site, "PSet_Address", prop_name): # Dacă există valoare în IFC dar nu în UI (e goală)
                 update_single_value(model, site, "PSet_Address", prop_name, "") # O setăm la gol


        # --- Corectat aici ---
        # Export IFC
        # Obține conținutul IFC ca string, apoi codifică-l în bytes
        ifc_string_content = model.to_string()
        ifc_bytes_content = ifc_string_content.encode("utf-8")
        
        # Creează un obiect BytesIO din conținutul byte
        file_data = io.BytesIO(ifc_bytes_content)
        # file_data.seek(0) # Nu este necesar aici deoarece BytesIO este inițializat direct cu conținutul
        # --- Sfârșit corecție ---

        st.success("Modificările au fost aplicate! Folosiți butonul de mai jos pentru a descărca fișierul IFC actualizat.")
        st.download_button(
            label="Descarcă IFC îmbogățit",
            data=file_data, # Acum file_data este un BytesIO care conține datele fișierului
            file_name=f"+{uploaded_file.name if uploaded_file else 'model'}",
            mime="application/x-industry-foundation-classes",
        )
