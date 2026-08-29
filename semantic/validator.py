"""Semantic Contract Validator.

Validates that kpi_definitions.yaml is complete, contains required fields,
and is structurally consistent.
"""
import yaml
import os
from typing import Dict, List, Tuple

def validate_semantic_contract(yaml_path: str = None) -> Tuple[bool, List[str]]:
    """Validate the KPI semantic contract.
    
    Checks:
    - Required KPIs exist (revenue, orders, asp, conversion_rate)
    - Required fields exist for each KPI (definition, formula, source, dimensions, drivers, threshold, refresh_frequency, lineage, access)
    - Format and consistency of fields
    
    Returns:
        Tuple of (is_valid, list_of_error_strings)
    """
    if yaml_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yaml_path = os.path.join(base_dir, 'semantic', 'kpi_definitions.yaml')
        
    errors = []
    
    if not os.path.exists(yaml_path):
        errors.append(f"Semantic contract file not found at: {yaml_path}")
        return False, errors
        
    try:
        with open(yaml_path, 'r') as f:
            kpi_defs = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"Failed to parse YAML semantic contract: {str(e)}")
        return False, errors
        
    if not isinstance(kpi_defs, dict):
        errors.append("KPI definitions must be a dictionary at the top level of the YAML file.")
        return False, errors
        
    required_kpis = ['revenue', 'orders', 'asp', 'conversion_rate']
    for kpi in required_kpis:
        if kpi not in kpi_defs:
            errors.append(f"Required KPI '{kpi}' is missing from semantic contract.")
            
    required_fields = [
        'definition', 'formula', 'source', 'dimensions', 
        'drivers', 'threshold', 'refresh_frequency', 'lineage', 'access'
    ]
    
    for kpi_name, kpi_def in kpi_defs.items():
        if not isinstance(kpi_def, dict):
            errors.append(f"KPI definition for '{kpi_name}' must be a dictionary.")
            continue
            
        for field in required_fields:
            if field not in kpi_def:
                errors.append(f"KPI '{kpi_name}' is missing required field '{field}'.")
                
        # Validate drivers structure
        drivers = kpi_def.get('drivers', [])
        if not isinstance(drivers, list):
            errors.append(f"KPI '{kpi_name}' 'drivers' must be a list.")
        else:
            for idx, driver in enumerate(drivers):
                if not isinstance(driver, dict):
                    errors.append(f"KPI '{kpi_name}' driver at index {idx} must be a dictionary.")
                else:
                    if 'name' not in driver:
                        errors.append(f"KPI '{kpi_name}' driver at index {idx} is missing 'name' field.")
                    if 'data_source' not in driver:
                        errors.append(f"KPI '{kpi_name}' driver at index {idx} is missing 'data_source' field.")
                        
        # Validate access policy
        access = kpi_def.get('access', {})
        if not isinstance(access, dict):
            errors.append(f"KPI '{kpi_name}' 'access' must be a dictionary.")
        else:
            if 'executive' not in access:
                errors.append(f"KPI '{kpi_name}' access is missing 'executive' policy.")
            if 'regional_manager' not in access:
                errors.append(f"KPI '{kpi_name}' access is missing 'regional_manager' policy.")
                
        # Validate threshold
        threshold = kpi_def.get('threshold')
        if threshold is not None and not isinstance(threshold, (int, float)):
            errors.append(f"KPI '{kpi_name}' threshold must be a number.")
            
    return len(errors) == 0, errors

if __name__ == '__main__':
    valid, errors = validate_semantic_contract()
    if valid:
        print("Semantic contract is valid!")
    else:
        print("Semantic contract validation failed:")
        for err in errors:
            print(f"- {err}")
