# Copyright (c) 2015 Servionica, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from keystoneclient.v2_0 import client

from nova import context as nova_context
from nova import image
from nova import objects
from nova.i18n import _
from nova.openstack.common import log as logging
from nova.scheduler import utils

from oslo.config import cfg

import math

auth_options = [
    cfg.StrOpt('admin_user',
               default='nova',
               help='Keystone account username'),
    cfg.StrOpt('admin_password',
               default='nova',
               help='Keystone account password'),
    cfg.StrOpt('admin_tenant_name',
               default='service',
               help='Tenant name'),
    cfg.StrOpt('auth_uri',
               default='http://controller:5000/v2.0',
               help='Public Identity API endpoint'),
]


CONF = cfg.CONF
CONF.register_opts(auth_options, 'keystone_authtoken')
LOG = logging.getLogger(__name__)

nova_client = client.Client(
    username=CONF.keystone_authtoken.admin_user,
    password=CONF.keystone_authtoken.admin_password,
    tenant_name=CONF.keystone_authtoken.admin_tenant_name,
    auth_url=CONF.keystone_authtoken.auth_uri
)

image_api = image.API()


def get_context():
    creds = nova_client
    s_catalog = creds.service_catalog.catalog['serviceCatalog']
    ctx = nova_context.RequestContext(user_id=creds.user_id,
                                      is_admin=True,
                                      project_id=creds.project_id,
                                      user_name=creds.username,
                                      project_name=creds.project_name,
                                      roles=['admin'],
                                      auth_token=creds.auth_token,
                                      remote_address=None,
                                      service_catalog=s_catalog,
                                      request_id=None)
    return ctx


def _get_image(image_uuid):
    ctx = get_context()
    return (image_api.get(ctx, image_uuid), ctx)


def get_instance_object(context, uuid):
    expected_attrs = ['info_cache', 'security_groups',
                      'system_metadata']
    return objects.Instance.get_by_uuid(context, uuid, expected_attrs)


def get_instance_resources(i):
    if i.instance['task_state'] != 'migrating' and i['prev_cpu_time']:
        instance_resources = {'uuid': i.instance['uuid']}
        instance_resources['cpu'] = calculate_cpu(i)
        instance_resources['memory'] = i['mem']
        instance_resources['io'] = i[
            'block_dev_iops'] - i['prev_block_dev_iops']
        return instance_resources
    return None


def build_filter_properties(context, chosen_instance, nodes):
    instance = get_instance_object(context, chosen_instance['uuid'])
    image, ctx = _get_image(instance.get('image_ref'))
    req_spec = utils.build_request_spec(ctx, image, [instance])
    filter_properties = {'context': ctx}
    instance_type = req_spec.get('instance_type')
    project_id = req_spec['instance_properties']['project_id']
    instance_resources = chosen_instance['resources']
    dict_nodes = []
    for n in nodes:
        dict_node = {'memory_total': n['memory_total'],
                     'memory_used': n['memory_used'],
                     'cpu_used_percent': n['cpu_used_percent'],
                     'host': n.compute_node.hypervisor_hostname}
        dict_nodes.append(dict_node)
    filter_properties.update({'instance_type': instance_type,
                              'request_spec': req_spec,
                              'project_id': project_id,
                              'instance_resources': instance_resources,
                              'nodes': dict_nodes})
    return filter_properties


def normalize_params(params, k='uuid'):
    max_values = {}
    min_values = {}
    normalized_params = []
    for param in params:
        for key in param:
            if key != k:
                if max_values.get(key):
                    if max_values[key] < param[key]:
                        max_values[key] = param[key]
                else:
                    max_values[key] = param[key]
                if min_values.get(key):
                    if min_values[key] > param[key]:
                        min_values[key] = param[key]
                else:
                    min_values[key] = param[key]
    LOG.info(_(max_values))
    LOG.info(_(min_values))
    LOG.info(_(params))
    for param in params:
        norm_ins = {}
        for key in param:
            if key != k:
                if len(params) == 1 or max_values[key] == min_values[key]:
                    delta_key = 1
                else:
                    delta_key = max_values[key] - min_values[key]
                norm_ins[key] = float(
                    (param[key] - min_values[key])) / float((delta_key))
                norm_ins[k] = param[k]
        normalized_params.append(norm_ins)
    return normalized_params


def fill_compute_stats(instances, compute_nodes):
    host_loads = {}
    for instance in instances:
            cpu_util = calculate_cpu(instance, compute_nodes)
            if instance.instance['host'] in host_loads:
                host_loads[instance.instance['host']]['mem'] += instance['mem']
                host_loads[instance.instance['host']]['cpu'] += cpu_util
            else:
                host_loads[instance.instance['host']] = {}
                host_loads[instance.instance['host']]['mem'] = instance['mem']
                host_loads[instance.instance['host']]['cpu'] = cpu_util
    for node in compute_nodes:
        if node.compute_node.hypervisor_hostname not in host_loads:
            host_loads[node.compute_node.hypervisor_hostname] = {}
            host_loads[node.compute_node.hypervisor_hostname]['mem'] = 0
            host_loads[node.compute_node.hypervisor_hostname]['cpu'] = 0
    return host_loads


def calculate_host_loads(compute_nodes, compute_stats):
    host_loads = compute_stats
    for node in compute_nodes:
        host_loads[node.compute_node.hypervisor_hostname]['mem'] \
            /= float(node.compute_node.memory_mb)
        host_loads[node.compute_node.hypervisor_hostname]['cpu'] \
            /= 100.00
    return host_loads


def calculate_sd(hosts, param):
    mean = reduce(lambda res, x: res + hosts[x][param],
                  hosts, 0) / len(hosts)
    LOG.debug("Mean %(param)s: %(mean)f", {'mean': mean, 'param': param})
    variaton = float(reduce(
        lambda res, x: res + (hosts[x][param] - mean) ** 2,
        hosts, 0)) / len(hosts)
    sd = math.sqrt(variaton)
    LOG.debug("SD %(param)s: %(sd)f", {'sd': sd, 'param': param})
    return sd


def calculate_cpu(instance, compute_nodes=None):
    instance_host = instance.instance['host']
    if not instance['prev_cpu_time']:
        instance['prev_cpu_time'] = 0
    if instance['prev_cpu_time'] > instance['cpu_time']:
        instance['prev_cpu_time'] = 0
    delta_cpu_time = instance['cpu_time'] - instance['prev_cpu_time']
    delta_time = (instance['updated_at'] - instance['prev_updated_at'])\
        .seconds
    if compute_nodes:
        num_cpu = filter(
            lambda x: x.compute_node.hypervisor_hostname == instance_host,
            compute_nodes)[0].compute_node.vcpus
    else:
        num_cpu = instance.instance['vcpus']
    if delta_time:
        cpu_load = float(delta_cpu_time) / \
            (float(delta_time) * (10 ** 7) * num_cpu)
        cpu_load = round(cpu_load, 2)
        return cpu_load
    return 0
