
from typing import List

from microkure.exporter.export_object import ExportObject
from microkure.kmodel.kube_container import KubeContainer
from microkure.kmodel.kube_istio import KubeVirtualService, KubeDestinationRule, KubeIstioGateway
from microkure.kmodel.kube_networking import KubeService, KubeIngress, KubeNetworking
from microkure.kmodel.kube_object import KubeObject
from microkure.kmodel.kube_workload import KubeWorkload
from microkure.kmodel.utils import name_is_FQDN


class KubeCluster:

    def __init__(self):
        self.cluster_objects: list[KubeObject] = list()
        self.cluster_export_info: list[ExportObject] = list()

    @property
    def workloads(self):
        return [obj for obj in self.cluster_objects if isinstance(obj, KubeWorkload)]

    @property
    def networkings(self):
        return [n for n in self.cluster_objects if isinstance(n, KubeNetworking)]

    @property
    def services(self):
        return [svc for svc in self.cluster_objects if isinstance(svc, KubeService)]

    @property
    def containers(self):
        return [container for sublist in [w.containers for w in self.workloads] for container in sublist]

    @property
    def ingress(self):
        return [ing for ing in self.cluster_objects if isinstance(ing, KubeIngress)]

    @property
    def virtual_services(self):
        return [vs for vs in self.cluster_objects if isinstance(vs, KubeVirtualService)]

    @property
    def destination_rules(self):
        return [dr for dr in self.cluster_objects if isinstance(dr, KubeDestinationRule)]

    @property
    def istio_gateways(self):
        return [ig for ig in self.cluster_objects if isinstance(ig, KubeIstioGateway)]

    def add_object(self, kube_object):
        if not kube_object in self.cluster_objects:
            self.cluster_objects.append(kube_object)

    def remove_object(self, kube_object):
        if kube_object in self.cluster_objects:
            self.cluster_objects.remove(kube_object)

        for exp in self.cluster_export_info:
            if exp.kube_object == kube_object:
                self.cluster_export_info.remove(exp)

    def add_export_object(self, export_object: ExportObject):
        self.cluster_export_info.append(export_object)

    def find_workload_exposed_by_svc(self, service: KubeService) -> List[KubeWorkload]:
        return [w for w in self.workloads if service.does_expose_workload(w)]

    def find_svc_exposing_workload(self, workload: KubeWorkload):
        return [s for s in self.services if s.does_expose_workload(workload)]

    def get_object_by_name(self, object_name: str, type: type = KubeObject):
        if name_is_FQDN(object_name):
            object_name = '.'.join(object_name.split('.')[:-2])

        objects_found = []
        for obj in self.cluster_objects + self.containers:

            # Case: name is <name>.<namespace>.<shortname>
            if obj.typed_fullname == object_name:
                if not obj in objects_found:
                    objects_found.append(obj)

            # Case: name is <name>.<namespace>
            if obj.fullname == object_name:
                if not obj in objects_found:
                    objects_found.append(obj)

            # Case: name in only <name>
            if obj.name == object_name:
                if not obj in objects_found:
                    objects_found.append(obj)

        objects_found = [o for o in objects_found if isinstance(o, type)]

        #TODO questo controllo non mi convince
        if len(objects_found) == 0 and type == KubeContainer:
            for wl in self.workloads:
                if wl.fullname == object_name or wl.typed_fullname == object_name:
                    if len(wl.containers) == 1:
                        return wl.containers[0]

        if len(objects_found) > 1:
            raise AttributeError(f"More than one object found with name '{object_name}'")

        return objects_found[0] if objects_found else None

    def get_exp_object(self, kube_object):
        for obj in self.cluster_export_info:
            if obj.kube_object == kube_object:
                return obj