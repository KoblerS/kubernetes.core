#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = r"""
---
module: helm_info

short_description: Get information from Helm package deployed inside the cluster

version_added: "0.11.0"

author:
  - Lucas Boisserie (@LucasBoisserie)

requirements:
  - "helm (https://github.com/helm/helm/releases)"
  - "yaml (https://pypi.org/project/PyYAML/)"

description:
  -  Get information (values, states, ...) from Helm package deployed inside the cluster.

options:
  release_name:
    description:
      - Release name to manage.
    required: true
    type: str
    aliases: [ name ]
  release_namespace:
    description:
      - Kubernetes namespace where the chart should be installed.
    required: true
    type: str
    aliases: [ namespace ]
  release_state:
    description:
      - Show releases as per their states.
      - Default value is C(deployed) and C(failed).
      - If set to C(all), show all releases without any filter applied.
      - If set to C(deployed), show deployed releases.
      - If set to C(failed), show failed releases.
      - If set to C(pending), show pending releases.
      - If set to C(superseded), show superseded releases.
      - If set to C(uninstalled), show uninstalled releases, if C(helm uninstall --keep-history) was used.
      - If set to C(uninstalling), show releases that are currently being uninstalled.
    type: list
    elements: str
    version_added: "2.3.0"
extends_documentation_fragment:
  - kubernetes.core.helm_common_options
"""

EXAMPLES = r"""
- name: Gather information of Grafana chart inside monitoring namespace
  kubernetes.core.helm_info:
    name: test
    release_namespace: monitoring

- name: Gather information about test-chart with pending state
  kubernetes.core.helm_info:
    name: test-chart
    release_namespace: testenv
    release_state:
    - pending
"""

RETURN = r"""
status:
  type: complex
  description: A dictionary of status output
  returned: only when release exists
  contains:
    app_version:
      type: str
      returned: always
      description: Version of app deployed
    chart:
      type: str
      returned: always
      description: Chart name and chart version
    name:
      type: str
      returned: always
      description: Name of the release
    namespace:
      type: str
      returned: always
      description: Namespace where the release is deployed
    revision:
      type: str
      returned: always
      description: Number of time where the release has been updated
    status:
      type: str
      returned: always
      description: Status of release (can be DEPLOYED, FAILED, ...)
    updated:
      type: str
      returned: always
      description: The Date of last update
    values:
      type: str
      returned: always
      description: Dict of Values used to deploy
"""

import traceback
import copy

try:
    import yaml

    IMP_YAML = True
except ImportError:
    IMP_YAML_ERR = traceback.format_exc()
    IMP_YAML = False

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible_collections.kubernetes.core.plugins.module_utils.helm import (
    run_helm,
    get_values,
    get_helm_binary,
)
from ansible_collections.kubernetes.core.plugins.module_utils.helm_args_common import (
    HELM_AUTH_ARG_SPEC,
    HELM_AUTH_MUTUALLY_EXCLUSIVE,
)


# Get Release from all deployed releases
def get_release(state, release_name):
    if state is not None:
        for release in state:
            if release["name"] == release_name:
                return release
    return None


# Get Release state from deployed release
def get_release_status(module, command, release_name, release_state):
    list_command = command + " list --output=yaml"

    valid_release_states = [
        "all",
        "deployed",
        "failed",
        "pending",
        "superseded",
        "uninstalled",
        "uninstalling",
    ]

    for local_release_state in release_state:
        if local_release_state in valid_release_states:
            list_command += " --%s" % local_release_state

    list_command += " --filter " + release_name
    rc, out, err = run_helm(module, list_command)

    if rc != 0:
        module.fail_json(
            msg="Failure when executing Helm command. Exited {0}.\nstdout: {1}\nstderr: {2}".format(
                rc, out, err
            ),
            command=list_command,
        )

    release = get_release(yaml.safe_load(out), release_name)

    if release is None:  # not install
        return None

    release["values"] = get_values(module, command, release_name)

    return release


def argument_spec():
    arg_spec = copy.deepcopy(HELM_AUTH_ARG_SPEC)
    arg_spec.update(
        dict(
            release_name=dict(type="str", required=True, aliases=["name"]),
            release_namespace=dict(type="str", required=True, aliases=["namespace"]),
            release_state=dict(type="list", default=[], elements="str"),
        )
    )
    return arg_spec


def main():
    global module

    module = AnsibleModule(
        argument_spec=argument_spec(),
        mutually_exclusive=HELM_AUTH_MUTUALLY_EXCLUSIVE,
        supports_check_mode=True,
    )

    if not IMP_YAML:
        module.fail_json(msg=missing_required_lib("yaml"), exception=IMP_YAML_ERR)

    release_name = module.params.get("release_name")
    release_state = module.params.get("release_state")

    helm_cmd_common = get_helm_binary(module)

    release_status = get_release_status(
        module, helm_cmd_common, release_name, release_state
    )

    if release_status is not None:
        module.exit_json(changed=False, status=release_status)

    module.exit_json(changed=False)


if __name__ == "__main__":
    main()
