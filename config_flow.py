"""Constants for the CBS250 Monitor integration."""

DOMAIN = "cbs250"

CONF_COMMUNITY = "community"
CONF_ENABLE_CABLE_LENGTH = "enable_cable_length"

DEFAULT_PORT = 161
DEFAULT_COMMUNITY = "public"
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10

# ---------------------------------------------------------------------------
# Standard MIB-2 / IF-MIB OIDs
# ---------------------------------------------------------------------------
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_BRIDGE_MAC = "1.3.6.1.2.1.17.1.1.0"  # dot1dBaseBridgeAddress

OID_IF_TYPE = "1.3.6.1.2.1.2.2.1.3"          # ifType (6 = ethernetCsmacd)
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"   # ifOperStatus
OID_IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"       # ifName (e.g. gi1)
OID_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
OID_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"
OID_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"  # negotiated speed, Mbps
OID_IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"       # port description

# ---------------------------------------------------------------------------
# POWER-ETHERNET-MIB (RFC 3621)
# ---------------------------------------------------------------------------
# pethPsePortDetectionStatus, index: group.port
OID_PETH_PORT_DETECTION = "1.3.6.1.2.1.105.1.1.1.6"
# pethMainPseTable columns, index: col.group
OID_PETH_MAIN_TABLE = "1.3.6.1.2.1.105.1.3.1.1"

PETH_DETECTION_STATUS = {
    1: "disabled",
    2: "searching",
    3: "delivering_power",
    4: "fault",
    5: "test",
    6: "other_fault",
}

IF_OPER_STATUS = {
    1: "up",
    2: "down",
    3: "testing",
    4: "unknown",
    5: "dormant",
    6: "not_present",
    7: "lower_layer_down",
}

# ---------------------------------------------------------------------------
# CISCOSB-POE-MIB  (rlPoe = 1.3.6.1.4.1.9.6.1.101.108)
# rlPethPsePortTable entry columns, index: group.port  (group = 1, non-stacked)
# ---------------------------------------------------------------------------
OID_RL_POE_VOLTAGE = "1.3.6.1.4.1.9.6.1.101.108.1.1.3"   # millivolts
OID_RL_POE_CURRENT = "1.3.6.1.4.1.9.6.1.101.108.1.1.4"   # milliamps
OID_RL_POE_POWER = "1.3.6.1.4.1.9.6.1.101.108.1.1.5"     # milliwatts
OID_RL_POE_STATUS_DESCR = "1.3.6.1.4.1.9.6.1.101.108.1.1.8"

# ---------------------------------------------------------------------------
# CISCOSB-PHY-MIB  (rlPhy = 1.3.6.1.4.1.9.6.1.101.90)
# rlPhyTestGetTable, index: ifIndex.testType
# testType 4 = rlPhyTestTableCableLength
# ---------------------------------------------------------------------------
PHY_TEST_CABLE_LENGTH = 4
OID_RL_PHY_GET_RESULT = "1.3.6.1.4.1.9.6.1.101.90.1.2.1.3"
OID_RL_PHY_GET_STATUS = "1.3.6.1.4.1.9.6.1.101.90.1.2.1.2"
