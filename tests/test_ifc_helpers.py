"""Tests for the IFC helper functions in ifc_land_registration_app.

These exercise the pure (non-Streamlit) helpers against a minimal in-memory
IFC model, so they run without launching the Streamlit UI.
"""
import os
import sys

import ifcopenshell
import ifcopenshell.guid as guid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ifc_land_registration_app as app  # noqa: E402


def make_model():
    """Build a minimal IFC4 model with one project and one site."""
    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=guid.new(), Name="P")
    site = model.create_entity("IfcSite", GlobalId=guid.new(), Name="S")
    return model, project, site


def test_pset_roundtrip():
    """update_single_value writes a property readable via get_single_value."""
    model, _project, site = make_model()

    assert app.get_single_value(site, "PSet_LandRegistration", "LandId") == ""

    app.update_single_value(model, site, "PSet_LandRegistration", "LandId", "12345")
    assert app.get_single_value(site, "PSet_LandRegistration", "LandId") == "12345"

    # pset_or_create must reuse the same pset, not create a duplicate.
    app.update_single_value(model, site, "PSet_LandRegistration", "LandTitleID", "CF-99")
    psets = [p for p in model.by_type("IfcPropertySet") if p.Name == "PSet_LandRegistration"]
    assert len(psets) == 1
    assert app.get_single_value(site, "PSet_LandRegistration", "LandTitleID") == "CF-99"


def test_beneficiar_no_duplicate_on_reapply():
    """Calling upsert_beneficiar twice must leave exactly one actor assignment."""
    model, project, _site = make_model()

    app.upsert_beneficiar(model, project, "ACME SRL", is_org=True)
    assert len(model.by_type("IfcRelAssignsToActor")) == 1
    assert len(model.by_type("IfcOrganization")) == 1

    # Re-apply with a different value -> still exactly one of each, updated.
    app.upsert_beneficiar(model, project, "Ion Popescu", is_org=False)
    assert len(model.by_type("IfcRelAssignsToActor")) == 1
    assert len(model.by_type("IfcOrganization")) == 0
    assert len(model.by_type("IfcPerson")) == 1

    nume, is_org = app.get_beneficiar(model)
    assert nume == "Ion Popescu"
    assert is_org is False


def test_get_beneficiar_when_absent():
    model, _project, _site = make_model()
    assert app.get_beneficiar(model) == ("", False)


def test_postal_code_validation():
    assert app.is_valid_postal_code("123456") is True
    assert app.is_valid_postal_code("") is True
    assert app.is_valid_postal_code("12345") is False
    assert app.is_valid_postal_code("12a456") is False
