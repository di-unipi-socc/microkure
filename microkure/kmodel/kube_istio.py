import re
from typing import List, Dict

from microkure.kmodel.kube_object import KubeObject
from microkure.kmodel.utils import name_has_namespace
from microkure.kmodel.shortnames import ISTIO_VIRTUAL_SERVICE, ISTIO_DESTINATION_RULE, ISTIO_GATEWAY


class KubeIstio(KubeObject):
    pass


class KubeVirtualService(KubeIstio):

    def __init__(self, data: dict):
        super().__init__(data)
        self.shortname = ISTIO_VIRTUAL_SERVICE

    @property
    def timeouts(self):
        result: List[(str, str, str)] = []

        for host in self.data.get('spec', {}).get('hosts', []):
            for http_route in self.data.get('spec', {}).get('http', []):
                for route in http_route.get("route", []):
                    timeout = http_route.get('timeout', None)
                    if timeout is not None:
                        destination = route.get('destination', {}).get('host', None)
                        if destination is not None:
                            host = host if name_has_namespace(host) else f"{host}.{self.namespace}"
                            destination = destination if name_has_namespace(destination) else f"{destination}.{self.namespace}"
                            result.append((host, destination, timeout))
        return result

    @property
    def destinations(self):
        result: List[str] = []
        for http_route in self.data.get('spec', {}).get('http', []):
            for destination_route in http_route.get('route', []):
                destination = destination_route.get('destination', {}).get('host', None)
                if destination is not None:
                    result.append(destination if name_has_namespace(destination) else f"{destination}.{self.namespace}")
        return result

    @property
    def gateways(self):
        res = []
        for g in self.data.get("spec", {}).get("gateways", []):
            res.append(g if name_has_namespace(g) else f"{g}.{self.namespace}")
        return res

    @property
    def hosts(self):
        return self.data.get("spec", {}).get("hosts", [])

    @property
    def selectors(self) -> Dict[str, str]:
        return self.data.get("spec", {}).get("selector", None)


class KubeDestinationRule(KubeIstio):

    def __init__(self, data: dict):
        super().__init__(data)
        self.shortname = ISTIO_DESTINATION_RULE

    @property
    def is_circuit_breaker(self) -> bool:
        return self.data.get("spec", {}).get("trafficPolicy", {}).get("connectionPool", None) is not None
            # and self.data.get("spec", {}).get("trafficPolicy", {}).get("outlierDetection", None) is not None

    @property
    def host(self):
        host = self.data.get("spec", {}).get("host", None)
        return host if name_has_namespace(host) else f"{host}.{self.namespace}"

    @property
    def timeout(self) -> str:
        return self.data.get("spec", {}).get("trafficPolicy", {}).get("connectionPool", {})\
            .get("tcp", {}).get("connectionTimeout", None)


class KubeIstioGateway(KubeIstio):
    def __init__(self, data: dict):
        super().__init__(data)
        self.shortname = ISTIO_GATEWAY

    @property
    def hosts_exposed(self):
        result = []
        servers = self.data.get("spec", {}).get("servers", [])
        for server in servers:
            result += server.get("hosts", [])
        return result

    @property
    def selectors(self) -> dict:
        return self.data.get("spec", {}).get("selector", {})
