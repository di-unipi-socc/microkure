from microfreshener.core.analyser.costants import REFACTORING_ADD_API_GATEWAY
from microfreshener.core.analyser.smell import NoApiGatewaySmell
from microfreshener.core.model import MicroToscaModel, Service, MessageRouter, MessageBroker

from microkure.template.kobject_generators import generate_svc_NodePort_for_container, generate_svc_ports_for_container, \
    select_ports_for_node_port, convert_port_to_nodeport
from microkure.ignorer.ignorer import IgnoreType
from microkure.ignorer.impl.ignore_nothing import IgnoreNothing
from microkure.kmodel.kube_cluster import KubeCluster
from microkure.kmodel.kube_container import KubeContainer
from microkure.kmodel.kube_networking import KubeService
from microkure.kmodel.kube_workload import KubeWorkload
from microkure.report.report import RefactoringReport
from microkure.report.messages import cannot_apply_refactoring_on_node_msg, created_resource_msg, \
    resource_modified_msg, removed_exposing_params_msg, cannot_find_nodes_msg, exposed_node_port_change
from microkure.report.report_row import RefactoringStatus
from microkure.solver.pending_ops import PENDING_OPS
from microkure.solver.refactoring import RefactoringNotSupportedError, Refactoring


class AddAPIGatewayRefactoring(Refactoring):

    def __init__(self, cluster: KubeCluster, model: MicroToscaModel):
        super().__init__(cluster, model, REFACTORING_ADD_API_GATEWAY)

    def apply(self, smell: NoApiGatewaySmell, ignorer=IgnoreNothing()):
        report_row = RefactoringReport().add_row(smell=smell, refactoring_name=self.name)

        if ignorer.is_ignored(smell.node, IgnoreType.REFACTORING, self.name):
            return False

        if not isinstance(smell, NoApiGatewaySmell):
            raise RefactoringNotSupportedError(f"Refactoring {self.name} not supported for smell {smell.name}")

        if isinstance(smell.node, Service) or isinstance(smell.node, MessageBroker):
            container = self.cluster.get_object_by_name(smell.node.name)

            if container:
                workload = container.defining_workload

                ports_to_expose = generate_svc_ports_for_container(container, is_node_port=True, is_host_network=workload.host_network)
                ports_considered = select_ports_for_node_port(container, workload.host_network)
                expose_svc = self._search_for_existing_svc(workload, ports_considered)

                # Case: exists a Service that can expose this object
                if expose_svc and expose_svc.is_reachable_from_outside():
                    for port in ports_to_expose:
                        port["node_port"] = convert_port_to_nodeport(expose_svc, port["node_port"])
                        expose_svc.ports.append(port)
                    self._refactor_model(expose_svc, smell.node, service_exists=True)

                    # Update report row
                    export_object_fullname = self.cluster.get_exp_object(expose_svc).out_fullname
                    report_row.add_message(resource_modified_msg(expose_svc, export_object_fullname))
                    report_row.status = RefactoringStatus.SUCCESSFULLY_APPLIED

                    result = True

                # Case: need to create a new Service
                else:
                    node_port_service, port_mapping = generate_svc_NodePort_for_container(workload, container, workload.host_network)

                    exp = self._add_to_cluster(node_port_service)
                    self._refactor_model(node_port_service, smell.node, service_exists=False)

                    # Update report row
                    report_row.add_message(created_resource_msg(node_port_service, exp.out_fullname))
                    for new_port, old_port in port_mapping.items():
                        report_row.add_message(exposed_node_port_change(workload.fullname, old_port, new_port))
                    report_row.status = RefactoringStatus.PARTIALLY_APPLIED

                    result = True

                # Remove exposing parameters from Workload and update report
                self._remove_exposing_attributes(workload, container)
                exp_object = self.cluster.get_exp_object(workload)
                exp_fullname = exp_object.out_fullname if exp_object else ""
                report_row.add_message(removed_exposing_params_msg(workload.fullname, exp_fullname))

            else:
                report_row.add_message(cannot_find_nodes_msg([smell.node.name, container.workload_typed_fullname]))
                report_row.status = RefactoringStatus.NOT_APPLIED
                result = False

        else:
            report_row.add_message(cannot_apply_refactoring_on_node_msg(self.name, smell.name, smell.node))
            report_row.status = RefactoringStatus.NOT_APPLIED
            result = False

        return result

    def _remove_exposing_attributes(self, workload: KubeWorkload, container: KubeContainer):
        if workload.host_network:
            if self.solver_pending_ops_ref is not None:
                pending_action = (PENDING_OPS.REMOVE_WORKLOAD_HOST_NETWORK, workload)
                if not pending_action in self.solver_pending_ops_ref:
                    self.solver_pending_ops_ref.append(pending_action)
        else:
            for port in container.ports:
                if port.get("hostPort"):
                    del port["hostPort"]

    def _refactor_model(self, k_service: KubeService, node, service_exists: bool):
        mr_node = self.model.get_node_by_name(k_service.typed_fullname) if service_exists else MessageRouter(k_service.typed_fullname)

        if mr_node:
            if not service_exists:
                self.model.add_node(mr_node)
                self.model.edge.add_member(mr_node)

            self.model.edge.remove_member(node)
            self.model.add_interaction(source_node=mr_node, target_node=node)

    def _search_for_existing_svc(self, workload, ports_considered):
        services = [s for s in self.cluster.services if s.can_expose_workload(workload, ports_considered)]

        if len(services) == 0:
            return None
        elif len(services) == 1:
            expose_svc = services[0]
        else:
            services = sorted(services, key=self.cluster.find_svc_exposing_workload)
            expose_svc = services[0]

        return expose_svc


