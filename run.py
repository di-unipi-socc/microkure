import copy
import os.path

import click
from microfreshener.core.analyser import MicroToscaAnalyserBuilder
from microfreshener.core.analyser.costants import REFACTORING_NAMES, REFACTORING_ADD_API_GATEWAY, \
    REFACTORING_ADD_CIRCUIT_BREAKER, REFACTORING_ADD_MESSAGE_ROUTER, REFACTORING_USE_TIMEOUT, \
    REFACTORING_SPLIT_SERVICES, SMELLS_NAME
from microfreshener.core.exporter import YMLExporter
from microfreshener.core.importer import YMLImporter
from microfreshener.core.logging import MyLogger

from microkure.constants import IGNORE_CONFIG_SCHEMA_FILE, TOSCA_OUTPUT_FOLDER
from microkure.exporter.yamlkexporter import YamlKExporter
from microkure.extender.extender import KubeExtender
from microkure.extender.name_adjuster import NameAdjuster
from microkure.extender.worker_names import NAME_WORKER
from microkure.ignorer.impl.ignore_config import IgnoreConfig, IgnoreType
from microkure.ignorer.impl.ignore_nothing import IgnoreNothing
from microkure.importer.yamlkimporter import YamlKImporter
from microkure.report.report import RefactoringReport

from microkure.solver.solver import Solver, KubeSolver
from microkure.utils.utils import create_folder

SELECT_ALL = "all"

REFACTORING = ["add_api_gateway", "add_ag", "add_circuit_breaker", "add_cb", "add_message_router", "add_mr",
               "use_timeouts", "use_ts", "split_services", "split_svcs", SELECT_ALL]


@click.command()
@click.option("--kubepath", "--kube", required=True, type=str, help="Folder containing Kubernetes deploy files of the system")
@click.option("--modelpath", "--model", required=True, type=str, help="MicroTosca file containing the description of the system")
@click.option("--refactoring", "-r", default=["all"], type=click.Choice(REFACTORING), help="Select and apply one refactoring. This option can be used multiple times, for executing multiple refactoring", multiple=True)
@click.option("--ignore_config", "-ig", type=str, help="The file that specifies which smell, refactoring or worker ignore")
def run(kubepath, modelpath, refactoring: list, ignore_config):

    if not os.path.exists(kubepath):
        raise ValueError(f"Kubernetes deployment path passed as 'kube' parameter ({kubepath}) not found")

    if not os.path.exists(modelpath):
        raise ValueError(f"MicroTosca model path passed as 'model' parameter ({modelpath}) not found")

    if not os.path.exists(modelpath):
        raise ValueError(f"File passed as ignore config ({ignore_config}) not found")

    # Import model
    model = YMLImporter().Import(modelpath)

    # Import Kubernetes Cluster
    importer = YamlKImporter()
    cluster = importer.Import(kubepath)

    # Run name worker before everything
    name_extender = KubeExtender([NAME_WORKER])
    name_extender.extend(model, cluster)

    # Read ignore config from disk
    if ignore_config:
        ignorer = IgnoreConfig(ignore_config, IGNORE_CONFIG_SCHEMA_FILE)
        ignorer.adjust_names(name_extender.name_mapping)
    else:
        ignorer = IgnoreNothing()

    # Run extender
    extender = KubeExtender()
    extender.set_all_workers(exclude=[NAME_WORKER])
    extender.extend(model, cluster, ignorer)

    # Create name adjuster for export model with original names
    adjuster = NameAdjuster(extender.name_mapping)

    # Export 'extended-only' model
    export_extended_model(model, adjuster)

    smell_solved = -1
    run_count = 1
    while smell_solved != 0:
        print()
        print(f"Run number: {run_count}")
        print("-----------------------")

        # Run sniffer on the model
        analyser = build_analyser(model, ignorer)
        analyser_result = analyser.run(smell_as_dict=False)

        smells = [smell for sublist in [smell.get("smells", []) for sublist in analyser_result.values() for smell in sublist] for smell in sublist]
        smells = ignore_smells(smells, ignorer)

        # Run smell solver
        solver = build_solver(cluster, model, refactoring, ignorer)
        smell_solved = solver.solve(smells)

        run_count += 1

    MyLogger().get_logger().info("There are no other smells to refactor")

    # Export files
    adjuster.adjust(model)
    exporter = YamlKExporter()
    exporter.export(cluster, model, tosca_model_filename=modelpath)

    # Export report
    RefactoringReport().export()


def ignore_smells(smells, ignorer):
    #TODO in microfreshener-core smell ignoring appear to be commented out. For the moment I have to ignore in this way
    return [s for s in smells if not ignorer.is_ignored(s.node, IgnoreType.SMELLS, s.name)]


def export_extended_model(model, adjuster):
    model_copy = copy.deepcopy(model)
    adjuster.adjust(model_copy)

    tosca_model_str = YMLExporter().Export(model_copy)
    tosca_output_filename = f"{TOSCA_OUTPUT_FOLDER}/extended-only-model.yml"

    create_folder(tosca_output_filename)
    with open(tosca_output_filename, "w") as f:
        f.write(tosca_model_str)


def build_analyser(model, ignore_config):
    analyser = MicroToscaAnalyserBuilder(model).add_all_sniffers().build()

    for node in model.nodes:
        for smell in SMELLS_NAME:
            if ignore_config.is_ignored(node, IgnoreType.SMELLS, smell):
                analyser.ignore_smell_for_node(node, smell)

    return analyser


def build_solver(cluster, model, refactoring, ignorer) -> Solver:
    if SELECT_ALL in refactoring:
        return KubeSolver(cluster, model, REFACTORING_NAMES)

    selected_refactoring = []
    for r in refactoring:
        if r in ["add_api_gateway", "add_ag"]:
            selected_refactoring.append(REFACTORING_ADD_API_GATEWAY)

        if r in ["add_circuit_breaker", "add_cb"]:
            selected_refactoring.append(REFACTORING_ADD_CIRCUIT_BREAKER)

        if r in ["add_messagerouter", "add_mr"]:
            selected_refactoring.append(REFACTORING_ADD_MESSAGE_ROUTER)

        if r in ["use_timeouts", "use_ts"]:
            selected_refactoring.append(REFACTORING_USE_TIMEOUT)

        if r in ["split_services", "split_svcs"]:
            selected_refactoring.append(REFACTORING_SPLIT_SERVICES)

    return KubeSolver(cluster, model, selected_refactoring, ignorer)


if __name__ == '__main__':
    run()
