git
import allure
import pytest
import random
import copy
import time
from api_automation.conftest import fetch_data
from api_automation.conftest import get_operator_headers
from api_automation.const import NEW_USER_EMAIL
from api_automation.const import CREATE_POOL_MGMT_URL
from api_automation.const import BULK_URL
from api_automation.const import SYSTEMS_FILTER_URL
from api_automation.const import POOL_MANAGEMENT_AUDIT_LOGS_URL
from api_automation.const import ATTRIBUTE_OPTION_URL
from api_automation.const import POOL_MANAGEMENT_URL
from api_automation.logger import logger


@pytest.fixture(scope="module")
def pool_hierarchy(available_pools):
    headers = get_operator_headers()
    # ================= PROGRAM =================
    products=fetch_data(url=f"{ATTRIBUTE_OPTION_URL}?attributes_options=system_types,\
                        hw_config,pool,val_team,project,product,activity,active_state",
                            headers=get_operator_headers(),
                            method="GET",
                            return_response=True)
    assert products.status_code==200
    # All dropdown options
    attribute_options = products.json()
    # Get product options
    product_options = attribute_options["product"]
    assert product_options, "tags.product options not found"   
    existing_programs = {item["name"] for item in available_pools["program_scope"]}
    # Products that are not yet created
    available_products = []
    for product in product_options:
        if product not in existing_programs:
            available_products.append(product)
    assert available_products, "No unused program names available"

    selected_product = random.choice(available_products)

    program_payload = {
        "name": selected_product,
        "description": "testing",
        "owners": [NEW_USER_EMAIL]
    }
    program_response = fetch_data(
        f"{CREATE_POOL_MGMT_URL}/program-scope",
        headers=headers,
        method="POST",
        payload=program_payload,
        return_response=True
    )
    assert program_response.status_code==201
    program_pid = program_response.json()["pgid"]

    # ================= POOL =================
    products=fetch_data(url=f"{ATTRIBUTE_OPTION_URL}?attributes_options=system_types,\
                            hw_config,pool,val_team,project,product,activity,active_state",
                                headers=get_operator_headers(),
                                method="GET",
                                return_response=True)
    assert products.status_code==200
    # All dropdown options
    attribute_options = products.json()
    # Get product options
    product_options = attribute_options["pool"]
    pool_payload = {
        "name": random.choice(product_options),
        "description": "testing",
        "owners": [NEW_USER_EMAIL],
        "psid": program_pid
    }
    pool_response = fetch_data(
        f"{CREATE_POOL_MGMT_URL}/pool",
        headers=headers,
        method="POST",
        payload=pool_payload,
        return_response=True
    )
    assert pool_response.status_code==201
    pool_pid = pool_response.json()["pgid"]

    # ================= SUB POOL=================
    subpool_mapping = {
    "Segment_Customer_Col_Val": [
        "Customer_Col_Val",
        "Rack_Val",
        "Segment_Val"
    ],
    "E2E_Domains": [
        "mem",
        "avms",
        "AtScale",
        "PRISM",
        "IIO",
        "Reset_MMX",
        "ARS",
        "Mem_MMX",
        "CURVE"
    ],
    "Volume Validation": [
        "Reserved",
        "FV_VV",
        "BKC",
        "PV_VV",
        "EV_VV",
        "DPMO_VV"
    ],
    "PTP": [
        "SOC PTP",
        "Platform PTP"
    ],
    "xVST": [
        "FV_sysdebug",
        "PV_sysdebug"
    ]
    }
    time_format = random.choice(["Hours", "Days", "Months"])
    reservation_policy = random.choice(["Restricted", "Unrestricted"])
    duration = {
    "Hours": random.randint(1, 17520),
    "Days": random.randint(1, 730),
    "Months": random.randint(1, 24)
    }[time_format]
    restricted = {
    "Restricted": True,

    "Unrestricted": False

    }[reservation_policy]

    sub_pool_payload={"description":"TESTING",
                      "owners":[NEW_USER_EMAIL],
                      "utilization_threshold":100,
                      "planned_capacity":100,
                      "max_reservation_duration":duration,
                      "restricted":restricted,
                      "name":random.choice(subpool_mapping[pool_payload["name"]]),
                      "pid":pool_pid,
                      "psid":program_pid}
    sub_pool_response = fetch_data(
        f"{CREATE_POOL_MGMT_URL}/sub-pool",
        headers=headers,
        method="POST",
        payload=sub_pool_payload,
        return_response=True
    )
    assert sub_pool_response.status_code==201
    sub_pool_pid = sub_pool_response.json()["pgid"]
    """return {
        "program_pid": program_pid,
        "pool_pid": pool_pid,
        "sub_pool_pid": sub_pool_pid,
        "restricted":restricted,
        "duration":duration,
        "program_name": program_payload["name"],
        "pool_name": pool_payload["name"],
        "sub_pool_name": sub_pool_payload["name"]
    }"""
    hierarchy = {
    "program_pid": program_pid,
    "pool_pid": pool_pid,
    "sub_pool_pid": sub_pool_pid,
    "restricted": restricted,
    "duration": duration,
    "program_name": program_payload["name"],
    "pool_name": pool_payload["name"],
    "sub_pool_name": sub_pool_payload["name"]
}
    

    yield hierarchy

    try:
        delete_pool_hierarchy(hierarchy)
    except Exception as exc:
        logger.error(
            "Failed to delete pool hierarchy: %s",
            exc
        )
   
#===============================================
@pytest.mark.daily_run
@pytest.mark.parametrize(
    "pool_name,pid_key,patch_payload",
    [
        (
            "program-scope",
            "program_pid",
            {
                "description": "testing12",
                "owners": [NEW_USER_EMAIL]
            }
        ),
        (
            "pool",
            "pool_pid",
            {
                "description": "testing12",
                "owners": [NEW_USER_EMAIL]
            }
        ),
        (
            "sub-pool",
            "sub_pool_pid",
            {
                "description": "testing12",
                "owners": [NEW_USER_EMAIL],
                "utilization_threshold": 100,
                "planned_capacity": 100,
                "max_reservation_duration": 2160,
                "restricted": True
            }
        )
    ]
)
def test_pool_crud(
    pool_hierarchy,
    pool_name,
    pid_key,
    patch_payload
):

    pid = pool_hierarchy[pid_key]

    get_url = f"{CREATE_POOL_MGMT_URL}/{pool_name}"
    patch_url = f"{CREATE_POOL_MGMT_URL}/{pool_name}/{pid}"
    validate_audit_log("created")
    # GET VALIDATION
    response = fetch_data(
            get_url,
            headers=get_operator_headers(),
            method="GET",
            return_response=True
        )
    assert response.status_code == 200
    resources = response.json().get("data", [])
    resource = next(
            (
                item for item in resources
                if str(item.get("pgid")) == str(pid)
                or str(item.get("pid")) == str(pid)
            ),
            None
        )
    assert resource is not None, (
            f"Created {pool_name} with PID {pid} not found in GET response"
        )
    returned_pid = resource.get("pgid") or resource.get("pid")
    assert str(returned_pid) == str(pid), (
            f"Expected PID {pid}, but got {returned_pid}"
        )

    # PATCH
    response = fetch_data(
            patch_url,
            headers=get_operator_headers(),
            method="PATCH",
            payload=patch_payload,
            return_response=True
        )
    assert response.status_code == 200
    
    # PATCH VALIDATION

    response = fetch_data(
            get_url,
            headers=get_operator_headers(),
            method="GET",
            return_response=True
    )
    assert response.status_code == 200
    resources = response.json().get("data", [])
    updated_resource = next(
            (
                item for item in resources
                if str(item.get("pgid")) == str(pid)
                or str(item.get("pid")) == str(pid)
            ),
            None
        )
    assert updated_resource is not None, (
            f"Updated {pool_name} with PID {pid} not found"
        )
    returned_pid = updated_resource.get("pgid") or updated_resource.get("pid")
    assert str(returned_pid) == str(pid)
    
    validate_audit_log("updated")

    """# DELETE + VALIDATION
    if pool_name == "sub-pool":

        delete_pool_hierarchy(pool_hierarchy)

        for resource_type, resource_pid in [
        ("sub-pool", pool_hierarchy["sub_pool_pid"]),
        ("pool", pool_hierarchy["pool_pid"]),
        ("program-scope", pool_hierarchy["program_pid"]),
    ]:

            resources = fetch_data(
            f"{CREATE_POOL_MGMT_URL}/{resource_type}",
            headers=get_operator_headers(),
            method="GET",
            return_response=True
        ).json().get("data", [])

            assert not any(
            str(item.get("id")) == str(resource_pid)
            or str(item.get("psid")) == str(resource_pid)
            or str(item.get("pid")) == str(resource_pid)
            or str(item.get("pgid")) == str(resource_pid)
            for item in resources
        ), (
            f"{resource_type} with id {resource_pid} still exists"
        )
        validate_audit_log("deleted")"""

def delete_pool_hierarchy(pool_hierarchy):

    delete_order = [
        ("sub-pool", pool_hierarchy["sub_pool_pid"]),
        ("pool", pool_hierarchy["pool_pid"]),
        ("program-scope", pool_hierarchy["program_pid"]),
    ]

    for pool_type, pid in delete_order:

        response = fetch_data(
            f"{CREATE_POOL_MGMT_URL}/{pool_type}/{pid}",
            headers=get_operator_headers(),
            method="DELETE",
            return_response=True
        )
        assert response.status_code == 204

#======================

PROGRAM_BASE = {
    "name": "scope",
    "description": "testing",
    "owners": [NEW_USER_EMAIL]
}

POOL_BASE = {
    "name": "PTP",
    "description": "testing",
    "owners": [NEW_USER_EMAIL],
    "psid": "program_pid"
}

SUB_POOL_BASE = {
    "name": "FV_VV",
    "description": "testing",
    "owners": [NEW_USER_EMAIL],
    "pid": "pool_id",
    "psid": "program_pid",
    "utilization_threshold": 100,
    "planned_capacity": 1,
    "max_reservation_duration": 100,
    "restricted": True
}

def missing(payload, field):
    data = copy.deepcopy(payload)
    data.pop(field)
    return data


def update(payload, field, value):
    data = copy.deepcopy(payload)
    data[field] = value
    return data
NEGATIVE_SCENARIOS = [

    # ================= PROGRAM =================

    ("program-scope", missing(PROGRAM_BASE, "name")),
    ("program-scope", missing(PROGRAM_BASE, "description")),

    ("program-scope", update(PROGRAM_BASE, "name", "")),
    ("program-scope", update(PROGRAM_BASE, "description", "")),
    ("program-scope", update(PROGRAM_BASE, "owners", [])),

    ("program-scope", update(PROGRAM_BASE, "owners", "abc@zyz.com")),
    ("program-scope", update(PROGRAM_BASE, "owners", 123)),
    ("program-scope", update(PROGRAM_BASE, "owners", {})),
    ("program-scope", update(PROGRAM_BASE, "owners", None)),

    ("program-scope", update(PROGRAM_BASE, "name", 123)),
    ("program-scope", update(PROGRAM_BASE, "description", 123)),

    ("program-scope", update(PROGRAM_BASE,
                             "owners",
                             [NEW_USER_EMAIL] * 6)),

    ("program-scope", update(PROGRAM_BASE,
                             "description",
                             "A" * 513)),
    
    # ================= POOL =================

    ("pool", missing(POOL_BASE, "name")),
    ("pool", missing(POOL_BASE, "description")),
    ("pool", missing(POOL_BASE, "owners")),
    ("pool", missing(POOL_BASE, "psid")),

    ("pool", update(POOL_BASE, "name", "")),
    ("pool", update(POOL_BASE, "description", "")),
    ("pool", update(POOL_BASE, "owners", [])),
    ("pool", update(POOL_BASE, "psid", "")),

    ("pool", update(POOL_BASE, "owners", "abc")),
    ("pool", update(POOL_BASE, "owners", 123)),
    ("pool", update(POOL_BASE, "psid", 123)),
    ("pool", update(POOL_BASE, "psid", None)),

    ("pool", update(POOL_BASE,
                     "owners",
                     [NEW_USER_EMAIL] * 6)),

    ("pool", update(POOL_BASE,
                     "description",
                     "A" * 513)),

    ("pool", update(POOL_BASE,
                     "owners",
                     ["invalid@email.com"])),

    # ================= SUB POOL =================

    ("sub-pool", missing(SUB_POOL_BASE, "name")),
    ("sub-pool", missing(SUB_POOL_BASE, "description")),
    ("sub-pool", missing(SUB_POOL_BASE, "owners")),
    ("sub-pool", missing(SUB_POOL_BASE, "pid")),
    ("sub-pool", missing(SUB_POOL_BASE, "psid")),
    ("sub-pool", missing(SUB_POOL_BASE,
                         "utilization_threshold")),
    ("sub-pool", missing(SUB_POOL_BASE,
                         "planned_capacity")),
    ("sub-pool", missing(SUB_POOL_BASE,
                         "max_reservation_duration")),
    ("sub-pool", missing(SUB_POOL_BASE,
                         "restricted")),

    ("sub-pool", update(SUB_POOL_BASE, "name", "")),
    ("sub-pool", update(SUB_POOL_BASE, "description", "")),
    ("sub-pool", update(SUB_POOL_BASE, "owners", [])),
    ("sub-pool", update(SUB_POOL_BASE, "pid", "")),
    ("sub-pool", update(SUB_POOL_BASE, "psid", "")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "utilization_threshold", "")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "planned_capacity", "")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "max_reservation_duration", "")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "restricted", "")),

    # datatype validations

    ("sub-pool", update(SUB_POOL_BASE, "pid", 123)),
    ("sub-pool", update(SUB_POOL_BASE, "psid", 123)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "owners", "abc")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "owners", 123)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "restricted", 123)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "restricted", "True")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "planned_capacity", "1")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "utilization_threshold", "100")),
    ("sub-pool", update(SUB_POOL_BASE,
                        "max_reservation_duration", "100")),

    # boundary validations

    ("sub-pool", update(SUB_POOL_BASE,
                        "utilization_threshold", -1)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "utilization_threshold", 101)),

    ("sub-pool", update(SUB_POOL_BASE,
                        "planned_capacity", -1)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "planned_capacity", 0)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "planned_capacity", 50001)),

    ("sub-pool", update(SUB_POOL_BASE,
                        "max_reservation_duration", -1)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "max_reservation_duration", 17521)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "max_reservation_duration", 731)),
    ("sub-pool", update(SUB_POOL_BASE,
                        "max_reservation_duration", 25)),

    ("sub-pool", update(SUB_POOL_BASE,
                        "owners",
                        [NEW_USER_EMAIL] * 6)),

    ("sub-pool", update(SUB_POOL_BASE,
                        "description",
                        "A" * 513))
]
@pytest.mark.daily_run
@pytest.mark.parametrize(
    "pool_name,payload",
    NEGATIVE_SCENARIOS
)
def test_pool_negative_scenarios(
    pool_name,
    payload,
):

    payload = payload.copy()

    if payload.get("psid") == "program_pid":
        payload["psid"] = "program_pid"

    if payload.get("pid") == "pool_id":
        payload["pid"] ="pool_pid"

    response = fetch_data(
        f"{CREATE_POOL_MGMT_URL}/{pool_name}",
        headers=get_operator_headers(),
        method="POST",
        payload=payload,
        return_response=True
    )

    assert response.status_code in [400, 422,404,409], (
        f"Payload={payload}, "
        f"Status={response.status_code}, "
        f"Response={response.text}"
    )

DELETE_NEGATIVE_SCENARIOS = [

    # Resource not found
    ("program-scope", "999999999"),
    ("pool", "999999999"),
    ("sub-pool", "999999999"),

    # Invalid ID format
    ("program-scope", "invalid-id"),
    ("pool", "invalid-id"),
    ("sub-pool", "invalid-id"),

    # Special characters
    ("program-scope", "@#$%"),
    ("pool", "@#$%"),
    ("sub-pool", "@#$%"),

    # Dependency validations
    ("program-scope", "program_with_active_pools"),
    ("pool", "pool_with_active_subpools"),

    # Already deleted resources
    ("program-scope", "deleted_program_id"),
    ("pool", "deleted_pool_id"),
    ("sub-pool", "deleted_sub_pool_id"),
]
@pytest.mark.daily_run
@pytest.mark.parametrize(
    "resource_name,resource_id",
    DELETE_NEGATIVE_SCENARIOS
)
def test_delete_negative_scenarios(
    resource_name,
    resource_id,
):
    response = fetch_data(
        f"{CREATE_POOL_MGMT_URL}/{resource_name}/{resource_id}",
        headers=get_operator_headers(),
        method="DELETE",
        return_response=True
    )
    assert response.status_code in [400, 404, 409, 422]

@pytest.mark.daily_run   
def test_pool_already_existed(available_pools):
    available_program_scopes = [
    item["name"]
    for item in available_pools["program_scope"]
]

    selected_program = random.choice(available_program_scopes)

    program_payload = {
        "name": selected_program,
        "description": "testing",
        "owners": [NEW_USER_EMAIL]
    }

    response = fetch_data(
        f"{CREATE_POOL_MGMT_URL}/program-scope",
        headers=get_operator_headers(),
        method="POST",
        payload=program_payload,
        return_response=True
    )
    assert response.status_code in  (404,422,409)
#=============================================
@pytest.fixture(scope="module")
def available_pools():
    response = fetch_data(f"{CREATE_POOL_MGMT_URL}/available?list_all=true",
                          headers=get_operator_headers(),
                          method="GET",
                          return_response=True)
    assert response.status_code == 200
    return response.json()

@pytest.fixture(scope="module")
def systems():
    response = fetch_data(SYSTEMS_FILTER_URL,
                        headers=get_operator_headers(),
                        method="POST",
                        payload={
                            "system_filters": [],
                            "attributes_filter": {},
                            "system_ids": []
                        },
                        return_response=True
                    )
    assert response.status_code == 200
    systems = response.json().get("systems", [])
    return systems
#=====================filter by pool name================
@pytest.mark.p
@pytest.mark.parametrize(
    "pool_type,available_key,pool_key",
    [
        ("Program Scope", "program_scope", "program_scope"),
        ("Pool", "pool", "pool"),
        ("Sub Pool", "sub_pool", "sub_pool"),
    ]
)
def test_filter_by_pool_name(
    available_pools,
    pool_type,
    available_key,
    pool_key
):
    selected_pool = random.choice(available_pools[available_key])
    pool_name = selected_pool["name"]
    # Apply filter
    filtered_response = fetch_data(
        SYSTEMS_FILTER_URL,
        headers=get_operator_headers(),
        method="POST",
        payload={
            "system_filters": [
                {
                    "filter_name": pool_type,
                    "criteria": "one of",
                    "value": [pool_name]
                }
            ],
            "attributes_filter": {},
            "system_ids": []
        },
        return_response=True
    )
    assert filtered_response.status_code == 200
    filtered_systems = filtered_response.json().get("systems", [])

    # Validate all returned systems belong to selected pool
    assert all(
        system.get(pool_key) == pool_name
        for system in filtered_systems
    ), (
        f"Returned systems do not belong to "
        f"{pool_type}: {pool_name}"
    )
    if not filtered_systems:
        return
    assert filtered_systems, (
    f"No systems returned for {pool_type}: {pool_name}")

    assert all(
    system.get(pool_key) == pool_name
    for system in filtered_systems), (
    f"Returned systems do not belong to {pool_type}: {pool_name}")

#===========================audit_logs===================
def validate_audit_log(action):

    response = fetch_data(
        f"{POOL_MANAGEMENT_AUDIT_LOGS_URL}"
        "start=0&limit=50&event_types=Pool+Management",
        headers=get_operator_headers(),
        method="POST",
        payload={
            "system_ids": [],
            "start_date": "",
            "end_date": ""
        },
        return_response=True
    )

    assert response.status_code == 200

    audit_logs = response.json().get("data", [])

    assert any(
        action in log.get("description", "").lower()
        for log in audit_logs
    ), f"No '{action}' audit log found"
#===========================verify filters======================================
@allure.title("Verify Filters")
@pytest.mark.daily_run
@pytest.mark.parametrize(
    "filter_name,key,criteria",
    [
        ("HW Config", "hw_config", "one of"),
        ("System Type", "system_types", "one of"),
        ("Val Team", "val_team", "one of"),
        ("Program Scope", "program_scope", "one of"),
        ("Pool", "pool", "one of"),
        ("Sub Pool", "sub_pool", "one of"),
        *[
            ("HSDES Config", "hsdes_config", c)
            for c in ("contains", "not contain", "is empty", "not empty")
        ]
    ]
)
def test_filters(filter_name, key, criteria):

    if key in ("program_scope", "pool", "sub_pool"):
        value = random.choice(
            fetch_data(
                POOL_MANAGEMENT_URL,
                headers=get_operator_headers(),
                method="GET"
            )[key]
        )["name"]
    elif criteria != "one of":
        value = ""
    else:
        value = random.choice(
            fetch_data(
                f"{ATTRIBUTE_OPTION_URL}?attributes_options="
                "system_types,hw_config,pool,val_team",
                headers=get_operator_headers(),
                method="GET"
            )[key]
        )
    response = fetch_data(
        SYSTEMS_FILTER_URL,
        headers=get_operator_headers(),
        method="POST",
        payload={
            "system_filters": [{
                "filter_name": filter_name,
                "criteria": criteria,
                "value": value
            }],
            "attributes_filter": {},
            "system_ids": []
        },
        return_response=True
    )

    assert response.status_code == 200
    systems = response.json().get("systems", [])

    if not systems:
        return

    field_map = {
        "hw_config": "hw_config",
        "system_types": "system_type",
        "val_team": "val_team",
        "program_scope": "program_scope",
        "pool": "pool",
        "sub_pool": "sub_pool",
    }
    if criteria == "one of":
        assert all(
            str(s.get(field_map[key], "")) == str(value)
            for s in systems
        )
#=============================================
@pytest.fixture(scope="module")
def selected_systems_for_assignment(systems):
    
    return random.sample(
        systems,
        random.randint( 1, min(10, len(systems)))
    )
@pytest.mark.daily_run
@pytest.mark.parametrize(
    "pool_type",
    ["program-scope", "pool", "sub-pool"]
)
@allure.title("Validate Pool Assignment and Dashboard Utilization")
def test_pool_assignment_and_utilization(
    selected_systems_for_assignment,
    pool_hierarchy,
    pool_type
):
    selected_systems = selected_systems_for_assignment
    #logger.info("Selected systems: %s",[system["system_id"] for system in selected_systems])
    
    original_pools = {}

    try:

        pools = fetch_data(
            f"{CREATE_POOL_MGMT_URL}/{pool_type}",
            headers=get_operator_headers(),
            method="GET",
            return_response=True
        ).json()["data"]

        target_id = str(
            {
                "program-scope": pool_hierarchy["program_pid"],
                "pool": pool_hierarchy["pool_pid"],
                "sub-pool": pool_hierarchy["sub_pool_pid"]
            }[pool_type]
        )

        selected_pool = next(
            (
                p for p in pools
                if target_id in map(
                    str,
                    [
                        p.get("id"),
                        p.get("psid"),
                        p.get("pid"),
                        p.get("pgid")
                    ]
                )
            ),
            None
        )

        assert selected_pool is not None, (
            f"Pool Type={pool_type}, Target={target_id}"
        )
        #logger.info("Selected pool type: %s", pool_type)
        #logger.info("Selected pool: %s", selected_pool)

        pool_data = (
            {
                "psid": selected_pool.get("psid")
                or selected_pool.get("pgid")
            }
            if pool_type == "program-scope"
            else {
                "psid": selected_pool["psid"],
                "pid": selected_pool.get("pid")
                or selected_pool.get("pgid")
            }
            if pool_type == "pool"
            else {
                "psid": selected_pool["psid"],
                "pid": selected_pool["pid"],
                "spid": selected_pool["pgid"]
            }
        )

        original_pools = {
            s["system_id"]: {
                "psid": s.get("psid"),
                "pid": s.get("pid"),
                "pgid": s.get("pgid")
            }
            for s in selected_systems
        }

        response = fetch_data(
            BULK_URL,
            headers=get_operator_headers(),
            method="POST",
            payload=[
                {
                    "system_id": s["system_id"],
                    "pools": pool_data
                }
                for s in selected_systems
            ],
            return_response=True
        )

        resp_json = response.json()
        assert response.status_code == 200, response.text
        assert resp_json["failure"] == 0, resp_json
        assert resp_json["success"] > 0, resp_json
        
        if pool_type == "sub-pool":

            for _ in range(10):

                statistics = fetch_data(
                    (
                        f"{CREATE_POOL_MGMT_URL}/statistics"
                        "?pool_type=sub_pool"
                        "&statistics_types=capacity"
                        "&statistics_types=utilization"
                    ),
                    headers=get_operator_headers(),
                    method="GET",
                    return_response=True
                ).json()["statistics"]

                capacity_data = next(
                    (
                        item
                        for stat in statistics
                        if stat["statistics_type"] == "capacity"
                        for item in stat["data"]
                        if item.get("program_scope")
                        == pool_hierarchy["program_name"]
                        and item.get("pool")
                        == pool_hierarchy["pool_name"]
                        and item.get("sub_pool")
                        == pool_hierarchy["sub_pool_name"]
                    ),
                    None
                )

                utilization_data = next(
                    (
                        item
                        for stat in statistics
                        if stat["statistics_type"] == "utilization"
                        for item in stat["data"]
                        if item.get("program_scope")
                        == pool_hierarchy["program_name"]
                        and item.get("pool")
                        == pool_hierarchy["pool_name"]
                        and item.get("sub_pool")
                        == pool_hierarchy["sub_pool_name"]
                    ),
                    None
                )
                

                if capacity_data and utilization_data:
                    break

            assert capacity_data is not None
            assert utilization_data is not None
            assert capacity_data["total_actual_capacity"] >= 0
    
    finally:

        if original_pools:

            try:
                fetch_data(
                    BULK_URL,
                    headers=get_operator_headers(),
                    method="POST",
                    payload=[
                        {
                            "system_id": s["system_id"],
                            "pools": {
                                k: v
                               for k, v in original_pools[
                                    s["system_id"]
                                ].items()
                                if v is not None
                            }
                        }
                        for s in selected_systems
                    ],
                    return_response=True
                )

                fetch_data(
                    BULK_URL,
                    headers=get_operator_headers(),
                    method="POST",
                    payload=[
                        {
                            "system_id": s["system_id"],
                            "pools": {}
                        }
                        for s in selected_systems
                    ],
                    return_response=True
                )

            except Exception as exc:
                print(f"Cleanup failed: {exc}")
