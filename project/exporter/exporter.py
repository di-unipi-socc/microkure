from abc import ABC, abstractmethod

from microfreshener.core.model import MicroToscaModel

from project.kmodel.kube_cluster import KubeCluster


class Exporter(ABC):

    @abstractmethod
    def export(self, cluster: KubeCluster, model: MicroToscaModel):
        pass

