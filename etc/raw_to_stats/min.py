import json
import dateutil.parser
import math
import pprint

from copy import deepcopy
pp = pprint.PrettyPrinter(depth=3)


def calculate_sd(hosts, param):
    mean = reduce(lambda res, x: res + hosts[x][param],
                  hosts, 0) / len(hosts)
    #LOG.debug("Mean %(param)s: %(mean)f", {'mean': mean, 'param': param})
    variaton = float(reduce(
        lambda res, x: res + (hosts[x][param] - mean) ** 2,
        hosts, 0)) / len(hosts)
    sd = math.sqrt(variaton)
    #LOG.debug("SD %(param)s: %(sd)f", {'sd': sd, 'param': param})
    return sd



def calculate_cpu(instance, compute_nodes=None):
    if not instance['prev_cpu_time']:
        instance['prev_cpu_time'] = 0
    if instance['prev_cpu_time'] > instance['cpu_time']:
        instance['prev_cpu_time'] = 0
    delta_cpu_time = instance['cpu_time'] - instance['prev_cpu_time']
    delta_time = (dateutil.parser.parse(instance['updated_at']) - dateutil.parser.parse(instance['prev_updated_at']))\
        .seconds
    if compute_nodes:
        num_cpu = 8
    else:
        num_cpu = instance['vcpus']
    if delta_time:
        cpu_load = float(delta_cpu_time) / \
            (float(delta_time) * (10 ** 7) * num_cpu)
        cpu_load = round(cpu_load, 2)
        return cpu_load
    return 0


def fill_compute_stats(instances, compute_nodes):
    host_loads = {}
    for instance in instances:
            cpu_util = calculate_cpu(instance, compute_nodes)
            if instance['host'] in host_loads:
                host_loads[instance['host']]['mem'] += instance['mem']
                host_loads[instance['host']]['cpu'] += cpu_util
            else:
                host_loads[instance['host']] = {}
                host_loads[instance['host']]['mem'] = instance['mem']
                host_loads[instance['host']]['cpu'] = cpu_util
    for node in compute_nodes:
        if node['hypervisor_hostname'] not in host_loads:
            host_loads[node['hypervisor_hostname']] = {}
            host_loads[node['hypervisor_hostname']]['mem'] = 0
            host_loads[node['hypervisor_hostname']]['cpu'] = 0
    return host_loads


def calculate_host_loads(compute_nodes, compute_stats):
    host_loads = compute_stats
    for node in compute_nodes:
        host_loads[node['hypervisor_hostname']]['mem'] \
            /= float(node['memory_total'])
        host_loads[node['hypervisor_hostname']]['cpu'] \
            /= 100.00
    return host_loads

data = json.load(open('input_data.json'))
instances = data[0]['instances']
compute_nodes = data[1]['compute_nodes']
a = fill_compute_stats(instances, compute_nodes)
a = [calculate_host_loads(compute_nodes, a)]
pp.pprint(a)
with open('data.json', 'w') as output:
    json.dump(a, output)


def _simulate_migration(instance, node, host_loads, compute_nodes):
    source_host = instance['host']
    target_host = node['hypervisor_hostname']
    vm_ram = instance['mem']
    vm_cpu = calculate_cpu(instance, compute_nodes)
    _host_loads = deepcopy(host_loads)
    #print _host_loads
    _host_loads[source_host]['mem'] -= vm_ram
    _host_loads[source_host]['cpu'] -= vm_cpu
    _host_loads[target_host]['mem'] += vm_ram
    _host_loads[target_host]['cpu'] += vm_cpu
    _host_loads = calculate_host_loads(compute_nodes, _host_loads)
    ram_sd = calculate_sd(_host_loads, 'mem')
    cpu_sd = calculate_sd(_host_loads, 'cpu')
    return {'cpu_sd': cpu_sd,
            'ram_sd': ram_sd,
            'total_sd': cpu_sd + ram_sd}


def min_sd(**kwargs):
    compute_nodes = kwargs.get('nodes')
    host_loads = fill_compute_stats(instances, compute_nodes)
    pp.pprint(host_loads)
    vm_host_map = []
    for instance in instances:
        for node in compute_nodes:
            h_hostname = node['hypervisor_hostname']
            # Source host shouldn't be use.
            if instance['host'] != h_hostname:
                sd = _simulate_migration(instance, node, host_loads,
                                         compute_nodes)
                vm_host_map.append({'host': h_hostname,
                                    'vm': instance['instance_uuid'],
                                    'sd': sd})
    vm_host_map = sorted(vm_host_map, key=lambda x: x['sd']['total_sd'])
    pp.pprint(vm_host_map)


def get_instance_resources(i):
    instance_resources = {'uuid': i['instance_uuid']}
    instance_resources['cpu'] = calculate_cpu(i)
    instance_resources['memory'] = float(i['mem']) / 16384
    instance_resources['io'] = i[
        'block_dev_iops'] - i['prev_block_dev_iops']
    return instance_resources


min_sd(nodes=compute_nodes)

total_memory = 8192
instance_json = []
for i in instances:
    print get_instance_resources(i)
    instance_json.append(get_instance_resources(i))

with open('instance_out.json', 'w') as output_instance:
    json.dump(instance_json, output_instance)
