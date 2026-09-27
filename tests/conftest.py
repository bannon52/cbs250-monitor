"""Fixtures: a fake switch whose state the tests can mutate between polls."""

from __future__ import annotations

import copy
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cbs250.const import DOMAIN
from custom_components.cbs250.coordinator import PortData, SwitchData


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def make_port(idx, alias="", up=False, poe=None, poe_capable=True):
    return PortData(
        if_index=idx,
        name=f"gi{idx}",
        alias=alias,
        oper_status="up" if up else "down",
        link_speed_mbps=1000 if up else 10,
        rx_mbps=1.5 if up else 0.0,
        tx_mbps=0.5 if up else 0.0,
        poe_capable=poe_capable,
        poe_power_w=poe or 0.0,
        poe_status="delivering_power" if poe else "searching",
    )


class FakeSwitch:
    def __init__(self):
        self.data = SwitchData(
            ports={
                1: make_port(1, alias="Front Camera"),        # labelled, unplugged
                2: make_port(2, up=True),                     # linked, unlabelled
                3: make_port(3, poe=6.2),                     # powering something
                4: make_port(4),                              # nothing at all
                17: make_port(17, poe_capable=False),         # empty SFP uplink
            },
            total_poe_w=6.0,
            nominal_poe_w=120.0,
        )
        self.polls = 0

    async def fetch(self):
        self.polls += 1
        return copy.deepcopy(self.data)


@pytest.fixture
def switch():
    fake = FakeSwitch()
    with patch(
        "custom_components.cbs250.coordinator.Cbs250Coordinator._fetch",
        side_effect=fake.fetch,
    ):
        yield fake


@pytest.fixture
def entry():
    return MockConfigEntry(
        domain=DOMAIN,
        title="Rack Switch",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "192.168.1.2", "community": "test", "port": 161},
    )
