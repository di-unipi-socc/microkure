from microfreshener.core.analyser.costants import REFACTORING_USE_TIMEOUT
from microfreshener.core.analyser.smell import WobblyServiceInteractionSmell, Smell
from microfreshener.core.model import MicroToscaModel, Service, MessageRouter

from microkure.template.kobject_generators import generate_timeout_virtualsvc_for_svc
from microkure.ignorer.ignorer import IgnoreType
from microkure.ignorer.impl.ignore_nothing import IgnoreNothing
from microkure.kmodel.kube_cluster import KubeCluster
from microkure.report.report import RefactoringReport
from microkure.report.messages import cannot_apply_refactoring_on_node_msg, created_resource_msg, handle_error_on_microservice
from microkure.report.report_row import RefactoringStatus
from microkure.solver.refactoring import RefactoringNotSupportedError, Refactoring


class UseTimeoutRefactoring(Refactoring):
    DEFAULT_TIMEOUT_SEC = 2

    def __init__(self, cluster: KubeCluster, model: MicroToscaModel):
        super().__init__(cluster, model, REFACTORING_USE_TIMEOUT)

    def apply(self, smell: Smell, ignorer=IgnoreNothing()):
        if not isinstance(smell, WobblyServiceInteractionSmell):
            raise RefactoringNotSupportedError(f"Refactoring {self.name} not supported for smell {smell.name}")

        if ignorer.is_ignored(smell.node, IgnoreType.REFACTORING, self.name):
            return False

        if isinstance(smell.node, Service):
            for link in smell.links_cause:
                if not link.timeout:

                    if isinstance(link.target, Service):
                        pass
                        # This tool execute the whole process of finding smell ad refactoring multiple times, so this case
                        # will be solved when AddMessageRouter will add a MR in front of the smell node

                    if isinstance(link.target, MessageRouter):
                        k_service = self.cluster.get_object_by_name(link.target.name)

                        virtual_service = generate_timeout_virtualsvc_for_svc(k_service, self.DEFAULT_TIMEOUT_SEC)
                        exp = self._add_to_cluster(virtual_service)

                        # Refactor model
                        for up_interaction in link.target.incoming_interactions:
                            up_interaction.set_timeout(True)

                        report_row = RefactoringReport().add_row(smell=smell, refactoring_name=self.name)
                        report_row.add_message(created_resource_msg(virtual_service, exp.out_fullname))
                        report_row.add_message(handle_error_on_microservice("timeout", smell.node.name))
                        report_row.status = RefactoringStatus.PARTIALLY_APPLIED

            return True
        else:
            report_row = RefactoringReport().add_row(smell=smell, refactoring_name=self.name)
            report_row.add_message(cannot_apply_refactoring_on_node_msg(self.name, smell.name, smell.node))
            report_row.status = RefactoringStatus.NOT_APPLIED
            return False
