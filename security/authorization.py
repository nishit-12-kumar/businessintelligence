"""Role-based authorization module.

Security is enforced BEFORE data access. The authorization check happens
before any query is executed, not as a post-filter.
"""
import yaml
import os
from typing import Tuple, List, Dict, Optional

# Role definitions
ROLES: Dict[str, dict] = {
    "executive": {
        "display_name": "Executive",
        "level": "executive",
        "regions": ["North", "South", "East", "West"],
        "description": "Full access to all regions and KPIs"
    },
    "regional_manager_south": {
        "display_name": "Regional Manager (South)",
        "level": "regional_manager",
        "regions": ["South"],
        "description": "Access limited to South region data only"
    },
    "regional_manager_north": {
        "display_name": "Regional Manager (North)",
        "level": "regional_manager",
        "regions": ["North"],
        "description": "Access limited to North region data only"
    },
    "regional_manager_east": {
        "display_name": "Regional Manager (East)",
        "level": "regional_manager",
        "regions": ["East"],
        "description": "Access limited to East region data only"
    },
    "regional_manager_west": {
        "display_name": "Regional Manager (West)",
        "level": "regional_manager",
        "regions": ["West"],
        "description": "Access limited to West region data only"
    },
    "ops_lead": {
        "display_name": "Operations & Logistics Lead",
        "level": "regional_manager",
        "regions": ["North", "South", "East", "West"],
        "description": "Supply chain & logistics fulfillment operations access"
    },
    "analyst": {
        "display_name": "Data Analyst",
        "level": "executive",
        "regions": ["North", "South", "East", "West"],
        "description": "Full read-only access to all regions and KPIs"
    }
}


def load_kpi_access_rules(yaml_path: str = None) -> dict:
    """Load KPI access rules from the semantic contract."""
    if yaml_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yaml_path = os.path.join(base_dir, 'semantic', 'kpi_definitions.yaml')
    
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)

def get_user_permissions(role: str) -> dict:
    """Get permissions for a given role.
    
    Args:
        role: The role identifier (e.g., 'executive', 'regional_manager_south')
    
    Returns:
        Dict with 'regions', 'level', 'display_name', 'description'
    
    Raises:
        ValueError: If role is not recognized
    """
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}. Available roles: {list(ROLES.keys())}")
    return ROLES[role].copy()

def authorize(role: str, requested_regions: List[str], kpi_name: str = None) -> Tuple[bool, str, List[str]]:
    """Check if a user role is authorized to access data for the requested regions.
    
    This function MUST be called BEFORE any data query is executed.
    
    Args:
        role: The user's role identifier
        requested_regions: List of regions the user wants to access
        kpi_name: Optional KPI name to check specific access rules
    
    Returns:
        Tuple of (is_authorized, message, allowed_regions)
        - is_authorized: True if at least some requested regions are accessible
        - message: Human-readable authorization result
        - allowed_regions: List of regions the user CAN access (subset of requested)
    """
    permissions = get_user_permissions(role)
    user_regions = set(permissions['regions'])
    requested = set(requested_regions)
    
    allowed = requested & user_regions
    denied = requested - user_regions
    
    if not allowed:
        region_str = ', '.join(sorted(denied))
        return (False, 
                f"Access denied. You are not authorized to view {region_str} data.",
                [])
    
    if denied:
        allowed_str = ', '.join(sorted(allowed))
        denied_str = ', '.join(sorted(denied))
        return (True,
                f"Partial access. Showing data for {allowed_str}. Access denied for {denied_str}.",
                sorted(allowed))
    
    return (True, "Access granted.", sorted(allowed))

def check_access(role: str, region: str) -> Tuple[bool, str]:
    """Simple check for a single region.
    
    Args:
        role: The user's role identifier
        region: Single region to check
    
    Returns:
        Tuple of (is_allowed, message)
    """
    is_auth, message, _ = authorize(role, [region])
    return (is_auth, message)

def get_allowed_regions(role: str) -> List[str]:
    """Get all regions a role is allowed to access.
    
    Args:
        role: The user's role identifier
    
    Returns:
        List of allowed region names
    """
    permissions = get_user_permissions(role)
    return permissions['regions'][:]

def get_available_roles() -> Dict[str, str]:
    """Get all available roles with their display names.
    
    Returns:
        Dict mapping role_id to display_name
    """
    return {role_id: info['display_name'] for role_id, info in ROLES.items()}
