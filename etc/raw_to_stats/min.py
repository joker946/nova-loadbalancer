import json
import dateutil.parser


def calculate_cpu(instance, compute_nodes=None):
    instance_host = instance['host']
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
a = calculate_host_loads(compute_nodes, a)
print a
with open('data.json', 'w') as output:
    json.dump(a, output)
