import streamlit as st
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element as util
import ifcopenshell.guid as guid
import tempfile
import io
import os
import base64


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

def load_ifc_from_upload(file_bytes: bytes):
    """Load an IFC model from uploaded bytes."""
    tmp_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as temp_file:
            temp_file.write(file_bytes)
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
    file_bytes = uploaded_file.getvalue()
    model = load_ifc_from_upload(file_bytes)
    
    project = get_project(model)
    if project is None:
        st.error("Nu există niciun IfcProject în model.")
        st.stop()

    sites = list_sites(model)
    if not sites:
        st.error("Nu s-a găsit niciun IfcSite în modelul încărcat.")
        st.stop()

    b64_ifc = base64.b64encode(file_bytes).decode()
    
    # --- START: CORRECTED VIEWER CODE ---
    viewer_html = f"""
    <div id='viewer-container' style='width: 100%; height: 600px; position: relative;'></div>
    <script type='module'>
        // Import the components library
        import * as OBC from 'https://esm.sh/openbim-components';

        const container = document.getElementById('viewer-container');
        const components = new OBC.Components();

        // Configure the main components
        components.scene = new OBC.SimpleScene(components);
        components.renderer = new OBC.PostproductionRenderer(components, container);
        components.camera = new OBC.SimpleCamera(components);
        components.raycaster = new OBC.SimpleRaycaster(components);

        // Initialize the components
        await components.init();

        // Set the scene for the renderer and setup lighting
        components.renderer.setBackdrop(OBC.BackdropColor.Light);
        await components.scene.setup();

        // Add a grid for better spatial context
        new OBC.SimpleGrid(components, {{ size: 100 }});

        // Create a main toolbar for UI elements
        const mainToolbar = new OBC.Toolbar(components, {{
            name: "Main Toolbar",
            position: "bottom",
        }});
        components.ui.add(mainToolbar);

        // Add camera controls (zoom, pan, orbit, fit-to-sphere) to the toolbar
        const cameraControls = new OBC.CameraControls(components);
        mainToolbar.addChild(cameraControls);

        // Set up the IFC importer
        const importer = new OBC.IfcImporter(components);

        // Configure the path to the web-ifc WASM module
        importer.settings.wasm = {{
            path: "https://unpkg.com/web-ifc@0.0.55/",
            absolute: true,
        }};

        // Get the base64 encoded IFC data from Python
        const base64Data = '{b64_ifc}';

        // Load the model
        try {{
            const buffer = Uint8Array.from(atob(base64Data), c => c.charCodeAt(0));
            const model = await importer.load(buffer);
            components.scene.add(model);

            // Fit camera to the model after a short delay to ensure rendering is ready
            setTimeout(() => {{
                cameraControls.fitToSphere(model, true);
            }}, 100);

        }} catch (error) {{
            console.error("Error loading IFC model:", error);
            const errorElement = document.createElement('p');
            errorElement.textContent = `A apărut o eroare la încărcarea modelului 3D: ${{error.message}}`;
            errorElement.style.color = 'red';
            errorElement.style.padding = '20px';
            container.appendChild(errorElement);
        }}
    </script>
    """
    # --- END: CORRECTED VIEWER CODE ---
    
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
        
        # Actualizăm proprietățile de adresă
        address_pset = pset_or_create(model, site, "PSet_Address")
        ifcopenshell.api.run(
            "pset.edit_pset", 
            model, 
            pset=address_pset, 
            properties={k: v.strip() for k, v in address_props.items()}
        )


        # Export IFC
        # Get the IFC content as a string, then encode it to bytes
        ifc_string_content = model.to_string()
        ifc_bytes_content = ifc_string_content.encode("utf-8")
        
        # Create a BytesIO object from the byte content
        file_data = io.BytesIO(ifc_bytes_content)

        st.success("Modificările au fost aplicate! Folosiți butonul de mai jos pentru a descărca fișierul IFC actualizat.")
        st.download_button(
            label="Descarcă IFC îmbogățit",
            data=file_data,
            file_name=f"modificat_{uploaded_file.name if uploaded_file else 'model.ifc'}",
            mime="application/x-industry-foundation-classes",
        )
