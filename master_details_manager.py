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
    """Loads the master details JSON registry with multi-path resolution."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(current_dir, "master_invoice_details.json"),
        os.path.join(current_dir, "..", "08_Excel_Tax_Invoice_Creator", "master_invoice_details.json"),
        os.path.join(current_dir, "..", "01_E_Invoice_Generator", "master_invoice_details.json"),
        os.path.join(current_dir, "..", "config", "master_invoice_details.json"),
        REGISTRY_FILE
    ]
    for p in possible_paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {"contractors": [], "customers": [], "projects": []}


def get_contractor_by_name(name_query: str) -> dict:
    """Finds contractor by exact or partial name match."""
    data = load_master_registry()
    if not name_query:
        return {}
    query = name_query.strip().lower()
    for c in data.get("contractors", []):
        if query in c["name"].lower():
            return c
    return {}


def get_customer_by_name(name_query: str) -> dict:
    """Finds customer by exact or partial name match."""
    data = load_master_registry()
    if not name_query:
        return {}
    query = name_query.strip().lower()
    for cust in data.get("customers", []):
        if query in cust["name"].lower():
            return cust
    return {}


def get_project_by_location(location_query: str) -> dict:
    """Finds project by location key, short name, or description."""
    data = load_master_registry()
    if not location_query:
        return {}
    
    query_raw = location_query.strip()
    query_clean = " ".join(query_raw.lower().split())

    projects = data.get("projects", [])
    
    # 1. Exact match on location_key
    for p in projects:
        key_clean = " ".join(p.get("location_key", "").lower().split())
        if query_clean == key_clean:
            return p

    # 2. Substring match
    for p in projects:
        key_clean = " ".join(p.get("location_key", "").lower().split())
        desc_clean = " ".join(p.get("description", "").lower().split())
        if query_clean in key_clean or key_clean in query_clean or query_clean in desc_clean:
            return p

    # 3. Token match (e.g. 'kali', 'asarwa', 'vatva', 'zalod', 'piplaj', 'anjar', 'muthiya', 'kheda')
    tokens = [t for t in query_clean.replace(',', ' ').replace('-', ' ').split() if len(t) > 2 and t not in ['amc', 'gudc', 'gwssb']]
    if tokens:
        for p in projects:
            key_clean = " ".join(p.get("location_key", "").lower().split())
            if any(t in key_clean for t in tokens):
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
