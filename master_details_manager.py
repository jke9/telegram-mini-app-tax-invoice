#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Master Details Manager & Shared Registry
=========================================
Provides universal access to Contractors, Customers, Bank Accounts, and Project
locations extracted from 'Tax Invoice Formate Updates.xlsm' (Details sheet).

Usable by ALL Work Types:
  - 01_E_Invoice_Generator
  - 03_Direct_Invoice_Generator
  - 06_Excel_Database_Pipeline
  - 08_Excel_Tax_Invoice_Creator
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_FILE = os.path.join(BASE_DIR, "config", "master_invoice_details.json")


def load_master_registry() -> dict:
    """Loads the master details JSON registry."""
    if not os.path.exists(REGISTRY_FILE):
        return {"contractors": [], "customers": [], "projects": []}
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_contractor_by_name(name_query: str) -> dict:
    """Finds contractor by exact or partial name match."""
    data = load_master_registry()
    query = name_query.strip().lower()
    for c in data.get("contractors", []):
        if query in c["name"].lower():
            return c
    return {}


def get_customer_by_name(name_query: str) -> dict:
    """Finds customer by exact or partial name match."""
    data = load_master_registry()
    query = name_query.strip().lower()
    for cust in data.get("customers", []):
        if query in cust["name"].lower():
            return cust
    return {}


def get_project_by_location(location_query: str) -> dict:
    """Finds project by location key or description."""
    data = load_master_registry()
    query = location_query.strip().lower()
    for p in data.get("projects", []):
        if query in p["location_key"].lower() or query in p["description"].lower():
            return p
    return {}


def list_contractors() -> list:
    return load_master_registry().get("contractors", [])


def list_customers() -> list:
    return load_master_registry().get("customers", [])


def list_projects() -> list:
    return load_master_registry().get("projects", [])


if __name__ == "__main__":
    print("Master Registry Loaded:")
    print(f"  Contractors: {len(list_contractors())}")
    print(f"  Customers:   {len(list_customers())}")
    print(f"  Projects:    {len(list_projects())}")
