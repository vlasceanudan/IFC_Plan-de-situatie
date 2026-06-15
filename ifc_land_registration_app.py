import streamlit as st
import ifcopenshell
import ifcopenshell.api.pset
import ifcopenshell.util.element as util
import ifcopenshell.guid as guid
import tempfile
import io
import os

# ---------------------------------------------------------------------------
# 🇷🇴 Plan de situație IFC – Editor înregistrare teren (Streamlit)
# ---------------------------------------------------------------------------
# Rev‑10 (2025‑06‑07): Câmpul „Județ/Regiune” devine dropdown cu toate județele
#     României (inclusiv București). Valoarea implicită se preîncarcă din
#     PSet_Address dacă există. Adăugat placeholder pentru selecție județ.
#     Corectat load_ifc_from_upload pentru memoryview.
#     Corectat create_beneficiar: eliminat GlobalId pentru IfcOrganization/IfcPerson.
#     Corectat exportul IFC pentru a folosi model.to_string() cu BytesIO.
# Rev‑11 (2026‑06‑15): Compatibilitate ifcopenshell 0.8 (API pset directă).
#     Beneficiarul nu se mai dublează la reaplicare (upsert + preîncărcare).
#     Butonul de descărcare persistă prin st.session_state.
#     Încărcare IFC tolerantă la erori, validări ușoare și rezumat modificări.
#     Logica UI mutată în main() pentru a permite importul funcțiilor în teste.
# ---------------------------------------------------------------------------

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

BENEFICIAR_REL_NAME = "Beneficiar"

# ----------------------------------------------------------
# Funcții helper (fără dependențe Streamlit — testabile separat)
# ----------------------------------------------------------

def load_ifc_from_bytes(data: bytes):
    """Scrie conținutul încărcat într-un fișier temporar și deschide modelul IFC.

    Returnează modelul ifcopenshell. Ridică o excepție dacă fișierul nu este
    un IFC valid — apelantul (UI) o tratează și afișează un mesaj prietenos.
    """
    tmp_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as temp_file:
            temp_file.write(data)
            tmp_file_path = temp_file.name
        return ifcopenshell.open(tmp_file_path)
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


def list_sites(model):
    """Returnează toate entitățile IfcSite din model."""
    return model.by_type("IfcSite")


def find_pset_instance(product, pset_name: str):
    """Găsește IfcPropertySet-ul cu numele dat atașat direct produsului."""
    for rel in getattr(product, "HasAssociations", []):
        if rel.is_a("IfcRelDefinesByProperties"):
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet") and pdef.Name == pset_name:
                return pdef
    return None


def pset_or_create(model, product, pset_name: str):
    """Returnează PSet-ul existent sau îl creează dacă lipsește."""
    pset = find_pset_instance(product, pset_name)
    return pset or ifcopenshell.api.pset.add_pset(model, product=product, name=pset_name)


def update_single_value(model, product, pset_name: str, prop: str, value):
    """Setează o singură proprietate într-un PSet (creându-l la nevoie)."""
    pset = pset_or_create(model, product, pset_name)
    ifcopenshell.api.pset.edit_pset(model, pset=pset, properties={prop: value})


def get_single_value(product, pset_name: str, prop: str):
    """Citește o proprietate dintr-un PSet; returnează "" dacă lipsește."""
    pset_properties = util.get_pset(product, pset_name)
    return pset_properties.get(prop, "") if pset_properties else ""


def get_project(model):
    """Returnează primul IfcProject din model sau None."""
    projs = model.by_type("IfcProject")
    return projs[0] if projs else None


def find_beneficiar_rel(model):
    """Returnează relația IfcRelAssignsToActor numită „Beneficiar" sau None."""
    for rel in model.by_type("IfcRelAssignsToActor"):
        if rel.Name == BENEFICIAR_REL_NAME:
            return rel
    return None


def get_beneficiar(model):
    """Returnează (nume, este_organizație) pentru beneficiarul existent.

    Dacă nu există, returnează ("", False).
    """
    rel = find_beneficiar_rel(model)
    if rel is None:
        return "", False
    actor = rel.RelatingActor
    if actor is None:
        return "", False
    if actor.is_a("IfcOrganization"):
        return actor.Name or "", True
    if actor.is_a("IfcPerson"):
        name = " ".join(p for p in [actor.GivenName, actor.FamilyName] if p)
        return name, False
    return "", False


def upsert_beneficiar(model, project, nume: str, is_org: bool):
    """Setează beneficiarul proiectului fără a-l dubla.

    Elimină orice atribuire „Beneficiar" existentă (relație + actor + rol),
    apoi creează una nouă. Astfel reaplicarea sau reîncărcarea unui fișier deja
    îmbogățit nu mai acumulează actori duplicați.
    """
    # Curăță atribuirile existente pentru a evita duplicarea.
    rel = find_beneficiar_rel(model)
    while rel is not None:
        actor = rel.RelatingActor
        role = rel.ActingRole
        model.remove(rel)
        if actor is not None:
            try:
                model.remove(actor)
            except Exception:
                pass
        if role is not None:
            try:
                model.remove(role)
            except Exception:
                pass
        rel = find_beneficiar_rel(model)

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
        GlobalId=guid.new(), OwnerHistory=oh, Name=BENEFICIAR_REL_NAME,
        RelatedObjects=[project], RelatingActor=actor, ActingRole=role,
    )
    return actor


def is_valid_postal_code(code: str) -> bool:
    """Codul poștal românesc are exact 6 cifre. Gol = valid (opțional)."""
    code = (code or "").strip()
    return code == "" or (code.isdigit() and len(code) == 6)


def export_ifc_bytes(model) -> bytes:
    """Serializează modelul IFC în bytes (UTF-8)."""
    return model.to_string().encode("utf-8")


# ----------------------------------------------------------
# UI
# ----------------------------------------------------------

def main():
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

    st.title("Plan de situație IFC - Îmbogățire cu informații")

    uploaded_file = st.file_uploader(
        "Încarcă un fișier IFC", type=["ifc"], accept_multiple_files=False
    )

    if not uploaded_file:
        return

    # La un fișier nou, golim rezultatul anterior (butonul de descărcare).
    if st.session_state.get("uploaded_file_id") != uploaded_file.file_id:
        st.session_state["uploaded_file_id"] = uploaded_file.file_id
        st.session_state.pop("ifc_out", None)

    try:
        model = load_ifc_from_bytes(uploaded_file.getbuffer().tobytes())
    except Exception as exc:  # fișier corupt / non-IFC
        st.error(
            "Nu am putut citi fișierul ca IFC valid. Verificați că este un fișier "
            f".ifc corect.\n\nDetaliu: {exc}"
        )
        st.stop()

    project = get_project(model)
    if project is None:
        st.error("Nu există niciun IfcProject în model.")
        st.stop()

    sites = list_sites(model)
    if not sites:
        st.error("Nu s-a găsit niciun IfcSite în modelul încărcat.")
        st.stop()

    with st.expander("Informații proiect", expanded=True):
        project_name = st.text_input("Număr proiect", value=project.Name or "")
        project_long_name = st.text_input("Nume proiect", value=project.LongName or "")

    with st.expander("Beneficiar", expanded=True):
        existing_nume, existing_is_org = get_beneficiar(model)
        beneficiar_type = st.radio(
            "Tip beneficiar",
            ["Persoană fizică", "Persoană juridică"],
            index=1 if existing_is_org else 0,
            horizontal=True,
        )
        beneficiar_nume = st.text_input("Nume beneficiar", value=existing_nume)

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

    with st.expander("Adresă teren (PSet_Address)", expanded=True):
        strada = st.text_input("Stradă", value=get_single_value(site, "PSet_Address", "Street"))
        oras = st.text_input("Oraș", value=get_single_value(site, "PSet_Address", "Town"))

        default_judet_val_from_ifc = get_single_value(site, "PSet_Address", "Region")
        default_select_idx = 0

        if default_judet_val_from_ifc:
            try:
                original_list_idx = ROM_COUNTIES_BASE.index(default_judet_val_from_ifc)
                default_select_idx = original_list_idx + 1
            except ValueError:
                pass

        judet_selection = st.selectbox("Județ", UI_ROM_COUNTIES, index=default_select_idx)

        cod = st.text_input("Cod poștal", value=get_single_value(site, "PSet_Address", "PostalCode"))

    if st.button("Aplică modificările și generează descărcarea"):
        # Validări ușoare (non-blocante).
        if not is_valid_postal_code(cod):
            st.warning("Codul poștal românesc are de obicei 6 cifre. Valoarea va fi salvată ca atare.")
        if (land_id.strip() or strada.strip() or oras.strip()) and not land_title_id.strip():
            st.warning("Nr. Cărții funciare este gol, deși alte date de teren sunt completate.")

        summary = []

        project.Name = project_name
        project.LongName = project_long_name
        summary.append(("Număr proiect", project_name))
        summary.append(("Nume proiect", project_long_name))

        if beneficiar_nume.strip():
            upsert_beneficiar(
                model, project, beneficiar_nume.strip(),
                is_org=(beneficiar_type == "Persoană juridică"),
            )
            summary.append(("Beneficiar", f"{beneficiar_nume.strip()} ({beneficiar_type})"))
        else:
            st.info("Câmpul „Nume beneficiar” este gol — beneficiarul nu a fost modificat.")

        update_single_value(model, site, "PSet_LandRegistration", "LandTitleID", land_title_id)
        update_single_value(model, site, "PSet_LandRegistration", "LandId", land_id)
        summary.append(("Nr. Cărții funciare", land_title_id))
        summary.append(("Nr. Cadastral", land_id))

        actual_judet_to_save = judet_selection if judet_selection != DEFAULT_JUDET_PROMPT else ""

        address_props = {
            "Street": strada,
            "Town": oras,
            "Region": actual_judet_to_save,
            "PostalCode": cod,
            "Country": "Romania",
        }

        # Actualizăm proprietățile de adresă. PSet-ul va fi creat la nevoie.
        for prop_name, prop_value in address_props.items():
            if prop_value or prop_name == "Country":
                update_single_value(model, site, "PSet_Address", prop_name, prop_value.strip())
            elif get_single_value(site, "PSet_Address", prop_name):
                # Există valoare în IFC dar e goală în UI -> o golim.
                update_single_value(model, site, "PSet_Address", prop_name, "")

        summary.extend([
            ("Stradă", strada),
            ("Oraș", oras),
            ("Județ", actual_judet_to_save),
            ("Cod poștal", cod),
            ("Țară", "Romania"),
        ])

        # Persistăm rezultatul în session_state ca să supraviețuiască rerulării
        # declanșate de butonul de descărcare.
        st.session_state["ifc_out"] = {
            "name": f"+{uploaded_file.name}",
            "data": export_ifc_bytes(model),
            "summary": summary,
        }

    # Randăm rezumatul + butonul de descărcare în afara blocului butonului
    # „Aplică", ca să nu dispară la rerularea cauzată de descărcare.
    out = st.session_state.get("ifc_out")
    if out:
        st.success(
            "Modificările au fost aplicate! Folosiți butonul de mai jos pentru a "
            "descărca fișierul IFC actualizat."
        )
        if out["summary"]:
            st.markdown("**Rezumatul modificărilor:**")
            st.table({
                "Câmp": [k for k, _ in out["summary"]],
                "Valoare": [v if str(v).strip() else "—" for _, v in out["summary"]],
            })
        st.download_button(
            label="Descarcă IFC îmbogățit",
            data=out["data"],
            file_name=out["name"],
            mime="application/x-industry-foundation-classes",
        )


if __name__ == "__main__":
    main()
