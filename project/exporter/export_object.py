import os
import shutil

import yaml

from project.kmodel.kube_object import KubeObject


class ExportObject:

    def __init__(self, kube_object, filename):
        self.kube_object = kube_object
        self.filename = filename
        self.output_fullname = ""

    def export(self, output_folder: str):
        self.output_fullname = f"{output_folder}{self.filename}"
        self._create_folder()

        if self.kube_object is None:
            shutil.copy(self.filename, self.output_fullname) #TODO qui non ho l'import fullname!!!
        elif isinstance(self.kube_object, dict) or isinstance(self.kube_object, KubeObject):
            self._write_to_file()

    def _create_folder(self):
        file_folder = os.path.dirname(self.output_fullname)
        if not os.path.exists(file_folder):
            os.makedirs(file_folder, 0o777)

    def _write_to_file(self):
        YAML_SEPARATOR = "\n---\n\n"

        content = self.kube_object.data if isinstance(self.kube_object, KubeObject) else self.kube_object

        if isinstance(content, dict):
            c = yaml.dump(content, sort_keys=False)

        file_exists = os.path.exists(self.output_fullname)
        with open(self.output_fullname, "a" if file_exists else "w") as f:
            if file_exists:
                f.write(YAML_SEPARATOR)
            f.write(c)