from typing import List

from microfreshener.core.model import MicroToscaModel, MessageRouter, InteractsWith

from project.extender.kubeworker import KubeWorker
from project.extender.workerimpl.service_worker import ServiceWorker
from project.kmodel.kube_cluster import KubeCluster
from project.kmodel.kube_istio import KubeIstioGateway, KubeVirtualService
from project.kmodel.kube_networking import KubeService


#TODO SISTEMARE LA COSA DEI NOMI

def _check_gateway_virtualservice_match(gateway: KubeIstioGateway, virtual_service: KubeVirtualService):
    gateway_check = gateway.fullname in virtual_service.gateways

    gateway_hosts = gateway.hosts_exposed
    virtual_service_hosts = virtual_service.hosts
    host_check = len([h for h in gateway_hosts if h in virtual_service_hosts])

    return host_check and gateway_check


class IstioWorker(KubeWorker):
    GATEWAY_NODE_GENERIC_NAME = "istio-ingress-gateway"

    def __init__(self):
        super().__init__()
        self.model = None
        self.cluster: KubeCluster = None
        self.executed_only_after_workers.append(ServiceWorker)

    def refine(self, model: MicroToscaModel, kube_cluster: KubeCluster):
        self.model = model
        self.cluster = kube_cluster

        self._search_for_gateways()
        self._search_for_circuit_breaker()
        self._search_for_timeouts()

    def _search_for_timeouts(self):
        self._search_for_timeouts_with_virtual_service()
        self._search_for_timeouts_with_destination_rule()

    def _search_for_timeouts_with_virtual_service(self):
        for vservice in self.cluster.virtual_services:
            #TODO anche qui, do per scontato che nei VServices route e destination siamo definiti come FQDN
            timeouts: List[(list, str)] = vservice.timeouts
            for (route, destination, timeout) in timeouts:
                if route == destination:
                    node = self.model.get_node_by_name(route)
                    if node is not None:
                        for interaction in [r for r in node.incoming_interactions if isinstance(r, InteractsWith)]:
                            interaction.set_timeout(True)
                else:
                    route_mr_node = self.model.get_node_by_name(route)
                    destination_mr_node = self.model.get_node_by_name(destination)

                    if route_mr_node is not None and destination_mr_node is not None:
                        for r in [r for r in route_mr_node.interactions if r.target == destination_mr_node]:
                            r.set_timeout(True)

    def _search_for_timeouts_with_destination_rule(self):
        for rule in self.cluster.destination_rules:
            if rule.timeout is not None:
                mr_node = self.model.get_node_by_name(rule.host)
                for r in list(mr_node.incoming_interactions):
                    r.set_timeout(True)

    def _search_for_circuit_breaker(self):
        for rule in self.cluster.destination_rules:
            if rule.is_circuit_breaker:
                # TODO anche qui suppongo che siano stati usati i FQDN
                node = next(iter([n for n in self.model.nodes if n.name == rule.host]), None)
                if node is not None:
                    for r in node.incoming_interactions:
                        r.set_circuit_breaker(True)

    def _search_for_gateways(self):
        gateway_node = self._find_or_create_gateway()

        for gateway in self.cluster.istio_gateways:

            for virtual_service in self.cluster.virtual_services:
                if _check_gateway_virtualservice_match(gateway, virtual_service):

                    for service in self.cluster.services:
                        if service.fullname in virtual_service.destinations:

                            is_one_pod_exposed = self._has_pod_exposed(gateway=gateway, service=service)
                            if is_one_pod_exposed:
                                service_node = self.model.get_node_by_name(service.fullname
                                                                  + ".svc.cluster.local")

                                if service_node is not None:
                                    self.model.edge.remove_member(service_node)
                                    self.model.add_interaction(source_node=gateway_node, target_node=service_node)

        if len(gateway_node.interactions) + len(gateway_node.incoming_interactions) == 0:
            self.model.delete_node(gateway_node)

    def _find_or_create_gateway(self) -> MessageRouter:
        gateway_node = self.model.get_node_by_name(self.GATEWAY_NODE_GENERIC_NAME)
        if gateway_node is None:
            gateway_node = MessageRouter(self.GATEWAY_NODE_GENERIC_NAME)
            self.model.edge.add_member(gateway_node)
            self.model.add_node(gateway_node)
        return gateway_node

    def _has_pod_exposed(self, service: KubeService, gateway: KubeIstioGateway):
        for workload in self.cluster.find_workload_exposed_by_svc(service):
            labels = workload.labels
            if len([l for l in labels if l in gateway.selectors]) > 0:
                return True
        return False

